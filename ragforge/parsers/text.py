"""Plain text parser."""

from __future__ import annotations

from typing import ClassVar

from ragforge.models.document import Document
from ragforge.parsers.base import Parser, register_parser


class TextParser(Parser):
    """Handles ``.txt`` and unknown-but-textual files."""

    name: ClassVar[str] = "text"
    extensions: ClassVar[tuple[str, ...]] = (".txt", ".text", ".log", ".rst")

    def parse_text(self, text: str, *, source: str = "", title: str = "") -> Document:
        content = text.replace("\r\n", "\n").replace("\r", "\n")
        derived_title = title or _first_line_title(content)
        return self.build_document(
            content,
            source=source,
            title=derived_title,
            metadata={"format": "text"},
        )


def _first_line_title(content: str) -> str:
    for line in content.split("\n", 8):
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return "Untitled"


register_parser(TextParser())
