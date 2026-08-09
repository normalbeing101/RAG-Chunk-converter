"""CSV/TSV parser.

Two rendering modes:

``records`` (default)
    Each row becomes a small labelled section - ideal for RAG because a
    retrieved chunk reads as ``Column: value`` pairs instead of a bare row.

``table``
    The whole sheet is rendered as one Markdown table (kept intact by the
    table-aware chunker when it fits).
"""

from __future__ import annotations

import csv
import io
from typing import ClassVar

from ragforge.errors import ParseError
from ragforge.models.document import Document
from ragforge.parsers.base import Parser, register_parser

_MAX_TABLE_ROWS = 200


class CsvParser(Parser):
    name: ClassVar[str] = "csv"
    extensions: ClassVar[tuple[str, ...]] = (".csv", ".tsv")

    def __init__(self, mode: str = "records") -> None:
        self.mode = mode

    def parse_text(self, text: str, *, source: str = "", title: str = "") -> Document:
        if not text.strip():
            return self.build_document(
                "", source=source, title=title or "Empty CSV", metadata={"format": "csv", "rows": 0}
            )
        dialect = _sniff(text, source)
        reader = csv.reader(io.StringIO(text, newline=""), dialect)
        try:
            rows = [row for row in reader if any(cell.strip() for cell in row)]
        except csv.Error as exc:
            raise ParseError(source or "CSV input", f"malformed CSV ({exc})") from exc
        if not rows:
            return self.build_document(
                "", source=source, title=title or "Empty CSV", metadata={"format": "csv", "rows": 0}
            )

        header = [cell.strip() or f"column_{i + 1}" for i, cell in enumerate(rows[0])]
        body = rows[1:]
        doc_title = title or "CSV dataset"

        if self.mode == "table" or len(body) <= 1:
            content = _render_table(header, body)
        else:
            content = _render_records(header, body)

        return self.build_document(
            content,
            source=source,
            title=doc_title,
            metadata={
                "format": "csv",
                "rows": len(body),
                "columns": header,
                "render_mode": self.mode,
            },
        )


def _sniff(text: str, source: str) -> type[csv.Dialect] | csv.Dialect:
    sample = text[:8192]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.excel_tab if "\t" in sample.split("\n")[0] else csv.excel


def _render_records(header: list[str], rows: list[list[str]]) -> str:
    lines: list[str] = []
    for index, row in enumerate(rows, start=1):
        label = row[0].strip() if row and row[0].strip() else f"Row {index}"
        lines.append(f"## {label}")
        lines.append("")
        for column, value in zip(header, row, strict=False):
            cleaned = value.strip()
            if cleaned:
                lines.append(f"- {column}: {cleaned}")
        lines.append("")
    return "\n".join(lines).strip()


def _render_table(header: list[str], rows: list[list[str]]) -> str:
    width = len(header)
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
    for row in rows[:_MAX_TABLE_ROWS]:
        cells = [*row, *([""] * (width - len(row)))][:width]
        lines.append("| " + " | ".join(cell.strip().replace("|", "\\|") for cell in cells) + " |")
    if len(rows) > _MAX_TABLE_ROWS:
        lines.append("")
        lines.append(f"_({len(rows) - _MAX_TABLE_ROWS} additional rows omitted from table view)_")
    return "\n".join(lines)


register_parser(CsvParser())
