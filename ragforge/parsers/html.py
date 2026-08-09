"""HTML parser.

Uses the standard library ``html.parser`` (no external dependency) to convert
HTML into Markdown while dropping boilerplate such as ``<script>``, ``<style>``,
``<nav>``, ``<header>`` and ``<footer>``.
"""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser as _StdHTMLParser
from typing import Any, ClassVar

from ragforge.models.document import Document
from ragforge.parsers.base import Parser, register_parser

_DROP_TAGS = {"script", "style", "noscript", "template", "svg", "iframe", "form"}
_BOILERPLATE_TAGS = {"nav", "header", "footer", "aside"}
_BLOCK_TAGS = {
    "p",
    "div",
    "section",
    "article",
    "main",
    "ul",
    "ol",
    "table",
    "tr",
    "blockquote",
    "pre",
    "figure",
    "figcaption",
    "br",
    "hr",
}
_HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


class _HtmlToMarkdown(_StdHTMLParser):
    def __init__(self, *, drop_boilerplate: bool = True) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title: str = ""
        self.meta: dict[str, Any] = {}
        self._drop_boilerplate = drop_boilerplate
        self._skip_depth = 0
        self._skip_tag: str | None = None
        self._in_title = False
        self._in_pre = False
        self._pre_lang: str | None = None
        self._list_stack: list[dict[str, Any]] = []
        self._pending_heading: int | None = None
        self._table_row: list[str] = []
        self._table_rows: list[list[str]] = []
        self._in_cell = False
        self._cell_buffer: list[str] = []
        self._in_table = False
        self._header_row_done = False

    # -- helpers ---------------------------------------------------------
    def _emit(self, text: str) -> None:
        if self._skip_depth:
            return
        self.parts.append(text)

    def _newline(self, count: int = 2) -> None:
        if self._skip_depth:
            return
        if self.parts and not self.parts[-1].endswith("\n" * count):
            self.parts.append("\n" * count)

    # -- HTMLParser API --------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrd = {k: (v or "") for k, v in attrs}
        if tag in _DROP_TAGS or (self._drop_boilerplate and tag in _BOILERPLATE_TAGS):
            if self._skip_depth == 0:
                self._skip_tag = tag
            self._skip_depth += 1
            return
        if self._skip_depth:
            return

        if tag == "title":
            self._in_title = True
            return
        if tag == "meta":
            name = (attrd.get("name") or attrd.get("property") or "").lower()
            if name in {"description", "author", "keywords", "og:title", "og:description"}:
                self.meta[name.replace("og:", "")] = attrd.get("content", "")
            return
        if tag in _HEADING_TAGS:
            self._newline()
            self._pending_heading = _HEADING_TAGS[tag]
            self._emit("#" * _HEADING_TAGS[tag] + " ")
            return
        if tag == "pre":
            self._newline()
            self._in_pre = True
            self._emit("```" + (self._pre_lang or "") + "\n")
            return
        if tag == "code" and not self._in_pre:
            lang = _language_from_class(attrd.get("class", ""))
            self._pre_lang = lang
            self._emit("`")
            return
        if tag in {"ul", "ol"}:
            self._newline()
            self._list_stack.append({"ordered": tag == "ol", "index": 0})
            return
        if tag == "li":
            if self._list_stack:
                ctx = self._list_stack[-1]
                ctx["index"] += 1
                indent = "  " * (len(self._list_stack) - 1)
                marker = f"{ctx['index']}." if ctx["ordered"] else "-"
                self._emit(f"\n{indent}{marker} ")
            return
        if tag == "table":
            self._in_table = True
            self._table_rows = []
            self._header_row_done = False
            self._newline()
            return
        if tag == "tr" and self._in_table:
            self._table_row = []
            return
        if tag in {"td", "th"} and self._in_table:
            self._in_cell = True
            self._cell_buffer = []
            return
        if tag == "blockquote":
            self._newline()
            self._emit("> ")
            return
        if tag == "br":
            self._emit("\n")
            return
        if tag == "hr":
            self._newline()
            self._emit("---")
            self._newline()
            return
        if tag in {"strong", "b"}:
            self._emit("**")
            return
        if tag in {"em", "i"}:
            self._emit("*")
            return
        if tag == "img":
            alt = attrd.get("alt", "").strip()
            if alt:
                self._emit(f"![{alt}]({attrd.get('src', '')})")
            return
        if tag in _BLOCK_TAGS:
            self._newline()

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth:
            if tag == self._skip_tag:
                self._skip_depth -= 1
                if self._skip_depth == 0:
                    self._skip_tag = None
            return

        if tag == "title":
            self._in_title = False
            return
        if tag in _HEADING_TAGS:
            self._pending_heading = None
            self._newline()
            return
        if tag == "pre":
            self._in_pre = False
            self._emit("\n```")
            self._newline()
            return
        if tag == "code" and not self._in_pre:
            self._emit("`")
            return
        if tag in {"ul", "ol"}:
            if self._list_stack:
                self._list_stack.pop()
            self._newline()
            return
        if tag in {"td", "th"} and self._in_table:
            self._in_cell = False
            self._table_row.append(" ".join("".join(self._cell_buffer).split()))
            self._cell_buffer = []
            return
        if tag == "tr" and self._in_table:
            if self._table_row:
                self._table_rows.append(self._table_row)
            self._table_row = []
            return
        if tag == "table":
            self._in_table = False
            self._emit(_render_table(self._table_rows))
            self._table_rows = []
            self._newline()
            return
        if tag in {"strong", "b"}:
            self._emit("**")
            return
        if tag in {"em", "i"}:
            self._emit("*")
            return
        if tag in _BLOCK_TAGS:
            self._newline()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data.strip()
            return
        if self._in_cell:
            self._cell_buffer.append(data)
            return
        if self._in_pre:
            self._emit(data)
            return
        text = re.sub(r"\s+", " ", data)
        if not text.strip():
            if self.parts and not self.parts[-1].endswith((" ", "\n")):
                self.parts.append(" ")
            return
        self._emit(text)

    def result(self) -> str:
        text = "".join(self.parts)
        text = unescape(text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        return _MULTI_NEWLINE_RE.sub("\n\n", text).strip()


def _render_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    padded = [[*r, *([""] * (width - len(r)))] for r in rows]
    lines = ["| " + " | ".join(padded[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in padded[1:])
    return "\n".join(lines)


def _language_from_class(value: str) -> str:
    for token in value.split():
        if token.startswith(("language-", "lang-")):
            return token.split("-", 1)[1]
    return ""


class HtmlParser(Parser):
    name: ClassVar[str] = "html"
    extensions: ClassVar[tuple[str, ...]] = (".html", ".htm", ".xhtml")
    authoritative_title: ClassVar[bool] = True

    def __init__(self, *, drop_boilerplate: bool = True) -> None:
        self.drop_boilerplate = drop_boilerplate

    def parse_text(self, text: str, *, source: str = "", title: str = "") -> Document:
        converter = _HtmlToMarkdown(drop_boilerplate=self.drop_boilerplate)
        try:
            converter.feed(text)
            converter.close()
        except Exception as exc:  # pragma: no cover - html.parser is lenient
            from ragforge.errors import ParseError

            raise ParseError(source or "HTML input", f"malformed HTML ({exc})") from exc

        content = converter.result()
        metadata: dict[str, Any] = {"format": "html", **converter.meta}
        doc_title = title or converter.title or _first_markdown_heading(content) or "Untitled"
        return self.build_document(content, source=source, title=doc_title, metadata=metadata)


def _first_markdown_heading(text: str) -> str:
    for line in text.split("\n"):
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""


register_parser(HtmlParser())
