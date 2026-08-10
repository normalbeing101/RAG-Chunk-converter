"""Intelligent chunk overlap.

Overlap exists for one reason: a fact stated at the end of one chunk and
referenced at the start of the next would otherwise be unreachable. It is not
free - every overlapped token is stored and embedded twice - so it is applied
narrowly:

* only between two pieces of the **same** semantic unit (a unit the splitter
  had to divide), never across a section or concept boundary,
* only at a paragraph or sentence boundary,
* never duplicating a heading, a code fence, a table header or a list marker,
* never when the previous chunk's tail is already present in the next chunk.

The carried text is inserted *after* the next chunk's heading, so the heading
always stays on the first line and the chunk keeps reading as a document.
"""

from __future__ import annotations

import re
from itertools import pairwise

from ragforge.chunking.base import ChunkCandidate, SizeMeter
from ragforge.models.config import ChunkingConfig
from ragforge.utils.text import split_paragraphs, split_sentences

_HEADING_LINE_RE = re.compile(r"^\s{0,3}#{1,6}\s")
_STRUCTURAL_START = ("- ", "* ", "+ ", "|", ">", "```", "~~~")
_NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s")


class OverlapApplier:
    """Adds contextual overlap between consecutive pieces of a split unit."""

    def __init__(self, config: ChunkingConfig, meter: SizeMeter) -> None:
        self.config = config
        self.meter = meter
        self.amount = config.resolved_overlap()

    # ------------------------------------------------------------------
    def apply(self, candidates: list[ChunkCandidate]) -> list[ChunkCandidate]:
        if self.amount <= 0 or len(candidates) < 2:
            return candidates

        out: list[ChunkCandidate] = [candidates[0]]
        for previous, current in pairwise(candidates):
            carried = self._carry(previous, current)
            if carried:
                current.text = carried.text
                current.metadata = {
                    **current.metadata,
                    "overlap_prefix_chars": carried.length,
                }
            out.append(current)
        return out

    # ------------------------------------------------------------------
    def _carry(self, previous: ChunkCandidate, current: ChunkCandidate) -> _Carried | None:
        if not self._should_overlap(previous, current):
            return None
        tail = self._tail(previous.text)
        if not tail:
            return None
        # Never duplicate text the next chunk already contains.
        if tail in current.text:
            return None

        heading, body = _split_leading_heading(current.text)
        merged_body = f"{tail}\n\n{body}" if body else tail
        merged = f"{heading}\n\n{merged_body}" if heading else merged_body
        if self.meter.size(merged) > self.config.max_size:
            return None
        # Offset of the carried text within the final string.
        return _Carried(text=merged, length=len(tail))

    def _should_overlap(self, previous: ChunkCandidate, current: ChunkCandidate) -> bool:
        """Overlap only inside a single split unit."""
        if previous.heading_path != current.heading_path:
            return False
        if previous.metadata.get("heading_only") or current.metadata.get("heading_only"):
            return False
        # Code and tables are atomic: repeating part of them is noise.
        if {previous.content_type, current.content_type} & {"code", "table", "metadata"}:
            return False
        # Only pieces the splitter produced from one unit may overlap. Distinct
        # sibling concepts that merely share a heading path must not.
        return bool(previous.metadata.get("block_split") and current.metadata.get("block_split"))

    # ------------------------------------------------------------------
    def _tail(self, text: str) -> str:
        """Take up to ``amount`` units from the end of ``text``."""
        _, body = _split_leading_heading(text)
        if not body.strip():
            return ""
        for extractor in (self._tail_paragraphs, self._tail_sentences):
            tail = extractor(body)
            if tail and _is_safe_tail(tail):
                return tail
        return ""

    def _tail_paragraphs(self, text: str) -> str:
        paragraphs = split_paragraphs(text)
        return self._collect(paragraphs, "\n\n") if len(paragraphs) >= 2 else ""

    def _tail_sentences(self, text: str) -> str:
        sentences = split_sentences(text)
        return self._collect(sentences, " ") if len(sentences) >= 2 else ""

    def _collect(self, parts: list[str], joiner: str) -> str:
        """Take whole trailing parts until the overlap budget is reached."""
        selected: list[str] = []
        size = 0
        for part in reversed(parts):
            part_size = self.meter.size(part)
            if selected and size + part_size > self.amount:
                break
            if not selected and part_size > self.amount * 1.5:
                return ""  # single trailing unit far larger than the budget
            selected.insert(0, part)
            size += part_size
            if size >= self.amount:
                break
        if not selected or len(selected) == len(parts):
            return ""
        return joiner.join(selected).strip()


class _Carried:
    __slots__ = ("length", "text")

    def __init__(self, text: str, length: int) -> None:
        self.text = text
        self.length = length


def _split_leading_heading(text: str) -> tuple[str, str]:
    """Separate a leading Markdown heading from the body that follows it."""
    lines = text.split("\n")
    index = 0
    heading: list[str] = []
    while index < len(lines) and (not lines[index].strip() or _HEADING_LINE_RE.match(lines[index])):
        if lines[index].strip():
            heading.append(lines[index].strip())
        index += 1
    return "\n".join(heading), "\n".join(lines[index:]).strip()


def _is_safe_tail(tail: str) -> bool:
    """Reject tails that would corrupt structure when prepended."""
    stripped = tail.strip()
    if not stripped:
        return False
    if _HEADING_LINE_RE.match(stripped):
        return False
    if stripped.startswith(_STRUCTURAL_START) or _NUMBERED_RE.match(stripped):
        return False
    # Unbalanced code fence would break the next chunk's Markdown.
    return stripped.count("```") % 2 == 0
