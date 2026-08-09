"""Structural analysis.

Turns Markdown-flavoured text into an ordered list of :class:`Block` objects
with a resolved heading hierarchy. Every downstream chunker consumes blocks
rather than raw text, which is what makes chunk boundaries structural instead
of arbitrary.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator

from ragforge.models.document import Block, BlockType, Document, DocumentStructure

_ATX_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^(\s*)(```+|~~~+)\s*([\w+#.-]*)")
_INDENTED_CODE_RE = re.compile(r"^(?: {4}|\t)\S")
_BULLET_RE = re.compile(r"^\s*[-*+\u2022]\s+")
_NUMBERED_RE = re.compile(r"^\s*(?:\d+|[a-zA-Z])[.)]\s+")
_QUOTE_RE = re.compile(r"^\s*>\s?")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")
_HR_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")


class StructureAnalyzer:
    """Parses text into structural blocks with heading paths."""

    def __init__(self, *, max_heading_depth: int = 6) -> None:
        self.max_heading_depth = max_heading_depth

    def analyze(self, document: Document) -> Document:
        structure = self.analyze_text(document.content)
        return document.model_copy(update={"structure": structure})

    def analyze_text(self, text: str) -> DocumentStructure:
        blocks = list(self._iter_blocks(text or ""))
        self._assign_heading_paths(blocks)
        counts = Counter(block.type.value for block in blocks)
        heading_levels = [b.level for b in blocks if b.is_heading]
        return DocumentStructure(
            blocks=blocks,
            has_headings=bool(heading_levels),
            max_heading_depth=max(heading_levels, default=0),
            block_counts=dict(counts),
        )

    # ------------------------------------------------------------------
    # Block segmentation
    # ------------------------------------------------------------------
    def _iter_blocks(self, text: str) -> Iterator[Block]:
        lines = text.split("\n")
        offsets = _line_offsets(lines)
        index = 0
        total = len(lines)

        while index < total:
            line = lines[index]
            stripped = line.strip()

            if not stripped:
                index += 1
                continue

            fence = _FENCE_RE.match(line)
            if fence:
                block, index = _consume_fenced_code(lines, index, offsets, fence)
                yield block
                continue

            heading = _ATX_RE.match(stripped)
            if heading:
                level = len(heading.group(1))
                yield Block(
                    type=BlockType.HEADING,
                    text=heading.group(2).strip(),
                    level=level,
                    start_line=index,
                    end_line=index,
                    start_offset=offsets[index],
                    end_offset=offsets[index] + len(line),
                )
                index += 1
                continue

            if _HR_RE.match(stripped):
                index += 1
                continue

            if _TABLE_ROW_RE.match(line):
                table, next_index = _consume_table(lines, index, offsets)
                if table is not None:
                    yield table
                    index = next_index
                    continue

            if _QUOTE_RE.match(line):
                block, index = _consume_while(
                    lines, index, offsets, BlockType.QUOTE, lambda ln: bool(_QUOTE_RE.match(ln))
                )
                yield block
                continue

            if _BULLET_RE.match(line) or _NUMBERED_RE.match(line):
                is_numbered = bool(_NUMBERED_RE.match(line))
                block, index = _consume_list(lines, index, offsets, numbered=is_numbered)
                yield block
                continue

            if _INDENTED_CODE_RE.match(line):
                block, index = _consume_while(
                    lines,
                    index,
                    offsets,
                    BlockType.CODE,
                    lambda ln: bool(_INDENTED_CODE_RE.match(ln)) or not ln.strip(),
                )
                block.metadata["fenced"] = False
                yield block
                continue

            block, index = _consume_paragraph(lines, index, offsets)
            yield block

    def _assign_heading_paths(self, blocks: list[Block]) -> None:
        stack: list[tuple[int, str]] = []
        first_heading_seen = False
        for block in blocks:
            if block.is_heading:
                while stack and stack[-1][0] >= block.level:
                    stack.pop()
                block.heading_path = [title for _, title in stack]
                if not first_heading_seen:
                    block.type = BlockType.TITLE if block.level == 1 else BlockType.HEADING
                    first_heading_seen = True
                stack.append((block.level, block.text.strip()))
            else:
                block.heading_path = [title for _, title in stack]


# ----------------------------------------------------------------------
# Consumers
# ----------------------------------------------------------------------
def _line_offsets(lines: list[str]) -> list[int]:
    offsets = []
    position = 0
    for line in lines:
        offsets.append(position)
        position += len(line) + 1
    offsets.append(position)
    return offsets


def _consume_fenced_code(
    lines: list[str], start: int, offsets: list[int], fence: re.Match[str]
) -> tuple[Block, int]:
    marker = fence.group(2)
    language = (fence.group(3) or "").strip() or None
    index = start + 1
    closed = False
    while index < len(lines):
        candidate = lines[index].strip()
        if candidate.startswith(marker[0] * len(marker)) and set(candidate) <= set(marker[0]):
            closed = True
            index += 1
            break
        index += 1
    end = index - 1
    text = "\n".join(lines[start:index])
    return (
        Block(
            type=BlockType.CODE,
            text=text,
            language=language,
            start_line=start,
            end_line=end,
            start_offset=offsets[start],
            end_offset=offsets[min(index, len(lines))],
            metadata={"fenced": True, "closed": closed, "fence": marker},
        ),
        index,
    )


def _consume_table(lines: list[str], start: int, offsets: list[int]) -> tuple[Block | None, int]:
    index = start
    rows = 0
    while index < len(lines) and _TABLE_ROW_RE.match(lines[index]):
        rows += 1
        index += 1
    if rows < 2:
        return None, start
    second = lines[start + 1] if start + 1 < len(lines) else ""
    has_separator = bool(_TABLE_SEP_RE.match(second))
    text = "\n".join(lines[start:index])
    return (
        Block(
            type=BlockType.TABLE,
            text=text,
            start_line=start,
            end_line=index - 1,
            start_offset=offsets[start],
            end_offset=offsets[index],
            metadata={"rows": rows, "has_header": has_separator},
        ),
        index,
    )


def _consume_list(
    lines: list[str], start: int, offsets: list[int], *, numbered: bool
) -> tuple[Block, int]:
    index = start
    blank_run = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            blank_run += 1
            if blank_run > 1:
                break
            index += 1
            continue
        is_item = bool(_BULLET_RE.match(line) or _NUMBERED_RE.match(line))
        is_continuation = line.startswith((" ", "\t")) and blank_run == 0
        if not (is_item or is_continuation):
            break
        blank_run = 0
        index += 1
    while index > start and not lines[index - 1].strip():
        index -= 1
    text = "\n".join(lines[start:index])
    return (
        Block(
            type=BlockType.NUMBERED_LIST if numbered else BlockType.LIST,
            text=text,
            start_line=start,
            end_line=index - 1,
            start_offset=offsets[start],
            end_offset=offsets[index],
            metadata={"items": _count_items(text)},
        ),
        index,
    )


def _consume_while(
    lines: list[str], start: int, offsets: list[int], block_type: BlockType, predicate
) -> tuple[Block, int]:
    index = start
    while index < len(lines) and predicate(lines[index]):
        index += 1
    while index > start and not lines[index - 1].strip():
        index -= 1
    text = "\n".join(lines[start:index])
    return (
        Block(
            type=block_type,
            text=text,
            start_line=start,
            end_line=index - 1,
            start_offset=offsets[start],
            end_offset=offsets[index],
        ),
        index,
    )


def _consume_paragraph(lines: list[str], start: int, offsets: list[int]) -> tuple[Block, int]:
    index = start
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            break
        if index > start and (
            _ATX_RE.match(line.strip())
            or _FENCE_RE.match(line)
            or _BULLET_RE.match(line)
            or _NUMBERED_RE.match(line)
            or _TABLE_ROW_RE.match(line)
            or _QUOTE_RE.match(line)
        ):
            break
        index += 1
    text = "\n".join(lines[start:index])
    return (
        Block(
            type=BlockType.PARAGRAPH,
            text=text,
            start_line=start,
            end_line=index - 1,
            start_offset=offsets[start],
            end_offset=offsets[index],
        ),
        index,
    )


def _count_items(text: str) -> int:
    return sum(1 for line in text.split("\n") if _BULLET_RE.match(line) or _NUMBERED_RE.match(line))


def analyze(text: str) -> DocumentStructure:
    """Convenience helper for tests and quick usage."""
    return StructureAnalyzer().analyze_text(text)
