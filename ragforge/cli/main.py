"""``ragforge`` command line interface."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from ragforge import __version__
from ragforge.chunking.engine import available_strategies
from ragforge.cli import render
from ragforge.errors import InputError, RagForgeError
from ragforge.exporters.base import available_formats, get_exporter
from ragforge.exporters.statistics import write_statistics
from ragforge.models.chunk import Chunk, ChunkMetadata, ChunkQuality
from ragforge.models.config import ForgeConfig, OutputFormat, SizeUnit, Strategy
from ragforge.models.result import ForgeResult, Statistics
from ragforge.parsers.base import supported_extensions
from ragforge.pipeline import Pipeline
from ragforge.quality.validator import DatasetValidator

app = typer.Typer(
    name="ragforge",
    help="Intelligent document chunking for production RAG datasets.",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

_DEBUG = {"enabled": False}


# ----------------------------------------------------------------------
# Shared option handling
# ----------------------------------------------------------------------
def _load_config(
    config_path: Path | None,
    *,
    strategy: str | None = None,
    chunk_size: int | None = None,
    min_size: int | None = None,
    max_size: int | None = None,
    overlap: float | None = None,
    unit: str | None = None,
    output: Path | None = None,
    output_format: str | None = None,
    no_dedup: bool = False,
    no_clean: bool = False,
    no_context: bool = False,
    tokenizer: str | None = None,
    reference: Path | None = None,
) -> ForgeConfig:
    if config_path is not None:
        config = ForgeConfig.load(config_path)
    else:
        config = ForgeConfig.discover(reference) or ForgeConfig()

    chunking = config.chunking.model_dump()
    if strategy:
        chunking["strategy"] = Strategy(strategy)
    if chunk_size is not None:
        chunking["target_size"] = chunk_size
        if max_size is None and chunk_size > config.chunking.max_size:
            chunking["max_size"] = int(chunk_size * 1.6)
        if min_size is None and chunk_size < config.chunking.min_size:
            chunking["min_size"] = max(1, int(chunk_size * 0.2))
    if min_size is not None:
        chunking["min_size"] = min_size
    if max_size is not None:
        chunking["max_size"] = max_size
    if overlap is not None:
        chunking["overlap"] = overlap
    if unit:
        chunking["unit"] = SizeUnit(unit)
    if tokenizer:
        chunking["tokenizer"] = tokenizer
    config.chunking = type(config.chunking)(**chunking)

    if no_dedup:
        config.deduplication.enabled = False
    if no_clean:
        config.cleaning.enabled = False
    if no_context:
        config.context.include_context_prefix = False
        config.context.include_neighbors = False

    if output is not None:
        if output.suffix:
            config.output.path = str(output.parent) if str(output.parent) != "" else "."
            config.output.filename = output.stem
            inferred = _format_from_suffix(output.suffix)
            if inferred and output_format is None:
                config.output.format = inferred
        else:
            config.output.path = str(output)
    if output_format:
        config.output.format = OutputFormat(output_format)
    return config


def _format_from_suffix(suffix: str) -> OutputFormat | None:
    mapping = {
        ".jsonl": OutputFormat.JSONL,
        ".ndjson": OutputFormat.JSONL,
        ".json": OutputFormat.JSON,
        ".csv": OutputFormat.CSV,
        ".md": OutputFormat.MARKDOWN,
        ".markdown": OutputFormat.MARKDOWN,
    }
    return mapping.get(suffix.lower())


def _fail(exc: RagForgeError) -> None:
    if _DEBUG["enabled"]:
        raise exc
    render.print_error(str(exc), getattr(exc, "hint", None))
    raise typer.Exit(code=1)


def _version_callback(value: bool) -> None:
    if value:
        render.console.print(f"ragforge {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version", "-V", callback=_version_callback, is_eager=True, help="Show version."
        ),
    ] = False,
    debug: Annotated[bool, typer.Option("--debug", help="Show full tracebacks.")] = False,
) -> None:
    _DEBUG["enabled"] = debug


# ----------------------------------------------------------------------
# process
# ----------------------------------------------------------------------
@app.command()
def process(
    inputs: Annotated[list[Path], typer.Argument(help="Files and/or directories to process.")],
    config_path: Annotated[
        Path | None, typer.Option("--config", "-c", help="Path to a YAML/JSON config file.")
    ] = None,
    strategy: Annotated[
        str | None,
        typer.Option("--strategy", "-s", help=f"One of: {', '.join(available_strategies())}"),
    ] = None,
    chunk_size: Annotated[
        int | None, typer.Option("--chunk-size", help="Target chunk size.")
    ] = None,
    min_size: Annotated[int | None, typer.Option("--min-size", help="Minimum chunk size.")] = None,
    max_size: Annotated[int | None, typer.Option("--max-size", help="Maximum chunk size.")] = None,
    overlap: Annotated[float | None, typer.Option("--overlap", help="Chunk overlap.")] = None,
    unit: Annotated[
        str | None, typer.Option("--unit", "-u", help="characters | words | tokens")
    ] = None,
    tokenizer: Annotated[
        str | None, typer.Option("--tokenizer", help="heuristic | tiktoken:<encoding>")
    ] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output file or directory.")
    ] = None,
    output_format: Annotated[
        str | None, typer.Option("--format", "-f", help=f"One of: {', '.join(available_formats())}")
    ] = None,
    no_recursive: Annotated[
        bool, typer.Option("--no-recursive", help="Do not walk subdirectories.")
    ] = False,
    no_dedup: Annotated[bool, typer.Option("--no-dedup", help="Disable deduplication.")] = False,
    no_clean: Annotated[bool, typer.Option("--no-clean", help="Disable text cleaning.")] = False,
    no_context: Annotated[
        bool, typer.Option("--no-context", help="Disable context enrichment.")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Process without writing files.")
    ] = False,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Only print the output paths.")
    ] = False,
    show_chunks: Annotated[
        int, typer.Option("--show", help="Preview N chunks after processing.")
    ] = 0,
) -> None:
    """Chunk documents and write a RAG-ready dataset."""
    try:
        config = _load_config(
            config_path,
            strategy=strategy,
            chunk_size=chunk_size,
            min_size=min_size,
            max_size=max_size,
            overlap=overlap,
            unit=unit,
            output=output,
            output_format=output_format,
            no_dedup=no_dedup,
            no_clean=no_clean,
            no_context=no_context,
            tokenizer=tokenizer,
            reference=inputs[0] if inputs else None,
        )
        progress = render.RichProgress(enabled=not quiet)
        pipeline = Pipeline(config, progress=progress)
        result = pipeline.run(inputs, recursive=not no_recursive, write=not dry_run)
    except RagForgeError as exc:
        _fail(exc)
        return

    if quiet:
        for path in result.outputs:
            render.console.print(path)
    else:
        render.print_result_summary(result)
        if show_chunks:
            render.print_chunk_table(result.chunks, limit=show_chunks)
    if result.failed:
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# inspect
# ----------------------------------------------------------------------
@app.command()
def inspect(
    target: Annotated[Path, typer.Argument(help="A source document or an existing dataset file.")],
    chunk: Annotated[
        str | None, typer.Option("--chunk", help="Show one chunk by id or index.")
    ] = None,
    search: Annotated[
        str | None, typer.Option("--search", help="Filter chunks containing this text.")
    ] = None,
    section: Annotated[
        str | None, typer.Option("--section", help="Filter chunks by heading path substring.")
    ] = None,
    role: Annotated[
        str | None,
        typer.Option("--role", help="Filter by semantic role (knowledge, document_meta, ...)."),
    ] = None,
    knowledge_only: Annotated[
        bool, typer.Option("--knowledge-only", help="Hide metadata and navigation chunks.")
    ] = False,
    flagged: Annotated[
        bool, typer.Option("--flagged", help="Only show chunks with warnings.")
    ] = False,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Maximum rows to display.")] = 20,
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    strategy: Annotated[str | None, typer.Option("--strategy", "-s")] = None,
    chunk_size: Annotated[int | None, typer.Option("--chunk-size")] = None,
    overlap: Annotated[float | None, typer.Option("--overlap")] = None,
    unit: Annotated[str | None, typer.Option("--unit", "-u")] = None,
) -> None:
    """Browse chunks of a document or an exported dataset."""
    try:
        chunks = _load_chunks(
            target,
            config_path=config_path,
            strategy=strategy,
            chunk_size=chunk_size,
            overlap=overlap,
            unit=unit,
        )
    except RagForgeError as exc:
        _fail(exc)
        return

    if search:
        needle = search.casefold()
        chunks = [c for c in chunks if needle in c.content.casefold()]
    if section:
        needle = section.casefold()
        chunks = [c for c in chunks if needle in " > ".join(c.metadata.heading_path).casefold()]
    if role:
        chunks = [c for c in chunks if c.metadata.semantic_role == role]
    if knowledge_only:
        chunks = [c for c in chunks if c.is_knowledge]
    if flagged:
        chunks = [c for c in chunks if c.quality and c.quality.flags]

    if chunk is not None:
        selected = _find_chunk(chunks, chunk)
        if selected is None:
            render.print_error(f"No chunk matching '{chunk}'.")
            raise typer.Exit(code=1)
        render.print_chunk_detail(selected)
        return

    if not chunks:
        render.console.print("[yellow]No chunks matched the given filters.[/yellow]")
        return
    render.print_chunk_table(chunks, limit=limit)


# ----------------------------------------------------------------------
# stats
# ----------------------------------------------------------------------
@app.command()
def stats(
    target: Annotated[Path, typer.Argument(help="Source document/directory or dataset file.")],
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    strategy: Annotated[str | None, typer.Option("--strategy", "-s")] = None,
    chunk_size: Annotated[int | None, typer.Option("--chunk-size")] = None,
    unit: Annotated[str | None, typer.Option("--unit", "-u")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
    save: Annotated[Path | None, typer.Option("--save", help="Write statistics.json here.")] = None,
) -> None:
    """Show chunk statistics and distributions."""
    try:
        config = _load_config(
            config_path, strategy=strategy, chunk_size=chunk_size, unit=unit, reference=target
        )
        chunks, coverage = _load_chunks(target, config=config, want_coverage=True)
    except RagForgeError as exc:
        _fail(exc)
        return

    statistics = Statistics.from_chunks(
        chunks,
        project=config.project.name,
        strategy=config.chunking.strategy_name,
        unit=config.chunking.unit.value,
    )
    statistics.coverage = coverage
    if as_json:
        render.console.print_json(json.dumps(statistics.model_dump(mode="json")))
    else:
        render.print_statistics(statistics)
        render.print_histogram(statistics)
        render.print_breakdown("Chunks by document", statistics.chunks_by_document)
        render.print_breakdown("Chunks by section", statistics.chunks_by_section)
        render.print_breakdown("Chunks by content type", statistics.chunks_by_content_type)
        render.print_breakdown("Chunks by semantic role", statistics.chunks_by_role)
        if statistics.retrieval_terms:
            render.print_breakdown("Retrieval terms harvested", statistics.retrieval_terms)
        if statistics.flag_counts:
            render.print_breakdown("Quality flags", statistics.flag_counts)
    if save:
        write_statistics(statistics, save)
        render.console.print(f"[green]Statistics written to {save}[/green]")


# ----------------------------------------------------------------------
# validate
# ----------------------------------------------------------------------
@app.command()
def validate(
    target: Annotated[Path, typer.Argument(help="Dataset file or source document to validate.")],
    config_path: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as failures.")] = False,
) -> None:
    """Validate a chunk dataset for structural problems."""
    try:
        config = _load_config(config_path, reference=target)
        chunks, coverage = _load_chunks(target, config=config, want_coverage=True)
    except RagForgeError as exc:
        _fail(exc)
        return

    report = DatasetValidator(config).validate(chunks)
    render.print_validation(report)
    if coverage:
        render.print_coverage(coverage)
    if report.errors or (strict and report.warnings):
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# convert / export
# ----------------------------------------------------------------------
@app.command()
def convert(
    dataset: Annotated[Path, typer.Argument(help="Existing .jsonl or .json dataset.")],
    output: Annotated[Path, typer.Argument(help="Destination file.")],
    output_format: Annotated[
        str | None, typer.Option("--format", "-f", help=f"One of: {', '.join(available_formats())}")
    ] = None,
) -> None:
    """Convert an exported dataset between formats."""
    try:
        chunks = _read_dataset(dataset)
        fmt = output_format or (_format_from_suffix(output.suffix) or OutputFormat.JSONL).value
        exporter = get_exporter(fmt)
        path = exporter.write(chunks, output)
    except RagForgeError as exc:
        _fail(exc)
        return
    render.console.print(f"[green]Wrote {len(chunks):,} chunks to {path}[/green]")


# ----------------------------------------------------------------------
# init
# ----------------------------------------------------------------------
@app.command()
def init(
    path: Annotated[Path, typer.Argument(help="Where to write the config file.")] = Path(
        "ragforge.yaml"
    ),
    force: Annotated[bool, typer.Option("--force", help="Overwrite an existing file.")] = False,
) -> None:
    """Write a commented starter configuration file."""
    if path.exists() and not force:
        render.print_error(f"{path} already exists.", "Pass --force to overwrite it.")
        raise typer.Exit(code=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_STARTER_CONFIG, encoding="utf-8")
    render.console.print(f"[green]Created {path}[/green]")


# ----------------------------------------------------------------------
# formats
# ----------------------------------------------------------------------
@app.command()
def formats() -> None:
    """List supported input and output formats."""
    render.console.print(
        "[bold cyan]Input formats:[/bold cyan] " + ", ".join(supported_extensions())
    )
    render.console.print("[bold cyan]Output formats:[/bold cyan] " + ", ".join(available_formats()))
    render.console.print("[bold cyan]Strategies:[/bold cyan] " + ", ".join(available_strategies()))


# ----------------------------------------------------------------------
# serve
# ----------------------------------------------------------------------
@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", help="Bind address.")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", "-p", help="Port to listen on.")] = 8000,
    reload: Annotated[bool, typer.Option("--reload", help="Enable auto-reload.")] = False,
) -> None:
    """Start the REST API and the local inspection web UI."""
    try:
        import uvicorn
    except ImportError:
        render.print_error(
            "The web interface requires FastAPI and uvicorn.",
            "Install them with: pip install 'rag-chunkforge[api]'",
        )
        raise typer.Exit(code=1) from None

    render.console.print(f"[bold green]RAG ChunkForge UI:[/bold green] http://{host}:{port}/")
    render.console.print(
        f"[bold green]API docs:[/bold green]           http://{host}:{port}/docs\n"
    )
    uvicorn.run("ragforge.api.app:app", host=host, port=port, reload=reload)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _load_chunks(
    target: Path,
    *,
    config: ForgeConfig | None = None,
    config_path: Path | None = None,
    strategy: str | None = None,
    chunk_size: int | None = None,
    overlap: float | None = None,
    unit: str | None = None,
    want_coverage: bool = False,
) -> Any:
    """Load chunks either from an exported dataset or by processing sources.

    With ``want_coverage`` the return value is ``(chunks, coverage)``; coverage
    is empty for pre-exported datasets, where the source is no longer present.
    """
    if target.is_file() and (
        target.suffix.lower() in {".jsonl", ".ndjson"}
        or (target.suffix.lower() == ".json" and _looks_like_dataset(target))
    ):
        chunks = _read_dataset(target)
        return (chunks, {}) if want_coverage else chunks

    cfg = config or _load_config(
        config_path,
        strategy=strategy,
        chunk_size=chunk_size,
        overlap=overlap,
        unit=unit,
        reference=target,
    )
    pipeline = Pipeline(cfg)
    result: ForgeResult = pipeline.run(target, write=False)
    if result.failed and not result.chunks:
        raise InputError(result.failed[0].error or "Processing failed.")
    if want_coverage:
        return result.chunks, result.statistics.coverage
    return result.chunks


def _looks_like_dataset(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8") as handle:
            head = handle.read(4096)
    except OSError:
        return False
    return '"documents"' in head and '"content"' in head


def _read_dataset(path: Path) -> list[Chunk]:
    from ragforge.errors import ParseError

    if not path.exists():
        raise InputError(f"Dataset not found: {path}")
    records: list[dict] = []
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        for number, line in enumerate(text.split("\n"), start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ParseError(str(path), f"invalid JSON on line {number}: {exc.msg}") from exc
    else:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ParseError(str(path), f"invalid JSON: {exc.msg}") from exc
        records = payload.get("documents", payload) if isinstance(payload, dict) else payload

    chunks: list[Chunk] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        quality = record.get("quality")
        chunks.append(
            Chunk(
                id=str(record.get("id", "")),
                content=str(record.get("content", "")),
                metadata=ChunkMetadata(**(record.get("metadata") or {})),
                quality=ChunkQuality(**quality) if isinstance(quality, dict) else None,
                context_prefix=record.get("context_prefix"),
                embedding=record.get("embedding"),
            )
        )
    return chunks


def _find_chunk(chunks: list[Chunk], selector: str) -> Chunk | None:
    for chunk in chunks:
        if chunk.id == selector:
            return chunk
    if selector.isdigit():
        index = int(selector)
        for chunk in chunks:
            if chunk.metadata.chunk_index == index:
                return chunk
        if 0 <= index < len(chunks):
            return chunks[index]
    lowered = selector.casefold()
    for chunk in chunks:
        if lowered in chunk.id.casefold():
            return chunk
    return None


_STARTER_CONFIG = """\
# RAG ChunkForge configuration
project:
  name: my-rag-dataset
  description: ""

chunking:
  strategy: semantic       # semantic | structural | recursive | sentence | code | auto
  target_size: 500
  min_size: 100
  max_size: 800
  overlap: 75
  unit: tokens             # characters | words | tokens
  overlap_unit: same       # same | percentage | characters | words | tokens
  tokenizer: heuristic     # heuristic | tiktoken:cl100k_base
  respect_sentence_boundaries: true
  keep_code_blocks_intact: true
  keep_tables_intact: true
  merge_small_chunks: true
  split_on_headings: true

semantics:
  enabled: true
  # Keyword / tag / alias / entity sections become structured metadata fields
  # instead of ordinary knowledge chunks. Nothing is discarded.
  separate_retrieval_metadata: true
  keep_document_metadata: true    # front-matter kept, but role-marked
  min_terms: 5
  max_terms_per_field: 256
  include_terms_in_embedding_text: false

cleaning:
  enabled: true
  normalize_whitespace: true
  collapse_blank_lines: true
  normalize_unicode: true
  normalize_quotes: false
  remove_headers: false
  remove_footers: false
  remove_navigation: false
  preserve_code_blocks: true

deduplication:
  enabled: true
  similarity_threshold: 0.92
  method: minhash          # exact | minhash | off
  action: flag             # flag | drop
  scope: global            # global | document

context:
  include_heading_path: true
  include_source: true
  include_title: true
  include_context_prefix: true
  prepend_context_to_content: false
  include_neighbors: true
  include_parents: true

quality:
  enabled: true
  drop_low_quality: false
  min_quality_score: 0.0
  validate_information_loss: true

embeddings:
  enabled: false
  provider: hash           # hash | sentence-transformers | ollama | openai
  model: ""
  dimensions: 256

output:
  format: jsonl            # jsonl | json | csv | markdown
  path: output
  filename: chunks
  write_statistics: true
  include_quality: true
"""


def run() -> None:
    """Console-script entry point with friendly error handling."""
    try:
        app()
    except RagForgeError as exc:  # pragma: no cover - safety net
        if _DEBUG["enabled"]:
            raise
        render.print_error(str(exc), getattr(exc, "hint", None))
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    run()
