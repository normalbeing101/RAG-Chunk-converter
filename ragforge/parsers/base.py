"""Parser interface and registry.

Adding a new format means writing a :class:`Parser` subclass and registering it
with :func:`register_parser`. Nothing else in the pipeline needs to change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from ragforge.errors import ParseError, UnsupportedFormatError
from ragforge.models.document import Document
from ragforge.utils.ids import stable_id

_MAX_PROBE_BYTES = 8192


class Parser(ABC):
    """Converts a source file (or raw text) into a :class:`Document`."""

    name: ClassVar[str] = "base"
    extensions: ClassVar[tuple[str, ...]] = ()
    authoritative_title: ClassVar[bool] = False
    """True when the format can name itself (frontmatter, ``<title>``, ``# H1``).

    For such formats the extracted title wins over the filename; otherwise the
    filename is the more reliable label.
    """

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    @abstractmethod
    def parse_text(self, text: str, *, source: str = "", title: str = "") -> Document:
        """Parse in-memory text into a document."""

    def parse(self, path: Path) -> Document:
        """Parse a file from disk.

        Formats that can name themselves keep the title they extracted;
        everything else falls back to a title derived from the filename.
        """
        text = read_text_file(path)
        fallback = default_title(path)
        if not self.authoritative_title:
            return self.parse_text(text, source=str(path), title=fallback)
        document = self.parse_text(text, source=str(path))
        if not document.title or document.title == "Untitled":
            return document.model_copy(update={"title": fallback})
        return document

    # Helper used by subclasses to build documents consistently.
    def build_document(
        self,
        content: str,
        *,
        source: str,
        title: str,
        metadata: dict | None = None,
    ) -> Document:
        meta = {"parser": self.name, "format": self.name}
        if metadata:
            meta.update(metadata)
        return Document(
            id=stable_id("doc", source or title or content[:256]),
            title=title,
            source=source,
            content=content,
            metadata=meta,
        )


_REGISTRY: list[Parser] = []


def register_parser(parser: Parser) -> Parser:
    """Register a parser instance (last registered wins for ties)."""
    _REGISTRY.insert(0, parser)
    return parser


def registered_parsers() -> list[Parser]:
    return list(_REGISTRY)


def supported_extensions() -> list[str]:
    seen: list[str] = []
    for parser in _REGISTRY:
        for ext in parser.extensions:
            if ext not in seen:
                seen.append(ext)
    return sorted(seen)


def get_parser(path: Path) -> Parser:
    """Find a parser able to handle ``path``."""
    for parser in _REGISTRY:
        if parser.supports(path):
            return parser
    raise UnsupportedFormatError(path.suffix.lower(), supported_extensions())


def get_parser_by_name(name: str) -> Parser | None:
    for parser in _REGISTRY:
        if parser.name == name:
            return parser
    return None


def read_text_file(path: Path) -> str:
    """Read a text file, tolerating common encodings and BOMs."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise ParseError(str(path), "file not found") from exc
    except OSError as exc:
        raise ParseError(str(path), f"cannot read file ({exc.strerror or exc})") from exc

    if b"\x00" in raw[:_MAX_PROBE_BYTES]:
        raise ParseError(
            str(path),
            "file appears to be binary",
            hint="Only text-based formats are supported for this parser.",
        )
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def default_title(path: Path) -> str:
    """Human-friendly title derived from a filename."""
    stem = path.stem.replace("_", " ").replace("-", " ").strip()
    if not stem:
        return path.name
    return " ".join(word if word.isupper() else word.capitalize() for word in stem.split())
