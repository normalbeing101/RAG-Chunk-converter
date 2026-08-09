"""Recursive splitting.

Implements the separator hierarchy

``heading -> paragraph -> line -> sentence -> whitespace -> characters``

and only descends to a finer separator when the current unit still exceeds the
target size. Pieces are then greedily merged back together so that chunks land
close to the target size instead of being needlessly fragmented.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from ragforge.chunking.base import ChunkCandidate, Chunker, SizeMeter
from ragforge.models.config import ChunkingConfig
from ragforge.models.document import Document
from ragforge.utils.text import split_sentences

_HEADING_SPLIT_RE = re.compile(r"(?=^#{1,6}\s+)", re.MULTILINE)


class RecursiveSplitter:
    """Splits a text into pieces no larger than ``max_size`` where possible."""

    def __init__(
        self,
        meter: SizeMeter,
        *,
        target_size: int,
        max_size: int,
        min_size: int = 0,
        respect_sentences: bool = True,
    ) -> None:
        self.meter = meter
        self.target_size = target_size
        self.max_size = max_size
        self.min_size = min_size
        self.respect_sentences = respect_sentences

    # ------------------------------------------------------------------
    def split(self, text: str) -> list[str]:
        stripped = text.strip()
        if not stripped:
            return []
        if self.meter.size(stripped) <= self.target_size:
            return [stripped]
        pieces = self._split_recursive(stripped, 0)
        return self._merge(pieces)

    # ------------------------------------------------------------------
    def _split_recursive(self, text: str, level: int) -> list[str]:
        if not text.strip():
            return []
        if self.meter.size(text) <= self.target_size:
            return [text]

        splitters = self._splitters()
        if level >= len(splitters):
            return [text]

        parts = [p for p in splitters[level](text) if p.strip()]
        if len(parts) <= 1:
            return self._split_recursive(text, level + 1)

        out: list[str] = []
        for part in parts:
            if self.meter.size(part) <= self.target_size:
                out.append(part)
            else:
                out.extend(self._split_recursive(part, level + 1))
        return out

    def _splitters(self) -> list[Callable[[str], list[str]]]:
        """Separator hierarchy, coarsest first."""
        items: list[Callable[[str], list[str]]] = [
            _split_headings,
            _split_paragraphs_keep,
            _split_lines,
        ]
        if self.respect_sentences:
            items.append(split_sentences)
        items.append(_split_words)
        items.append(self._split_characters)
        return items

    def _split_characters(self, text: str) -> list[str]:
        """Hard fallback: slice by characters proportional to the size unit."""
        size = self.meter.size(text)
        if size <= self.max_size or not text:
            return [text]
        approx_chars = max(1, int(len(text) * self.target_size / max(size, 1)))
        return [text[i : i + approx_chars] for i in range(0, len(text), approx_chars)]

    # ------------------------------------------------------------------
    def _merge(self, pieces: list[str]) -> list[str]:
        """Greedily merge adjacent pieces until they approach the target size."""
        merged: list[str] = []
        buffer: list[str] = []
        buffer_size = 0

        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            piece_size = self.meter.size(piece)
            if buffer and buffer_size + piece_size > self.target_size:
                if buffer_size + piece_size <= self.max_size and buffer_size < self.min_size:
                    buffer.append(piece)
                    buffer_size += piece_size
                    continue
                merged.append(_join(buffer))
                buffer = [piece]
                buffer_size = piece_size
                continue
            buffer.append(piece)
            buffer_size += piece_size
        if buffer:
            merged.append(_join(buffer))
        return [m for m in merged if m.strip()]


def _join(parts: list[str]) -> str:
    out = ""
    for part in parts:
        if not out:
            out = part
            continue
        separator = "\n\n" if (_looks_like_block(part) or out.endswith((":", "\n"))) else " "
        out = f"{out.rstrip()}{separator}{part.lstrip()}"
    return out.strip()


def _looks_like_block(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith(("#", "-", "*", "|", ">", "```", "1.", "2.", "3."))


def _split_headings(text: str) -> list[str]:
    parts = _HEADING_SPLIT_RE.split(text)
    return parts if len(parts) > 1 else [text]


def _split_paragraphs_keep(text: str) -> list[str]:
    return re.split(r"\n\s*\n+", text)


def _split_lines(text: str) -> list[str]:
    return text.split("\n")


def _split_words(text: str) -> list[str]:
    return re.split(r"(?<=\s)", text)


class RecursiveChunker(Chunker):
    """Section-aware recursive chunking (the default strategy)."""

    name = "recursive"

    def __init__(
        self, config: ChunkingConfig | None = None, meter: SizeMeter | None = None
    ) -> None:
        super().__init__(config, meter)
        from ragforge.chunking.structural import StructuralChunker

        self._structural = StructuralChunker(self.config, self.meter, mode="recursive")

    def chunk(self, document: Document) -> list[ChunkCandidate]:
        return self._structural.chunk(document)
