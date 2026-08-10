"""Chunking engine.

Selects a strategy, applies overlap, and converts raw candidates into fully
formed :class:`Chunk` objects with identifiers and size metadata. Context
enrichment (heading paths, neighbours, parents) happens in
:mod:`ragforge.context`.
"""

from __future__ import annotations

from ragforge.chunking.base import ChunkCandidate, Chunker, SizeMeter
from ragforge.chunking.code import CodeChunker
from ragforge.chunking.overlap import OverlapApplier
from ragforge.chunking.recursive import RecursiveChunker
from ragforge.chunking.semantic import SemanticChunker
from ragforge.chunking.sentence import SentenceChunker
from ragforge.chunking.structural import StructuralChunker
from ragforge.errors import ChunkingError
from ragforge.models.chunk import Chunk, ChunkMetadata, RetrievalMetadata
from ragforge.models.config import ChunkingConfig, SemanticsConfig, SizeUnit, Strategy
from ragforge.models.document import BlockType, Document
from ragforge.semantics.classifier import RoleClassifier
from ragforge.utils.ids import chunk_id, section_id
from ragforge.utils.text import split_sentences, word_count
from ragforge.utils.tokenizer import get_tokenizer

_STRATEGIES: dict[str, type[Chunker]] = {
    Strategy.SEMANTIC.value: SemanticChunker,
    Strategy.STRUCTURAL.value: StructuralChunker,
    Strategy.RECURSIVE.value: RecursiveChunker,
    Strategy.SENTENCE.value: SentenceChunker,
    Strategy.CODE.value: CodeChunker,
}


def register_strategy(name: str, chunker: type[Chunker]) -> None:
    """Register a custom chunking strategy."""
    _STRATEGIES[name] = chunker


def available_strategies() -> list[str]:
    return sorted([*_STRATEGIES, Strategy.AUTO.value])


class ChunkingEngine:
    """Runs a chunking strategy over documents."""

    def __init__(
        self,
        config: ChunkingConfig | None = None,
        semantics: SemanticsConfig | None = None,
    ) -> None:
        self.config = config or ChunkingConfig()
        self.semantics = semantics or SemanticsConfig()
        self.meter = SizeMeter(self.config.unit, get_tokenizer(self.config.tokenizer))
        self.overlap = OverlapApplier(self.config, self.meter)
        self.classifier = RoleClassifier(
            enabled=self.semantics.enabled, min_terms=self.semantics.min_terms
        )

    # ------------------------------------------------------------------
    def chunk_document(self, document: Document) -> list[Chunk]:
        strategy = self._resolve_strategy(document)
        chunker = self._build(strategy)
        candidates = chunker.chunk(document)
        candidates = [c for c in candidates if c.text.strip()]
        if not candidates:
            return []
        candidates = self.overlap.apply(candidates)
        return self._materialize(document, candidates, strategy)

    # ------------------------------------------------------------------
    def _resolve_strategy(self, document: Document) -> str:
        strategy = self.config.strategy
        if strategy is not Strategy.AUTO:
            return self.config.strategy_name
        structure = document.structure
        blocks = structure.blocks if structure else []
        if not blocks:
            return Strategy.SENTENCE.value
        code_blocks = sum(1 for b in blocks if b.type is BlockType.CODE)
        if code_blocks and code_blocks / max(len(blocks), 1) >= 0.25:
            return Strategy.CODE.value
        if structure and structure.has_headings:
            return Strategy.SEMANTIC.value
        return Strategy.SENTENCE.value

    def _build(self, strategy: str) -> Chunker:
        chunker_cls = _STRATEGIES.get(strategy)
        if chunker_cls is None:
            raise ChunkingError(
                f"Unknown chunking strategy: {strategy}",
                hint=f"Available strategies: {', '.join(available_strategies())}",
            )
        if chunker_cls is StructuralChunker:
            return StructuralChunker(self.config, self.meter, mode="structural")
        if chunker_cls is SemanticChunker:
            return SemanticChunker(self.config, self.meter, classifier=self.classifier)
        return chunker_cls(self.config, self.meter)

    # ------------------------------------------------------------------
    def _materialize(
        self, document: Document, candidates: list[ChunkCandidate], strategy: str
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        total = len(candidates)
        tokenizer = self.meter.tokenizer

        for index, candidate in enumerate(candidates):
            text = candidate.text.strip()
            identifier = chunk_id(document.id, index)
            parent = section_id(document.id, candidate.heading_path, 0)
            role = str(candidate.metadata.get("semantic_role", "knowledge"))
            retrieval = self._retrieval_for(candidate)
            metadata = ChunkMetadata(
                document_id=document.id,
                title=document.title,
                source=document.source,
                section=candidate.section,
                parent_section=candidate.parent_section,
                heading_path=list(candidate.heading_path),
                content_type=candidate.content_type,
                semantic_role=role,
                language=candidate.language,
                chunk_index=index,
                total_chunks=total,
                strategy=strategy,
                unit=self.config.unit.value,
                size=self.meter.size(text),
                char_count=len(text),
                word_count=word_count(text),
                token_count=tokenizer.count_tokens(text),
                sentence_count=len(split_sentences(text)),
                start_offset=candidate.start_offset,
                end_offset=candidate.end_offset,
                overlap_prefix_chars=int(candidate.metadata.get("overlap_prefix_chars", 0)),
                parent_id=parent,
                extra={
                    k: v
                    for k, v in candidate.metadata.items()
                    if k not in {"overlap_prefix_chars", "retrieval_terms", "semantic_role"}
                },
            )
            if candidate.block_types:
                metadata.extra["block_types"] = candidate.block_types
            chunks.append(
                Chunk(
                    id=identifier,
                    content=text,
                    metadata=metadata,
                    retrieval=retrieval,
                )
            )
        return chunks

    def _retrieval_for(self, candidate: ChunkCandidate) -> RetrievalMetadata:
        """Build the retrieval metadata attached to a chunk."""
        if not self.semantics.attach_terms_to_chunks:
            return RetrievalMetadata()
        raw = candidate.metadata.get("retrieval_terms") or {}
        if not isinstance(raw, dict):
            return RetrievalMetadata()
        limit = self.semantics.max_terms_per_field
        payload = {
            key: list(values)[:limit]
            for key, values in raw.items()
            if key in RetrievalMetadata.model_fields and values
        }
        return RetrievalMetadata(**payload)


def chunk_text(
    text: str,
    config: ChunkingConfig | None = None,
    *,
    title: str = "Document",
    source: str = "inline",
) -> list[Chunk]:
    """Chunk raw text with a single call (used by tests and the API)."""
    from ragforge.preprocessing.structure import StructureAnalyzer

    document = Document(title=title, source=source, content=text)
    document = StructureAnalyzer().analyze(document)
    return ChunkingEngine(config).chunk_document(document)


__all__ = [
    "ChunkingEngine",
    "SizeUnit",
    "available_strategies",
    "chunk_text",
    "register_strategy",
]
