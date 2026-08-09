"""Intelligent chunk overlap.

Overlap text is taken from the *end* of the previous chunk and prepended to the
next one, but only at a legitimate boundary:

1. paragraph boundary,
2. sentence boundary,
3. line boundary,
4. word boundary (last resort).

Overlap is never applied across section boundaries and never duplicates a
heading-only or code chunk wholesale.
"""

from __future__ import annotations

from itertools import pairwise

from ragforge.chunking.base import ChunkCandidate, SizeMeter
from ragforge.models.config import ChunkingConfig
from ragforge.utils.text import split_paragraphs, split_sentences


class OverlapApplier:
    """Adds contextual overlap between consecutive chunks."""

    def __init__(self, config: ChunkingConfig, meter: SizeMeter) -> None:
        self.config = config
        self.meter = meter
        self.amount = config.resolved_overlap()

    def apply(self, candidates: list[ChunkCandidate]) -> list[ChunkCandidate]:
        if self.amount <= 0 or len(candidates) < 2:
            return candidates

        out: list[ChunkCandidate] = [candidates[0]]
        for previous, current in pairwise(candidates):
            if not self._should_overlap(previous, current):
                out.append(current)
                continue
            tail = self._tail(previous.text, current.text)
            if not tail:
                out.append(current)
                continue
            merged = f"{tail}\n\n{current.text}" if "\n" in tail else f"{tail} {current.text}"
            if self.meter.size(merged) > self.config.max_size:
                out.append(current)
                continue
            current.text = merged
            current.metadata = {**current.metadata, "overlap_prefix_chars": len(tail)}
            out.append(current)
        return out

    # ------------------------------------------------------------------
    def _should_overlap(self, previous: ChunkCandidate, current: ChunkCandidate) -> bool:
        if previous.heading_path != current.heading_path:
            return False
        if current.content_type == "code" or previous.content_type == "code":
            return False
        return not (previous.metadata.get("heading_only") or current.metadata.get("heading_only"))

    def _tail(self, text: str, following: str) -> str:
        """Extract up to ``amount`` units from the end of ``text``."""
        body = _strip_leading_heading(text)
        if not body.strip():
            return ""

        for extractor in (self._tail_paragraphs, self._tail_sentences, self._tail_lines):
            tail = extractor(body)
            if tail and tail.strip() and tail.strip() not in following:
                return tail.strip()
        return self._tail_words(body)

    def _tail_paragraphs(self, text: str) -> str:
        paragraphs = split_paragraphs(text)
        if len(paragraphs) < 2:
            return ""
        return self._collect_backwards(paragraphs, "\n\n")

    def _tail_sentences(self, text: str) -> str:
        sentences = split_sentences(text)
        if len(sentences) < 2:
            return ""
        return self._collect_backwards(sentences, " ")

    def _tail_lines(self, text: str) -> str:
        lines = [line for line in text.split("\n") if line.strip()]
        if len(lines) < 2:
            return ""
        return self._collect_backwards(lines, "\n")

    def _tail_words(self, text: str) -> str:
        words = text.split()
        if len(words) < 2:
            return ""
        selected: list[str] = []
        size = 0
        for word in reversed(words):
            word_size = self.meter.size(word + " ")
            if size + word_size > self.amount and selected:
                break
            selected.insert(0, word)
            size += word_size
        return " ".join(selected) if len(selected) < len(words) else ""

    def _collect_backwards(self, parts: list[str], joiner: str) -> str:
        selected: list[str] = []
        size = 0
        for part in reversed(parts):
            part_size = self.meter.size(part)
            if selected and size + part_size > self.amount:
                break
            if not selected and part_size > self.amount * 1.5:
                # Single trailing unit far larger than the overlap budget.
                return ""
            selected.insert(0, part)
            size += part_size
            if size >= self.amount:
                break
        if not selected or len(selected) == len(parts):
            return ""
        return joiner.join(selected)


def _strip_leading_heading(text: str) -> str:
    lines = text.split("\n")
    index = 0
    while index < len(lines) and (
        not lines[index].strip() or lines[index].lstrip().startswith("#")
    ):
        index += 1
    return "\n".join(lines[index:])
