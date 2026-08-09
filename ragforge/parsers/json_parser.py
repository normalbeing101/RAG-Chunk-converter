"""JSON and JSONL parser.

Structured data is flattened into readable Markdown so that chunking retains
key paths as context. Records in an array become sections; nested objects
become nested headings up to a configurable depth.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from ragforge.errors import ParseError
from ragforge.models.document import Document
from ragforge.parsers.base import Parser, register_parser

_MAX_HEADING_DEPTH = 5


class JsonParser(Parser):
    name: ClassVar[str] = "json"
    extensions: ClassVar[tuple[str, ...]] = (".json", ".jsonl", ".ndjson")

    def parse_text(self, text: str, *, source: str = "", title: str = "") -> Document:
        data, is_lines = _load(text, source)
        lines: list[str] = []
        doc_title = title or _guess_title(data) or "JSON document"

        if isinstance(data, list):
            for index, item in enumerate(data, start=1):
                heading = _record_heading(item, index)
                lines.append(f"## {heading}")
                lines.append("")
                lines.extend(_render(item, depth=2))
                lines.append("")
        else:
            lines.extend(_render(data, depth=1))

        content = "\n".join(lines).strip()
        return self.build_document(
            content,
            source=source,
            title=doc_title,
            metadata={
                "format": "jsonl" if is_lines else "json",
                "records": len(data) if isinstance(data, list) else 1,
            },
        )


def _load(text: str, source: str) -> tuple[Any, bool]:
    stripped = text.strip()
    if not stripped:
        return {}, False
    try:
        return json.loads(stripped), False
    except json.JSONDecodeError as first_error:
        records: list[Any] = []
        for line_number, line in enumerate(stripped.split("\n"), start=1):
            candidate = line.strip()
            if not candidate:
                continue
            try:
                records.append(json.loads(candidate))
            except json.JSONDecodeError as exc:
                raise ParseError(
                    source or "JSON input",
                    f"invalid JSON at line {line_number}: {exc.msg}",
                    hint=f"Top-level parse also failed: {first_error.msg}",
                ) from exc
        if not records:
            raise ParseError(
                source or "JSON input", f"invalid JSON: {first_error.msg}"
            ) from first_error
        return records, True


def _guess_title(data: Any) -> str:
    if isinstance(data, dict):
        for key in ("title", "name", "id", "heading"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _record_heading(item: Any, index: int) -> str:
    if isinstance(item, dict):
        for key in ("title", "name", "heading", "id", "slug"):
            value = item.get(key)
            if isinstance(value, str | int) and str(value).strip():
                return str(value).strip()
    return f"Record {index}"


def _render(value: Any, *, depth: int, prefix: str = "") -> list[str]:
    lines: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            label = str(key).replace("_", " ").strip()
            if isinstance(item, dict) and item:
                if depth <= _MAX_HEADING_DEPTH:
                    lines.append(f"{'#' * min(depth + 1, 6)} {label}")
                    lines.append("")
                    lines.extend(_render(item, depth=depth + 1))
                    lines.append("")
                else:
                    lines.append(f"{prefix}- {label}: {json.dumps(item, ensure_ascii=False)}")
            elif isinstance(item, list):
                lines.extend(_render_list(label, item, depth=depth, prefix=prefix))
            else:
                lines.append(f"{prefix}- {label}: {_scalar(item)}")
        return lines
    if isinstance(value, list):
        lines.extend(_render_list("items", value, depth=depth, prefix=prefix))
        return lines
    lines.append(f"{prefix}{_scalar(value)}")
    return lines


def _render_list(label: str, items: list[Any], *, depth: int, prefix: str) -> list[str]:
    lines: list[str] = []
    if not items:
        lines.append(f"{prefix}- {label}: (empty)")
        return lines
    if all(not isinstance(i, dict | list) for i in items):
        lines.append(f"{prefix}- {label}: {', '.join(_scalar(i) for i in items)}")
        return lines
    if depth <= _MAX_HEADING_DEPTH:
        lines.append(f"{'#' * min(depth + 1, 6)} {label}")
        lines.append("")
    for index, item in enumerate(items, start=1):
        if isinstance(item, dict):
            lines.append(f"{prefix}- {_record_heading(item, index)}")
            lines.extend(_render(item, depth=depth + 1, prefix=prefix + "  "))
        else:
            lines.append(f"{prefix}- {_scalar(item)}")
    lines.append("")
    return lines


def _scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value.strip()
    return json.dumps(value, ensure_ascii=False)


register_parser(JsonParser())
