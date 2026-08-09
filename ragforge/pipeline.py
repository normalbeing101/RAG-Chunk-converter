"""End-to-end processing pipeline.

    parse -> clean -> analyze structure -> chunk -> enrich
          -> deduplicate -> score -> (embed) -> export

Documents are processed one at a time and their content is released as soon as
chunks are produced, so memory stays proportional to the largest single
document rather than the whole corpus.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Iterator
from pathlib import Path

from ragforge.chunking.engine import ChunkingEngine
from ragforge.context.enricher import ContextEnricher
from ragforge.deduplication.deduplicator import Deduplicator
from ragforge.errors import InputError, RagForgeError
from ragforge.exporters.base import get_exporter
from ragforge.exporters.statistics import write_statistics
from ragforge.models.chunk import Chunk
from ragforge.models.config import ForgeConfig
from ragforge.models.document import Document
from ragforge.models.result import DocumentReport, ForgeResult, Statistics
from ragforge.parsers.base import get_parser, supported_extensions
from ragforge.preprocessing.cleaner import TextCleaner
from ragforge.preprocessing.structure import StructureAnalyzer
from ragforge.quality.scorer import QualityScorer
from ragforge.utils.progress import NullProgress, ProgressReporter

_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
}


class Pipeline:
    """Runs the full chunking pipeline over files, directories or raw text."""

    def __init__(
        self,
        config: ForgeConfig | None = None,
        *,
        progress: ProgressReporter | None = None,
    ) -> None:
        self.config = config or ForgeConfig()
        self.progress = progress or NullProgress()
        self.cleaner = TextCleaner(self.config.cleaning)
        self.analyzer = StructureAnalyzer()
        self.engine = ChunkingEngine(self.config.chunking)
        self.enricher = ContextEnricher(self.config.context)
        self.deduplicator = Deduplicator(self.config.deduplication)
        self.scorer = QualityScorer(self.config.quality, self.config.chunking)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(
        self,
        inputs: Iterable[str | Path] | str | Path,
        *,
        recursive: bool = True,
        write: bool = True,
    ) -> ForgeResult:
        started = time.perf_counter()
        paths = list(discover_inputs(inputs, recursive=recursive))
        if not paths:
            raise InputError(
                "No supported input files were found.",
                hint=f"Supported extensions: {', '.join(supported_extensions())}",
            )

        chunks: list[Chunk] = []
        reports: list[DocumentReport] = []

        self.progress.start(len(paths), "Processing documents")
        for path in paths:
            try:
                document, produced = self.process_file(path)
                chunks.extend(produced)
                reports.append(
                    DocumentReport(
                        document_id=document.id,
                        title=document.title,
                        source=document.source,
                        characters=len(document.content),
                        tokens=self.engine.meter.tokens(document.content),
                        blocks=len(document.blocks),
                        chunks=len(produced),
                    )
                )
            except RagForgeError as exc:
                reports.append(
                    DocumentReport(
                        document_id="",
                        title=path.name,
                        source=str(path),
                        error=str(exc),
                    )
                )
            self.progress.advance(detail=f"{path.name} - {len(chunks)} chunks")
        self.progress.finish()

        chunks = self.finalize(chunks)
        result = ForgeResult(
            chunks=chunks,
            reports=reports,
            statistics=self._statistics(chunks, reports, time.perf_counter() - started),
        )
        if write:
            result.outputs = [str(p) for p in self.export(result)]
        return result

    def iter_chunks(
        self,
        inputs: Iterable[str | Path] | str | Path,
        *,
        recursive: bool = True,
    ) -> Iterator[Chunk]:
        """Yield chunks document by document without retaining the corpus.

        Use this for corpora too large to hold in memory. Corpus-wide stages
        that need to see everything - global deduplication, re-indexing after
        drops - are skipped; per-document enrichment and quality scoring still
        run. Failed documents are skipped silently, so check
        :meth:`process_file` directly if you need error reporting.
        """
        paths = list(discover_inputs(inputs, recursive=recursive))
        self.progress.start(len(paths), "Streaming documents")
        for path in paths:
            try:
                _, chunks = self.process_file(path)
            except RagForgeError:
                self.progress.advance(detail=f"{path.name} - skipped")
                continue
            if self.config.quality.enabled:
                chunks = self.scorer.score_all(chunks)
            yield from chunks
            self.progress.advance(detail=path.name)
        self.progress.finish()

    def stream_to_file(
        self,
        inputs: Iterable[str | Path] | str | Path,
        target: str | Path,
        *,
        recursive: bool = True,
    ) -> Path:
        """Stream chunks straight to a JSONL file with constant memory use."""
        import json

        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        include_quality = self.config.output.include_quality
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for chunk in self.iter_chunks(inputs, recursive=recursive):
                record = chunk.to_record(include_quality=include_quality)
                handle.write(json.dumps(record, ensure_ascii=False))
                handle.write("\n")
        return path

    def process_file(self, path: str | Path) -> tuple[Document, list[Chunk]]:
        """Parse and chunk a single file."""
        file_path = Path(path)
        parser = get_parser(file_path)
        document = parser.parse(file_path)
        return document, self.process_document(document)

    def process_text(
        self, text: str, *, title: str = "Document", source: str = "inline"
    ) -> tuple[Document, list[Chunk]]:
        """Parse and chunk raw text (Markdown flavoured)."""
        from ragforge.parsers.markdown import MarkdownParser

        document = MarkdownParser().parse_text(text, source=source, title=title)
        return document, self.process_document(document)

    def process_document(self, document: Document) -> list[Chunk]:
        """Clean, analyze, chunk and enrich a single document."""
        document = self.cleaner.clean_document(document)
        document = self.analyzer.analyze(document)
        chunks = self.engine.chunk_document(document)
        return self.enricher.enrich(chunks, document)

    def finalize(self, chunks: list[Chunk]) -> list[Chunk]:
        """Corpus-wide steps: dedup, quality, optional filtering and embeddings."""
        dedup = self.deduplicator.run(chunks)
        chunks = dedup.chunks
        chunks = self.scorer.score_all(chunks)

        quality_cfg = self.config.quality
        if quality_cfg.enabled and quality_cfg.drop_low_quality and quality_cfg.min_quality_score:
            chunks = [
                c
                for c in chunks
                if c.quality is None or c.quality.quality_score >= quality_cfg.min_quality_score
            ]

        # Re-index after any removal so indices/neighbours stay consistent.
        chunks = self._reindex(chunks)

        if self.config.embeddings.enabled:
            from ragforge.embeddings.base import get_provider

            provider = get_provider(self.config.embeddings)
            chunks = provider.embed_chunks(chunks)
        return chunks

    def export(self, result: ForgeResult) -> list[Path]:
        """Write the dataset (and statistics) to disk."""
        out_cfg = self.config.output
        directory = Path(out_cfg.path)
        exporter = get_exporter(out_cfg.format.value, out_cfg)
        target = directory / f"{out_cfg.filename}{exporter.extension}"
        written = [exporter.write(result.chunks, target)]
        if out_cfg.write_statistics:
            written.append(write_statistics(result.statistics, directory / "statistics.json"))
        return written

    # ------------------------------------------------------------------
    def _reindex(self, chunks: list[Chunk]) -> list[Chunk]:
        by_document: dict[str, list[Chunk]] = {}
        for chunk in chunks:
            by_document.setdefault(chunk.metadata.document_id, []).append(chunk)
        for group in by_document.values():
            total = len(group)
            for index, chunk in enumerate(group):
                chunk.metadata.chunk_index = index
                chunk.metadata.total_chunks = total
            if self.config.context.include_neighbors:
                for index, chunk in enumerate(group):
                    chunk.metadata.previous_chunk = group[index - 1].id if index else None
                    chunk.metadata.next_chunk = group[index + 1].id if index + 1 < total else None
        return chunks

    def _statistics(
        self, chunks: list[Chunk], reports: list[DocumentReport], elapsed: float
    ) -> Statistics:
        return Statistics.from_chunks(
            chunks,
            reports=reports,
            project=self.config.project.name,
            strategy=self.config.chunking.strategy_name,
            unit=self.config.chunking.unit.value,
            elapsed=elapsed,
        )


# ----------------------------------------------------------------------
def discover_inputs(
    inputs: Iterable[str | Path] | str | Path, *, recursive: bool = True
) -> Iterator[Path]:
    """Yield supported files from a mix of file and directory paths."""
    if isinstance(inputs, str | Path):
        inputs = [inputs]
    extensions = set(supported_extensions())
    seen: set[Path] = set()

    for raw in inputs:
        path = Path(raw)
        if not path.exists():
            raise InputError(f"Input path does not exist: {path}")
        if path.is_file():
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield path
            continue
        pattern = "**/*" if recursive else "*"
        for candidate in sorted(path.glob(pattern)):
            if not candidate.is_file():
                continue
            if any(part in _SKIP_DIRS for part in candidate.parts):
                continue
            if candidate.suffix.lower() not in extensions:
                continue
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield candidate


def process(
    inputs: Iterable[str | Path] | str | Path,
    config: ForgeConfig | None = None,
    *,
    write: bool = False,
    recursive: bool = True,
) -> ForgeResult:
    """One-call helper for library users."""
    return Pipeline(config).run(inputs, recursive=recursive, write=write)
