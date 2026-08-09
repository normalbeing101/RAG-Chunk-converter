"""PDF parser built on the optional ``pypdf`` dependency.

Beyond raw text extraction the parser:

* joins hyphenated line breaks,
* reflows hard-wrapped lines into paragraphs,
* detects repeated page headers/footers and removes them,
* promotes likely headings (short, title-cased, numbered lines) to Markdown.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, ClassVar

from ragforge.errors import MissingDependencyError, ParseError
from ragforge.models.document import Document
from ragforge.parsers.base import Parser, default_title, register_parser

_HYPHEN_BREAK_RE = re.compile(r"(\w)-\n(\w)")
_NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.{0,90})$")
_PAGE_NUMBER_RE = re.compile(r"^(?:page\s*)?\d+(?:\s*/\s*\d+)?$", re.IGNORECASE)


class PdfParser(Parser):
    name: ClassVar[str] = "pdf"
    extensions: ClassVar[tuple[str, ...]] = (".pdf",)
    authoritative_title: ClassVar[bool] = True

    def parse_text(self, text: str, *, source: str = "", title: str = "") -> Document:
        """Treat already-extracted PDF text as plain text."""
        content = _postprocess_pages([text])
        return self.build_document(
            content,
            source=source,
            title=title or "PDF document",
            metadata={"format": "pdf", "pages": 1},
        )

    def parse(self, path: Path) -> Document:
        try:
            from pypdf import PdfReader
            from pypdf.errors import PdfReadError
        except ImportError as exc:
            raise MissingDependencyError(
                "pypdf", "PDF parsing", extra="rag-chunkforge[pdf]"
            ) from exc

        try:
            reader = PdfReader(str(path))
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception as exc:
                    raise ParseError(
                        str(path),
                        "document is password protected",
                        hint="Decrypt the PDF before processing it.",
                    ) from exc
            pages = [page.extract_text() or "" for page in reader.pages]
            info: dict[str, Any] = dict(reader.metadata or {})
        except ParseError:
            raise
        except PdfReadError as exc:
            raise ParseError(str(path), f"document appears corrupted ({exc})") from exc
        except Exception as exc:
            raise ParseError(str(path), f"could not read PDF ({exc})") from exc

        if not any(page.strip() for page in pages):
            raise ParseError(
                str(path),
                "no extractable text found",
                hint="The PDF may be a scanned image; run OCR first.",
            )

        content = _postprocess_pages(pages)
        meta_title = _clean_metadata_title(str(info.get("/Title", "")) if info else "")
        metadata = {
            "format": "pdf",
            "pages": len(pages),
            "pdf_author": str(info.get("/Author", "")).strip() if info else "",
        }
        return self.build_document(
            content,
            source=str(path),
            title=meta_title or default_title(path),
            metadata=metadata,
        )


_PLACEHOLDER_TITLES = {
    "untitled",
    "untitled document",
    "document",
    "microsoft word",
    "pdf document",
    "no title",
    "unknown",
    "-",
    "title",
}


def _clean_metadata_title(value: str) -> str:
    """Reject the placeholder titles that PDF producers routinely embed."""
    title = value.strip()
    if not title or title.casefold() in _PLACEHOLDER_TITLES:
        return ""
    # "manual.docx" style titles are just the source filename.
    if title.casefold().endswith((".doc", ".docx", ".pdf", ".tex", ".odt")):
        return ""
    return title


def _postprocess_pages(pages: list[str]) -> str:
    cleaned_pages = [p.replace("\r\n", "\n").replace("\r", "\n") for p in pages]
    boilerplate = _detect_boilerplate(cleaned_pages)
    blocks: list[str] = []
    for page in cleaned_pages:
        page = _HYPHEN_BREAK_RE.sub(r"\1\2", page)
        lines = [
            line.rstrip()
            for line in page.split("\n")
            if line.strip()
            and line.strip() not in boilerplate
            and not _PAGE_NUMBER_RE.match(line.strip())
        ]
        if lines:
            blocks.append(_reflow(lines))
    return "\n\n".join(block for block in blocks if block.strip()).strip()


def _detect_boilerplate(pages: list[str]) -> set[str]:
    if len(pages) < 3:
        return set()
    counter: Counter[str] = Counter()
    for page in pages:
        lines = [line.strip() for line in page.split("\n") if line.strip()]
        for line in lines[:2] + lines[-2:]:
            if 3 <= len(line) <= 120:
                counter[line] += 1
    threshold = max(3, int(len(pages) * 0.6))
    return {line for line, count in counter.items() if count >= threshold}


def _reflow(lines: list[str]) -> str:
    """Merge hard-wrapped lines into paragraphs and promote headings."""
    out: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            out.append(" ".join(buffer).strip())
            buffer.clear()

    for line in lines:
        stripped = line.strip()
        heading = _as_heading(stripped)
        if heading:
            flush()
            out.append(heading)
            continue
        if re.match(r"^\s*(?:[-*\u2022]|\d+[.)])\s+", line):
            flush()
            out.append(stripped)
            continue
        buffer.append(stripped)
        if stripped.endswith((".", "!", "?", ":")) and len(stripped) < 400:
            flush()
    flush()
    return "\n\n".join(part for part in out if part)


def _as_heading(line: str) -> str | None:
    if len(line) > 100 or line.endswith((".", ",", ";")):
        return None
    match = _NUMBERED_HEADING_RE.match(line)
    if match:
        depth = min(match.group(1).count(".") + 1, 6)
        return f"{'#' * depth} {match.group(1)} {match.group(2).strip()}"
    words = line.split()
    if 1 <= len(words) <= 10 and (line.isupper() or _is_title_case(words)):
        return f"## {line}"
    return None


def _is_title_case(words: list[str]) -> bool:
    significant = [w for w in words if len(w) > 3]
    if len(significant) < 2:
        return False
    return all(w[0].isupper() for w in significant)


register_parser(PdfParser())
