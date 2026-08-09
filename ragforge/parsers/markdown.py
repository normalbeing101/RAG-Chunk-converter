"""Markdown parser.

Markdown is the canonical internal flavour: HTML, JSON, CSV and PDF parsers all
normalise into Markdown so that a single structure analyzer can be used.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from ragforge.models.document import Document
from ragforge.parsers.base import Parser, register_parser

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.DOTALL)
_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$", re.MULTILINE)
_SETEXT_H1_RE = re.compile(r"^(?P<text>[^\n]+)\n=={2,}\s*$", re.MULTILINE)
_SETEXT_H2_RE = re.compile(r"^(?P<text>[^\n]+)\n--{2,}\s*$", re.MULTILINE)


class MarkdownParser(Parser):
    name: ClassVar[str] = "markdown"
    extensions: ClassVar[tuple[str, ...]] = (".md", ".markdown", ".mdown", ".mkd", ".mdx")
    authoritative_title: ClassVar[bool] = True

    def parse_text(self, text: str, *, source: str = "", title: str = "") -> Document:
        content = text.replace("\r\n", "\n").replace("\r", "\n")
        metadata: dict[str, Any] = {"format": "markdown"}

        frontmatter, content = _extract_frontmatter(content)
        if frontmatter:
            metadata["frontmatter"] = frontmatter
            for key in ("title", "description", "tags", "author", "date"):
                if key in frontmatter:
                    metadata[key] = frontmatter[key]

        content = _normalize_setext_headings(content)
        doc_title = title or str(frontmatter.get("title", "")) or _first_heading(content)
        return self.build_document(
            content,
            source=source,
            title=doc_title or "Untitled",
            metadata=metadata,
        )


def _extract_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    body = text[match.end() :]
    raw = match.group(1)
    data: dict[str, Any] = {}
    try:
        import yaml

        loaded = yaml.safe_load(raw)
        if isinstance(loaded, dict):
            data = loaded
    except Exception:
        data = _parse_simple_frontmatter(raw)
    return data, body


def _parse_simple_frontmatter(raw: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for line in raw.split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            data[key.strip()] = value.strip().strip("\"'")
    return data


def _normalize_setext_headings(text: str) -> str:
    """Rewrite ``Title\\n=====`` into ATX form so downstream code sees one style."""
    text = _SETEXT_H1_RE.sub(lambda m: f"# {m.group('text').strip()}", text)
    text = _SETEXT_H2_RE.sub(
        lambda m: (
            m.group(0)
            if m.group("text").strip().startswith(("-", "*", "|"))
            else f"## {m.group('text').strip()}"
        ),
        text,
    )
    return text


def _first_heading(text: str) -> str:
    in_code = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            continue
        if in_code:
            continue
        match = _ATX_HEADING_RE.match(line)
        if match:
            return match.group(2).strip()
    return ""


register_parser(MarkdownParser())
