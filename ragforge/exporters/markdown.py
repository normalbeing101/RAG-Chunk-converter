"""Markdown exporter - a human-readable inspection report."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar

from ragforge.errors import ExportError
from ragforge.exporters.base import Exporter, register_exporter
from ragforge.models.chunk import Chunk


@register_exporter
class MarkdownExporter(Exporter):
    name: ClassVar[str] = "markdown"
    extension: ClassVar[str] = ".md"

    def write(self, chunks: Iterable[Chunk], path: Path) -> Path:
        path = self.prepare(path)
        try:
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write("# Chunk inspection report\n\n")
                for chunk in chunks:
                    handle.write(_render(chunk))
        except OSError as exc:
            raise ExportError(f"Failed to write {path}: {exc}") from exc
        return path


def _render(chunk: Chunk) -> str:
    meta = chunk.metadata
    lines = [f"## `{chunk.id}`", ""]
    path = " > ".join(meta.heading_path) if meta.heading_path else "(no section)"
    lines.append(f"- **Document:** {meta.title or meta.document_id}")
    lines.append(f"- **Section:** {path}")
    lines.append(f"- **Source:** {meta.source or 'n/a'}")
    lines.append(
        f"- **Size:** {meta.size} {meta.unit} "
        f"({meta.char_count} chars, {meta.word_count} words, {meta.token_count} tokens)"
    )
    lines.append(f"- **Role:** {meta.semantic_role}")
    lines.append(
        f"- **Type:** {meta.content_type}" + (f" ({meta.language})" if meta.language else "")
    )
    lines.append(f"- **Index:** {meta.chunk_index + 1}/{meta.total_chunks}")
    if meta.previous_chunk or meta.next_chunk:
        lines.append(f"- **Neighbors:** {meta.previous_chunk or '-'} / {meta.next_chunk or '-'}")
    if chunk.quality:
        flags = ", ".join(f.value for f in chunk.quality.flags) or "none"
        lines.append(
            f"- **Quality:** {chunk.quality.quality_score:.2f} "
            f"(retrieval {chunk.quality.retrieval_score:.2f}, flags: {flags})"
        )
    for name in ("tags", "keywords", "aliases", "entities", "related_concepts", "questions"):
        values = getattr(chunk.retrieval, name)
        if values:
            preview = ", ".join(values[:8])
            more = f" _(+{len(values) - 8} more)_" if len(values) > 8 else ""
            lines.append(f"- **{name.replace('_', ' ').title()}:** {preview}{more}")
    if meta.duplicate_of:
        lines.append(f"- **Duplicate of:** `{meta.duplicate_of}` ({meta.similarity})")
    lines.append("")
    lines.append("```text")
    lines.append(chunk.content)
    lines.append("```")
    lines.append("")
    return "\n".join(lines)
