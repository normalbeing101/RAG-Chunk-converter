"""Rich rendering helpers for the CLI."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from ragforge.models.chunk import Chunk
from ragforge.models.result import ForgeResult, Statistics
from ragforge.quality.validator import ValidationReport
from ragforge.utils.text import truncate

console = Console()
error_console = Console(stderr=True)


def supports_unicode(encoding: str | None = None) -> bool:
    """Whether ``encoding`` can render box-drawing characters.

    Legacy Windows consoles default to cp1252 and raise ``UnicodeEncodeError``
    on characters such as U+2588, so bar charts fall back to ASCII there.
    """
    if encoding is None:
        encoding = getattr(console.file, "encoding", None) or "utf-8"
    try:
        "\u2588\u2192".encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


_UNICODE = supports_unicode()
BAR_CHAR = "\u2588" if _UNICODE else "#"
ARROW = "\u2192" if _UNICODE else "->"


class RichProgress:
    """ProgressReporter backed by a Rich progress bar."""

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self._progress: Progress | None = None
        self._task: TaskID | None = None

    def start(self, total: int, description: str) -> None:
        if not self.enabled:
            return
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TextColumn("[dim]{task.fields[detail]}"),
            console=console,
            transient=True,
        )
        self._progress.start()
        self._task = self._progress.add_task(description, total=max(total, 1), detail="")

    def advance(self, amount: int = 1, *, detail: str | None = None) -> None:
        if self._progress is not None and self._task is not None:
            self._progress.update(self._task, advance=amount, detail=detail or "")

    def finish(self) -> None:
        if self._progress is not None:
            self._progress.stop()
            self._progress = None
            self._task = None


def print_error(message: str, hint: str | None = None) -> None:
    error_console.print(f"[bold red]Error:[/bold red] {message}")
    if hint:
        error_console.print(f"[yellow]Hint:[/yellow] {hint}")


def print_statistics(stats: Statistics) -> None:
    table = Table(title="Dataset statistics", show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column()

    rows = [
        ("Project", stats.project or "-"),
        ("Strategy", f"{stats.strategy} ({stats.unit})"),
        ("Documents", f"{stats.documents:,}"),
        ("Failed documents", f"{stats.failed_documents:,}"),
        ("Original characters", f"{stats.original_characters:,}"),
        ("Original tokens", f"{stats.original_tokens:,}"),
        ("Generated chunks", f"{stats.total_chunks:,}"),
        ("Average size", f"{stats.average_size:,.0f} {stats.unit}"),
        ("Median size", f"{stats.median_size:,.0f} {stats.unit}"),
        ("Min / Max size", f"{stats.min_size:,} / {stats.max_size:,}"),
        ("P95 size", f"{stats.p95_size:,.0f}"),
        ("Average quality", f"{stats.average_quality:.2f}"),
        ("Duplicates", f"{stats.duplicates:,}"),
        ("Warnings", f"{stats.warnings:,}"),
        ("Elapsed", f"{stats.elapsed_seconds:.2f}s"),
    ]
    for label, value in rows:
        table.add_row(label, str(value))
    console.print(table)


def print_histogram(stats: Statistics, *, width: int = 40) -> None:
    if not stats.size_histogram:
        return
    peak = max(bucket["count"] for bucket in stats.size_histogram) or 1
    table = Table(title=f"Chunk size distribution ({stats.unit})", box=None, padding=(0, 1))
    table.add_column("Range", style="cyan", justify="right")
    table.add_column("Count", justify="right")
    table.add_column("")
    for bucket in stats.size_histogram:
        bar = BAR_CHAR * max(1, int(bucket["count"] / peak * width)) if bucket["count"] else ""
        table.add_row(
            f"{bucket['start']:.0f}-{bucket['end']:.0f}",
            f"{bucket['count']:,}",
            Text(bar, style="green"),
        )
    console.print(table)


def print_breakdown(title: str, data: dict[str, int], *, limit: int = 15) -> None:
    if not data:
        return
    table = Table(title=title, box=None, padding=(0, 2))
    table.add_column("Name", style="cyan", overflow="fold")
    table.add_column("Chunks", justify="right")
    for name, count in sorted(data.items(), key=lambda kv: -kv[1])[:limit]:
        table.add_row(truncate(name, 60), f"{count:,}")
    if len(data) > limit:
        table.add_row(f"[dim]... {len(data) - limit} more[/dim]", "")
    console.print(table)


def print_chunk_table(chunks: list[Chunk], *, limit: int = 20) -> None:
    table = Table(title=f"Chunks ({len(chunks):,})", box=None, padding=(0, 1))
    table.add_column("#", justify="right", style="dim")
    table.add_column("ID", style="cyan", overflow="fold")
    table.add_column("Section", overflow="fold")
    table.add_column("Type")
    table.add_column("Size", justify="right")
    table.add_column("Q", justify="right")
    table.add_column("Preview", overflow="fold")

    for chunk in chunks[:limit]:
        meta = chunk.metadata
        quality = f"{chunk.quality.quality_score:.2f}" if chunk.quality else "-"
        style = ""
        if chunk.quality and chunk.quality.flags:
            style = "yellow"
        table.add_row(
            str(meta.chunk_index),
            chunk.id,
            truncate(" > ".join(meta.heading_path) or "-", 34),
            meta.content_type,
            str(meta.size),
            quality,
            truncate(chunk.content, 60),
            style=style,
        )
    console.print(table)
    if len(chunks) > limit:
        console.print(f"[dim]... {len(chunks) - limit:,} more chunks[/dim]")


def print_chunk_detail(chunk: Chunk) -> None:
    meta = chunk.metadata
    header = Table.grid(padding=(0, 2))
    header.add_column(style="bold cyan")
    header.add_column()
    header.add_row("ID", chunk.id)
    header.add_row("Document", f"{meta.title} ({meta.document_id})")
    header.add_row("Source", meta.source or "-")
    header.add_row("Heading path", " > ".join(meta.heading_path) or "-")
    header.add_row("Type", meta.content_type + (f" / {meta.language}" if meta.language else ""))
    header.add_row("Index", f"{meta.chunk_index + 1} / {meta.total_chunks}")
    header.add_row(
        "Size", f"{meta.size} {meta.unit} | {meta.char_count} chars | {meta.word_count} words"
    )
    header.add_row("Neighbors", f"{meta.previous_chunk or '-'}  {ARROW}  {meta.next_chunk or '-'}")
    header.add_row("Parent", meta.parent_id or "-")
    if chunk.quality:
        flags = ", ".join(f.value for f in chunk.quality.flags) or "none"
        header.add_row(
            "Quality",
            f"{chunk.quality.quality_score:.2f} "
            f"(len {chunk.quality.length_score:.2f}, coh {chunk.quality.coherence_score:.2f}, "
            f"ctx {chunk.quality.context_score:.2f}) flags: {flags}",
        )
    if meta.duplicate_of:
        header.add_row("Duplicate of", f"{meta.duplicate_of} ({meta.similarity})")
    console.print(Panel(header, title=f"[bold]{chunk.id}", border_style="blue"))
    console.print(Panel(chunk.content, title="Content", border_style="dim"))


def print_validation(report: ValidationReport) -> None:
    if report.ok and not report.warnings:
        console.print(
            f"[bold green]OK[/bold green] {report.checked:,} chunks validated, no issues."
        )
        return
    table = Table(title="Validation issues", box=None, padding=(0, 2))
    table.add_column("Level")
    table.add_column("Code", style="cyan")
    table.add_column("Chunk", style="dim", overflow="fold")
    table.add_column("Message", overflow="fold")
    for issue in report.issues[:100]:
        color = "red" if issue.level == "error" else "yellow"
        table.add_row(
            f"[{color}]{issue.level}[/{color}]", issue.code, issue.chunk_id or "-", issue.message
        )
    console.print(table)
    if len(report.issues) > 100:
        console.print(f"[dim]... {len(report.issues) - 100} more issues[/dim]")
    console.print(
        f"\n[bold]{len(report.errors)} error(s), {len(report.warnings)} warning(s)"
        f" across {report.checked:,} chunks.[/bold]"
    )


def print_result_summary(result: ForgeResult) -> None:
    print_statistics(result.statistics)
    if result.failed:
        table = Table(title="Failed documents", box=None, padding=(0, 2))
        table.add_column("Source", style="cyan", overflow="fold")
        table.add_column("Error", style="red", overflow="fold")
        for report in result.failed:
            table.add_row(report.source, report.error or "unknown error")
        console.print(table)
    if result.outputs:
        console.print("\n[bold green]Written:[/bold green]")
        for path in result.outputs:
            console.print(f"  {path}")
