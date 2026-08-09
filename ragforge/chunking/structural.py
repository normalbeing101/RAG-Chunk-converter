"""Structural chunking.

The document is first grouped into *sections* delimited by headings. Blocks
within a section are then packed into chunks that stay as close as possible to
the target size while never crossing a section boundary and never splitting a
paragraph, table or code block unless it exceeds the hard maximum.

This module also powers the ``recursive`` and ``sentence`` strategies: they
share the same section packing logic and differ only in how oversized units are
broken down.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ragforge.chunking.base import ChunkCandidate, Chunker, SizeMeter
from ragforge.chunking.code import split_code_block
from ragforge.models.config import ChunkingConfig
from ragforge.models.document import Block, BlockType, Document
from ragforge.utils.text import split_sentences


@dataclass(slots=True)
class Section:
    """A heading and the blocks that belong to it."""

    heading: Block | None
    blocks: list[Block] = field(default_factory=list)
    path: list[str] = field(default_factory=list)

    @property
    def title(self) -> str | None:
        return self.path[-1] if self.path else None

    def content_blocks(self) -> list[Block]:
        return [b for b in self.blocks if not b.is_heading]


def build_sections(blocks: list[Block], *, max_depth: int = 6) -> list[Section]:
    """Group blocks under their nearest qualifying heading."""
    sections: list[Section] = []
    current = Section(heading=None, blocks=[], path=[])

    for block in blocks:
        if block.is_heading and block.level <= max_depth:
            if current.blocks:
                sections.append(current)
            current = Section(heading=block, blocks=[block], path=block.full_path())
            continue
        current.blocks.append(block)
        if not current.path and block.heading_path:
            current.path = list(block.heading_path)
    if current.blocks:
        sections.append(current)
    return sections


class StructuralChunker(Chunker):
    """Packs structural blocks into coherent chunks.

    ``mode`` controls how oversized units are handled:

    * ``structural`` - split paragraphs on sentence boundaries only.
    * ``recursive``  - full recursive separator hierarchy.
    * ``sentence``   - every prose block is decomposed into sentences first.
    """

    name = "structural"

    def __init__(
        self,
        config: ChunkingConfig | None = None,
        meter: SizeMeter | None = None,
        *,
        mode: str = "structural",
    ) -> None:
        super().__init__(config, meter)
        self.mode = mode
        self.name = mode

    # ------------------------------------------------------------------
    def chunk(self, document: Document) -> list[ChunkCandidate]:
        blocks = self.blocks_of(document)
        if not blocks:
            return []
        max_depth = self.config.max_heading_depth_split if self.config.split_on_headings else 0
        sections = build_sections(blocks, max_depth=max_depth or 0)
        candidates: list[ChunkCandidate] = []
        for group in self._coalesce_sections(sections):
            candidates.extend(self._chunk_group(group))
        return [c for c in candidates if c.text.strip()]

    # ------------------------------------------------------------------
    def _coalesce_sections(self, sections: list[Section]) -> list[list[Section]]:
        """Group consecutive small related sections so they share a chunk.

        A document made of many short sections (glossaries, FAQs, API stubs)
        would otherwise produce one tiny chunk per heading. Merging related
        neighbours up to the target size yields chunks that are both complete
        and appropriately sized. Sections are only merged when one is an
        ancestor of the other or they are siblings, so unrelated topics never
        end up together.
        """
        if not self.config.merge_small_chunks or len(sections) < 2:
            return [[section] for section in sections]

        groups: list[list[Section]] = []
        current: list[Section] = []
        current_size = 0

        for section in sections:
            size = self.meter.size(self._render_section(section))
            if current and (
                current_size + size > self.config.target_size
                or not _related(current[-1].path, section.path)
                or current_size >= self.config.min_size
            ):
                groups.append(current)
                current, current_size = [], 0
            current.append(section)
            current_size += size
        if current:
            groups.append(current)
        return groups

    def _render_section(self, section: Section) -> str:
        parts = []
        if section.heading:
            parts.append(f"{'#' * section.heading.level} {section.heading.text.strip()}")
        parts.extend(b.text.strip() for b in section.content_blocks() if b.text.strip())
        return "\n\n".join(parts)

    def _chunk_group(self, group: list[Section]) -> list[ChunkCandidate]:
        if len(group) == 1:
            return self._chunk_section(group[0])

        # Merged sections become one candidate holding every heading inline.
        text = "\n\n".join(self._render_section(s) for s in group if self._render_section(s))
        if not text.strip():
            return []
        blocks = [b for section in group for b in section.blocks]
        content_blocks = [b for b in blocks if not b.is_heading]
        # The shared ancestor path is the only honest label for a merged group;
        # the individual titles remain inline in the text and in metadata.
        return [
            ChunkCandidate(
                text=text,
                heading_path=_common_path([s.path for s in group]),
                content_type=self.content_type_for(content_blocks or blocks),
                language=self.language_for(blocks),
                start_offset=blocks[0].start_offset,
                end_offset=blocks[-1].end_offset,
                block_types=sorted({b.type.value for b in blocks}),
                metadata={"merged_sections": [s.title for s in group if s.title]},
            )
        ]

    # ------------------------------------------------------------------
    def _chunk_section(self, section: Section) -> list[ChunkCandidate]:
        heading_text = section.heading.text.strip() if section.heading else ""
        heading_prefix = f"{'#' * section.heading.level} {heading_text}" if section.heading else ""
        content_blocks = section.content_blocks()
        path = section.path

        if not content_blocks:
            if heading_prefix:
                return [
                    ChunkCandidate(
                        text=heading_prefix,
                        heading_path=path,
                        content_type="heading",
                        start_offset=section.heading.start_offset if section.heading else 0,
                        end_offset=section.heading.end_offset if section.heading else 0,
                        block_types=["heading"],
                        metadata={"heading_only": True},
                    )
                ]
            return []

        heading_size = self.meter.size(heading_prefix) if heading_prefix else 0
        budget = max(1, self.config.target_size - heading_size)
        hard_limit = max(budget, self.config.max_size - heading_size)

        groups = self._pack_blocks(content_blocks, budget=budget, hard_limit=hard_limit)
        if self.config.merge_small_chunks:
            groups = self._merge_small(groups, budget=budget, hard_limit=hard_limit)

        candidates: list[ChunkCandidate] = []
        for group in groups:
            # The heading is repeated in every chunk of the section so that each
            # chunk remains self-describing when retrieved in isolation.
            text = group.render(heading_prefix)
            candidates.append(
                ChunkCandidate(
                    text=text,
                    heading_path=path,
                    content_type=group.content_type,
                    language=group.language,
                    start_offset=group.start_offset,
                    end_offset=group.end_offset,
                    block_types=group.block_types,
                    metadata=group.metadata,
                )
            )
        return candidates

    # ------------------------------------------------------------------
    def _pack_blocks(self, blocks: list[Block], *, budget: int, hard_limit: int) -> list[_Group]:
        groups: list[_Group] = []
        current = _Group()

        for block in blocks:
            units = self._decompose(block, budget=budget, hard_limit=hard_limit)
            for unit in units:
                size = self.meter.size(unit.text)
                if current.units and current.size + size > budget:
                    groups.append(current)
                    current = _Group()
                current.add(unit, size)
                if current.size >= hard_limit:
                    groups.append(current)
                    current = _Group()
        if current.units:
            groups.append(current)
        return groups

    def _decompose(self, block: Block, *, budget: int, hard_limit: int) -> list[_Unit]:
        """Break a block into units that individually fit the budget."""
        text = block.text.strip()
        if not text:
            return []
        size = self.meter.size(text)
        base = _Unit(
            text=text,
            block_type=block.type,
            language=block.language,
            start_offset=block.start_offset,
            end_offset=block.end_offset,
        )
        if size <= budget:
            return [base]

        if block.type is BlockType.CODE:
            if self.config.keep_code_blocks_intact and size <= hard_limit:
                return [base]
            pieces = split_code_block(text, self.meter, budget=budget, language=block.language)
            return [
                _Unit(
                    text=piece,
                    block_type=BlockType.CODE,
                    language=block.language,
                    start_offset=block.start_offset,
                    end_offset=block.end_offset,
                    split=len(pieces) > 1,
                )
                for piece in pieces
            ]

        if block.type is BlockType.TABLE:
            if self.config.keep_tables_intact and size <= hard_limit:
                return [base]
            return [
                _Unit(
                    text=piece,
                    block_type=BlockType.TABLE,
                    start_offset=block.start_offset,
                    end_offset=block.end_offset,
                    split=True,
                )
                for piece in _split_table(text, self.meter, budget)
            ]

        if block.type in {BlockType.LIST, BlockType.NUMBERED_LIST}:
            pieces = _split_list_items(text, self.meter, budget)
        elif self.mode == "sentence":
            pieces = _pack_sentences(split_sentences(text), self.meter, budget)
        elif self.mode == "recursive":
            from ragforge.chunking.recursive import RecursiveSplitter

            splitter = RecursiveSplitter(
                self.meter,
                target_size=budget,
                max_size=hard_limit,
                min_size=min(self.config.min_size, budget),
                respect_sentences=self.config.respect_sentence_boundaries,
            )
            pieces = splitter.split(text)
        else:
            pieces = _pack_sentences(split_sentences(text), self.meter, budget)

        if not pieces:
            pieces = [text]
        return [
            _Unit(
                text=piece,
                block_type=block.type,
                start_offset=block.start_offset,
                end_offset=block.end_offset,
                split=len(pieces) > 1,
            )
            for piece in pieces
        ]

    def _merge_small(self, groups: list[_Group], *, budget: int, hard_limit: int) -> list[_Group]:
        """Fold undersized trailing groups back into their neighbour."""
        if len(groups) < 2:
            return groups
        minimum = min(self.config.min_size, budget)
        merged: list[_Group] = []
        for group in groups:
            if merged and group.size < minimum and merged[-1].size + group.size <= hard_limit:
                merged[-1].absorb(group)
                continue
            merged.append(group)
        # A single leading small group may still remain; merge forwards.
        if (
            len(merged) >= 2
            and merged[0].size < minimum
            and merged[0].size + merged[1].size <= hard_limit
        ):
            head = merged.pop(0)
            head.absorb(merged[0])
            merged[0] = head
        return merged


def _related(left: list[str], right: list[str]) -> bool:
    """True when two heading paths are siblings or ancestor/descendant."""
    if not left or not right:
        return True
    shorter = min(len(left), len(right))
    if left[: shorter - 1] != right[: shorter - 1]:
        return False
    return len(left) == len(right) or left[:shorter] == right[:shorter]


def _common_path(paths: list[list[str]]) -> list[str]:
    """Longest heading path shared by every section in a merged group."""
    if not paths:
        return []
    common = list(paths[0])
    for path in paths[1:]:
        limit = 0
        for a, b in zip(common, path, strict=False):
            if a != b:
                break
            limit += 1
        common = common[:limit]
    return common


_TYPE_LABELS: dict[BlockType, str] = {
    BlockType.CODE: "code",
    BlockType.TABLE: "table",
    BlockType.LIST: "list",
    BlockType.NUMBERED_LIST: "list",
    BlockType.QUOTE: "quote",
    BlockType.HEADING: "heading",
    BlockType.TITLE: "heading",
}


def classify_content_type(weighted: list[tuple[BlockType, int]]) -> str:
    """Dominant content type for a chunk, weighted by characters contributed.

    Specialised blocks (code, table, list, quote) outrank surrounding prose,
    because a paragraph introducing a code sample is still best described - and
    filtered - as a code chunk. ``mixed`` is reserved for chunks where two
    *different* specialised types share the space without a clear majority.
    """
    if not weighted:
        return "text"
    weights: dict[str, int] = {}
    for block_type, length in weighted:
        label = _TYPE_LABELS.get(block_type, "text")
        weights[label] = weights.get(label, 0) + length

    special = {k: v for k, v in weights.items() if k not in {"text", "heading"}}
    if not special:
        return "heading" if set(weights) == {"heading"} else "text"
    total = sum(special.values()) or 1
    label, weight = max(special.items(), key=lambda kv: kv[1])
    if len(special) > 1 and weight / total < 0.6:
        return "mixed"
    return label


@dataclass(slots=True)
class _Unit:
    text: str
    block_type: BlockType = BlockType.PARAGRAPH
    language: str | None = None
    start_offset: int = 0
    end_offset: int = 0
    split: bool = False


@dataclass(slots=True)
class _Group:
    units: list[_Unit] = field(default_factory=list)
    size: int = 0

    def add(self, unit: _Unit, size: int) -> None:
        self.units.append(unit)
        self.size += size

    def absorb(self, other: _Group) -> None:
        self.units.extend(other.units)
        self.size += other.size

    @property
    def start_offset(self) -> int:
        return self.units[0].start_offset if self.units else 0

    @property
    def end_offset(self) -> int:
        return self.units[-1].end_offset if self.units else 0

    @property
    def block_types(self) -> list[str]:
        seen: list[str] = []
        for unit in self.units:
            value = unit.block_type.value
            if value not in seen:
                seen.append(value)
        return seen

    @property
    def language(self) -> str | None:
        for unit in self.units:
            if unit.language:
                return unit.language
        return None

    @property
    def content_type(self) -> str:
        return classify_content_type([(u.block_type, len(u.text)) for u in self.units])

    @property
    def metadata(self) -> dict:
        meta: dict = {}
        if any(u.split and u.block_type is BlockType.CODE for u in self.units):
            meta["code_split"] = True
        if any(u.split for u in self.units):
            meta["block_split"] = True
        return meta

    def render(self, heading_prefix: str = "") -> str:
        body = "\n\n".join(unit.text.strip() for unit in self.units if unit.text.strip())
        if heading_prefix:
            return f"{heading_prefix}\n\n{body}".strip()
        return body.strip()


# ----------------------------------------------------------------------
# Splitting helpers
# ----------------------------------------------------------------------
def _pack_sentences(sentences: list[str], meter: SizeMeter, budget: int) -> list[str]:
    """Greedily pack sentences without ever cutting one in half."""
    packed: list[str] = []
    buffer: list[str] = []
    size = 0
    for sentence in sentences:
        sentence_size = meter.size(sentence)
        if buffer and size + sentence_size > budget:
            packed.append(" ".join(buffer).strip())
            buffer, size = [], 0
        if sentence_size > budget and not buffer:
            packed.extend(_hard_split(sentence, meter, budget))
            continue
        buffer.append(sentence)
        size += sentence_size
    if buffer:
        packed.append(" ".join(buffer).strip())
    return [p for p in packed if p]


def _split_list_items(text: str, meter: SizeMeter, budget: int) -> list[str]:
    """Split a list at item boundaries, keeping nested continuation lines."""
    import re

    marker = re.compile(r"^\s*(?:[-*+\u2022]|\d+[.)]|[a-zA-Z][.)])\s+")
    items: list[str] = []
    buffer: list[str] = []
    for line in text.split("\n"):
        if marker.match(line) and buffer:
            items.append("\n".join(buffer))
            buffer = [line]
        else:
            buffer.append(line)
    if buffer:
        items.append("\n".join(buffer))

    packed: list[str] = []
    current: list[str] = []
    size = 0
    for item in items:
        item_size = meter.size(item)
        if current and size + item_size > budget:
            packed.append("\n".join(current).strip())
            current, size = [], 0
        current.append(item)
        size += item_size
    if current:
        packed.append("\n".join(current).strip())
    return [p for p in packed if p.strip()]


def _split_table(text: str, meter: SizeMeter, budget: int) -> list[str]:
    """Split a Markdown table by rows, repeating the header in each part."""
    lines = [line for line in text.split("\n") if line.strip()]
    if len(lines) <= 2:
        return [text]
    header = lines[:2] if set(lines[1].replace("|", "").strip()) <= set("-: ") else lines[:1]
    body = lines[len(header) :]
    header_text = "\n".join(header)
    header_size = meter.size(header_text)

    parts: list[str] = []
    current: list[str] = []
    size = header_size
    for row in body:
        row_size = meter.size(row)
        if current and size + row_size > budget:
            parts.append("\n".join([*header, *current]))
            current, size = [], header_size
        current.append(row)
        size += row_size
    if current:
        parts.append("\n".join([*header, *current]))
    return parts or [text]


def _hard_split(text: str, meter: SizeMeter, budget: int) -> list[str]:
    """Last-resort word-boundary split for a single oversized sentence."""
    words = text.split()
    if not words:
        return [text]
    parts: list[str] = []
    buffer: list[str] = []
    size = 0
    for word in words:
        word_size = meter.size(word + " ")
        if buffer and size + word_size > budget:
            parts.append(" ".join(buffer))
            buffer, size = [], 0
        buffer.append(word)
        size += word_size
    if buffer:
        parts.append(" ".join(buffer))
    return parts
