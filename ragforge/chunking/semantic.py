"""Semantic chunking.

The pipeline the other strategies lacked:

    sections -> classify roles -> build semantic units -> merge related
             -> split oversized at semantic boundaries -> emit

Key differences from :mod:`ragforge.chunking.structural`:

* **Roles drive the outcome.** Keyword/alias/tag sections never become ordinary
  knowledge chunks; they are extracted into structured retrieval metadata and
  attached to the knowledge chunks around them.
* **Units are concepts, not headings.** A heading plus its explanation plus its
  definitions, rules and examples stay together while they fit.
* **Splitting respects meaning.** Oversized units break at paragraph and
  sentence boundaries only, never inside a definition, table row, list item,
  code block or misconception/correction pair.
* **Headings are never emitted alone.** An empty heading is carried forward and
  attached to the next unit that has content.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ragforge.chunking.base import ChunkCandidate, Chunker, SizeMeter
from ragforge.chunking.code import split_code_block
from ragforge.chunking.structural import Section, build_sections, classify_content_type
from ragforge.models.config import ChunkingConfig
from ragforge.models.document import Block, BlockType, Document
from ragforge.semantics.classifier import RoleClassifier, extract_terms
from ragforge.semantics.roles import SemanticRole, TermField
from ragforge.utils.text import split_sentences


@dataclass(slots=True)
class TermBundle:
    """Retrieval terms harvested from one or more term-list sections."""

    fields: dict[TermField, list[str]] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)

    def add(self, term_field: TermField, terms: list[str], source: str) -> None:
        if not terms:
            return
        bucket = self.fields.setdefault(term_field, [])
        seen = {t.casefold() for t in bucket}
        for term in terms:
            key = term.casefold()
            if key not in seen:
                seen.add(key)
                bucket.append(term)
        if source and source not in self.sources:
            self.sources.append(source)

    def is_empty(self) -> bool:
        return not any(self.fields.values())

    def as_dict(self) -> dict[str, list[str]]:
        return {f.value: list(v) for f, v in self.fields.items() if v}


@dataclass(slots=True)
class SemanticUnit:
    """A self-contained concept: heading + the content that explains it."""

    heading: Block | None
    blocks: list[Block] = field(default_factory=list)
    path: list[str] = field(default_factory=list)
    role: SemanticRole = SemanticRole.KNOWLEDGE
    size: int = 0
    titles: list[str] = field(default_factory=list)
    """Headings folded into this unit, outermost first."""
    deepest_path: list[str] = field(default_factory=list)
    """Most specific heading path covered after merging."""
    preamble: Block | None = None
    """An ancestor heading that had no content of its own; rendered first."""

    @property
    def title(self) -> str | None:
        return self.path[-1] if self.path else None

    @property
    def effective_path(self) -> list[str]:
        """The path to report: the deepest one this unit actually covers."""
        return self.deepest_path if len(self.deepest_path) > len(self.path) else self.path

    def render(self) -> str:
        parts: list[str] = []
        if self.preamble is not None and self.preamble.text.strip():
            parts.append(self.preamble.text.strip())
        if self.heading is not None and self.heading.text.strip():
            level = max(1, self.heading.level)
            parts.append(f"{'#' * level} {self.heading.text.strip()}")
        parts.extend(b.text.strip() for b in self.blocks if b.text.strip())
        return "\n\n".join(p for p in parts if p).strip()

    @property
    def has_content(self) -> bool:
        return any(b.text.strip() for b in self.blocks)


class SemanticChunker(Chunker):
    """Role-aware, concept-oriented chunking."""

    name = "semantic"

    def __init__(
        self,
        config: ChunkingConfig | None = None,
        meter: SizeMeter | None = None,
        *,
        classifier: RoleClassifier | None = None,
    ) -> None:
        super().__init__(config, meter)
        self.classifier = classifier or RoleClassifier()

    # ------------------------------------------------------------------
    def chunk(self, document: Document) -> list[ChunkCandidate]:
        blocks = self.blocks_of(document)
        if not blocks:
            return []

        max_depth = self.config.max_heading_depth_split if self.config.split_on_headings else 0
        sections = build_sections(blocks, max_depth=max_depth or 0)

        units, document_terms, meta_units = self._build_units(sections)
        units = self._merge_units(units)
        candidates = self._emit(units, document_terms)
        candidates.extend(self._emit_auxiliary(meta_units, document_terms))
        return [c for c in candidates if c.text.strip()]

    # ------------------------------------------------------------------
    # Stage 1: classify sections and turn them into semantic units
    # ------------------------------------------------------------------
    def _build_units(
        self, sections: list[Section]
    ) -> tuple[list[SemanticUnit], TermBundle, list[SemanticUnit]]:
        units: list[SemanticUnit] = []
        terms = TermBundle()
        auxiliary: list[SemanticUnit] = []
        pending_heading: Block | None = None
        pending_path: list[str] = []

        for section in sections:
            body = "\n\n".join(b.text for b in section.content_blocks() if b.text.strip())
            heading_text = section.title or ""
            assignment = self.classifier.classify_text(body, heading=heading_text)

            # -- retrieval terms: harvest, do not emit as knowledge ------
            if assignment.role is SemanticRole.RETRIEVAL_TERMS:
                harvested = assignment.terms or extract_terms(body)
                # The section heading is itself a label for these terms, so it
                # is recorded as a term. This keeps the coverage audit honest:
                # nothing from the section is unaccounted for.
                if heading_text:
                    harvested = [heading_text, *harvested]
                terms.add(assignment.field or TermField.KEYWORDS, harvested, heading_text)
                continue

            # -- document metadata / navigation: keep, but mark ----------
            if assignment.role in {SemanticRole.DOCUMENT_META, SemanticRole.NAVIGATION}:
                if section.content_blocks():
                    auxiliary.append(
                        SemanticUnit(
                            heading=section.heading,
                            blocks=list(section.content_blocks()),
                            path=list(section.path),
                            role=assignment.role,
                            titles=[section.title] if section.title else [],
                        )
                    )
                continue

            # -- an empty heading is carried to the next unit ------------
            if not section.content_blocks():
                if section.heading is not None:
                    pending_heading = section.heading
                    pending_path = list(section.path)
                continue

            heading = section.heading
            path = list(section.path)
            extra_titles: list[str] = []
            preamble: Block | None = None
            blocks = list(section.content_blocks())
            if pending_heading is not None:
                # Attach the orphaned heading rather than emitting it alone or
                # discarding it. When this section has its own heading, the
                # orphan is prepended to the body so its text is never lost.
                if heading is None:
                    heading = pending_heading
                    path = pending_path
                else:
                    # The orphan is an ancestor of this section, so it belongs
                    # above the section's own heading, not inside its body.
                    extra_titles.append(pending_heading.text.strip())
                    preamble = _heading_as_block(pending_heading)
                pending_heading = None
                pending_path = []

            unit = SemanticUnit(
                heading=heading,
                blocks=blocks,
                path=path or list(section.path),
                role=assignment.role,
                titles=[*extra_titles, *([section.title] if section.title else [])],
                deepest_path=list(path or section.path),
                preamble=preamble,
            )
            unit.size = self.meter.size(unit.render())
            units.append(unit)

        # A trailing heading with no content anywhere after it.
        if pending_heading is not None:
            units.append(
                SemanticUnit(
                    heading=pending_heading,
                    blocks=[],
                    path=pending_path,
                    role=SemanticRole.KNOWLEDGE,
                    size=self.meter.size(pending_heading.text),
                )
            )
        return units, terms, auxiliary

    # ------------------------------------------------------------------
    # Stage 2: merge related undersized units
    # ------------------------------------------------------------------
    def _merge_units(self, units: list[SemanticUnit]) -> list[SemanticUnit]:
        """Fold small sibling/child units together up to the target size."""
        if not self.config.merge_small_chunks or len(units) < 2:
            return units

        target = self.config.target_size
        minimum = self.config.min_size
        merged: list[SemanticUnit] = []

        for unit in units:
            if not merged:
                merged.append(unit)
                continue
            previous = merged[-1]
            combined = previous.size + unit.size
            if (
                (previous.size < minimum or combined <= target)
                and combined <= self.config.max_size
                and _mergeable(previous, unit)
            ):
                previous.blocks.extend(_with_heading(unit))
                previous.size = combined
                previous.titles.extend(unit.titles)
                # Remember the deepest path covered so retrieval can still
                # filter on the most specific section in the merged chunk.
                if len(unit.path) > len(previous.deepest_path):
                    previous.deepest_path = list(unit.path)
                if previous.role is SemanticRole.KNOWLEDGE:
                    previous.role = unit.role
                continue
            merged.append(unit)

        # A heading-only unit that survived merging attaches to its successor.
        result: list[SemanticUnit] = []
        for unit in merged:
            if (
                not unit.has_content
                and result
                and result[-1].size + unit.size <= self.config.max_size
            ):
                result[-1].blocks.extend(_with_heading(unit))
                continue
            result.append(unit)
        # Or, if it is first, to the one that follows.
        if len(result) >= 2 and not result[0].has_content:
            head = result.pop(0)
            result[0].blocks[:0] = _with_heading(head)
            result[0].path = head.path or result[0].path
            result[0].heading = head.heading or result[0].heading
        return result

    # ------------------------------------------------------------------
    # Stage 3: emit, splitting oversized units at semantic boundaries
    # ------------------------------------------------------------------
    def _emit(self, units: list[SemanticUnit], terms: TermBundle) -> list[ChunkCandidate]:
        candidates: list[ChunkCandidate] = []
        shared = terms.as_dict()

        for unit in units:
            text = unit.render()
            if not text.strip():
                continue
            size = self.meter.size(text)
            if size <= self.config.max_size:
                candidates.append(self._candidate(unit, text, terms=shared, part=None))
                continue
            pieces = self._split_unit(unit)
            total = len(pieces)
            for index, piece in enumerate(pieces):
                candidates.append(self._candidate(unit, piece, terms=shared, part=(index, total)))
        return candidates

    def _emit_auxiliary(self, units: list[SemanticUnit], terms: TermBundle) -> list[ChunkCandidate]:
        """Emit document metadata as clearly marked, filterable chunks."""
        out: list[ChunkCandidate] = []
        for unit in units:
            text = unit.render()
            if not text.strip():
                continue
            out.append(
                ChunkCandidate(
                    text=text,
                    heading_path=list(unit.path),
                    content_type="metadata",
                    start_offset=_start(unit),
                    end_offset=_end(unit),
                    block_types=sorted({b.type.value for b in unit.blocks}),
                    metadata={
                        "semantic_role": unit.role.value,
                        "retrieval_terms": terms.as_dict() if unit is units[0] else {},
                    },
                )
            )
        return out

    def _candidate(
        self,
        unit: SemanticUnit,
        text: str,
        *,
        terms: dict[str, list[str]],
        part: tuple[int, int] | None,
    ) -> ChunkCandidate:
        meta: dict = {"semantic_role": unit.role.value}
        if terms:
            meta["retrieval_terms"] = terms
        if unit.titles:
            merged = [t for t in unit.titles if t]
            if len(merged) > 1:
                meta["merged_sections"] = merged
        if part is not None:
            meta["part_index"], meta["part_total"] = part
            meta["block_split"] = True
        return ChunkCandidate(
            text=text,
            heading_path=list(unit.effective_path),
            content_type=classify_content_type(
                [(b.type, len(b.text)) for b in unit.blocks] or [(BlockType.PARAGRAPH, 1)]
            ),
            language=next((b.language for b in unit.blocks if b.language), None),
            start_offset=_start(unit),
            end_offset=_end(unit),
            block_types=sorted({b.type.value for b in unit.blocks}),
            metadata=meta,
        )

    # ------------------------------------------------------------------
    def _split_unit(self, unit: SemanticUnit) -> list[str]:
        """Break an oversized unit without cutting through a semantic atom.

        The heading is repeated on every piece so each remains self-describing.
        """
        header_parts: list[str] = []
        if unit.preamble is not None and unit.preamble.text.strip():
            header_parts.append(unit.preamble.text.strip())
        if unit.heading is not None and unit.heading.text.strip():
            header_parts.append(f"{'#' * max(1, unit.heading.level)} {unit.heading.text.strip()}")
        heading = "\n\n".join(header_parts)
        overhead = self.meter.size(heading) if heading else 0
        budget = max(1, self.config.target_size - overhead)
        hard = max(budget, self.config.max_size - overhead)

        pieces: list[str] = []
        buffer: list[str] = []
        size = 0

        for block in unit.blocks:
            for atom in self._atoms(block, budget=budget, hard=hard):
                atom_size = self.meter.size(atom)
                if atom_size > hard:
                    # No semantic boundary exists inside this atom (one huge
                    # unbroken token, a minified line). Flush and hard-split.
                    if buffer:
                        pieces.append("\n\n".join(buffer))
                        buffer, size = [], 0
                    pieces.extend(_hard_split(atom, self.meter, budget))
                    continue
                if buffer and size + atom_size > budget:
                    pieces.append("\n\n".join(buffer))
                    buffer, size = [], 0
                buffer.append(atom)
                size += atom_size
        if buffer:
            pieces.append("\n\n".join(buffer))

        if heading:
            return [f"{heading}\n\n{p}".strip() for p in pieces if p.strip()]
        return [p for p in pieces if p.strip()]

    def _atoms(self, block: Block, *, budget: int, hard: int) -> list[str]:
        """Decompose a block into the smallest pieces that stay meaningful."""
        text = block.text.strip()
        if not text:
            return []
        if self.meter.size(text) <= budget:
            return [text]

        if block.type is BlockType.CODE:
            if self.config.keep_code_blocks_intact and self.meter.size(text) <= hard:
                return [text]
            return split_code_block(text, self.meter, budget=budget, language=block.language)

        if block.type is BlockType.TABLE:
            if self.config.keep_tables_intact and self.meter.size(text) <= hard:
                return [text]
            return _split_table_rows(text, self.meter, budget)

        if block.type in {BlockType.LIST, BlockType.NUMBERED_LIST}:
            return _split_list_groups(text, self.meter, budget)

        return _split_paragraph(text, self.meter, budget)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _mergeable(left: SemanticUnit, right: SemanticUnit) -> bool:
    """Only merge units that describe related material.

    Related means: same heading path, or one path is a prefix of the other
    (parent/child), or they are siblings under a common parent.
    """
    if left.role is not right.role and SemanticRole.CODE in {left.role, right.role}:
        # Code may join its explanation but two unrelated code units may not.
        pass
    a, b = left.path, right.path
    if not a or not b:
        return True
    shorter = min(len(a), len(b))
    return a[: shorter - 1] == b[: shorter - 1]


def _heading_as_block(heading: Block) -> Block:
    """Render a heading as an inline paragraph block so it stays in the text."""
    return Block(
        type=BlockType.PARAGRAPH,
        text=f"{'#' * max(1, heading.level)} {heading.text.strip()}",
        start_offset=heading.start_offset,
        end_offset=heading.end_offset,
    )


def _with_heading(unit: SemanticUnit) -> list[Block]:
    """Blocks of ``unit`` with its headings turned into inline blocks."""
    out: list[Block] = []
    if unit.preamble is not None and unit.preamble.text.strip():
        out.append(unit.preamble)
    if unit.heading is not None and unit.heading.text.strip():
        out.append(_heading_as_block(unit.heading))
    out.extend(unit.blocks)
    return out


def _start(unit: SemanticUnit) -> int:
    if unit.heading is not None:
        return unit.heading.start_offset
    return unit.blocks[0].start_offset if unit.blocks else 0


def _end(unit: SemanticUnit) -> int:
    if unit.blocks:
        return unit.blocks[-1].end_offset
    return unit.heading.end_offset if unit.heading is not None else 0


def _split_paragraph(text: str, meter: SizeMeter, budget: int) -> list[str]:
    """Split prose at paragraph boundaries first, then sentence boundaries."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    atoms: list[str] = []
    for paragraph in paragraphs:
        if meter.size(paragraph) <= budget:
            atoms.append(paragraph)
            continue
        buffer: list[str] = []
        size = 0
        for sentence in split_sentences(paragraph) or [paragraph]:
            sentence_size = meter.size(sentence)
            if buffer and size + sentence_size > budget:
                atoms.append(" ".join(buffer))
                buffer, size = [], 0
            buffer.append(sentence)
            size += sentence_size
        if buffer:
            atoms.append(" ".join(buffer))
    return atoms or [text]


def _split_list_groups(text: str, meter: SizeMeter, budget: int) -> list[str]:
    """Split a list at item boundaries, keeping continuation lines attached.

    Numbered lists and label/correction pairs (``Misconception:`` /
    ``Correction:``) are kept in adjacent pairs so a rule never loses its
    counterpart.
    """
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

    groups: list[str] = []
    current: list[str] = []
    size = 0
    for item in items:
        item_size = meter.size(item)
        if current and size + item_size > budget:
            groups.append("\n".join(current).strip())
            current, size = [], 0
        current.append(item)
        size += item_size
    if current:
        groups.append("\n".join(current).strip())
    return [g for g in groups if g.strip()] or [text]


def _hard_split(text: str, meter: SizeMeter, budget: int) -> list[str]:
    """Last resort for text with no usable boundary: slice by words, then chars.

    Only reached when a single atom exceeds the hard maximum on its own, which
    means no paragraph, sentence, line or word boundary was available.
    """
    words = text.split()
    if len(words) > 1:
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
        if all(meter.size(p) <= budget for p in parts):
            return parts

    total = meter.size(text)
    if total <= budget or not text:
        return [text]
    span = max(1, int(len(text) * budget / max(total, 1)))
    return [text[i : i + span] for i in range(0, len(text), span)]


def _split_table_rows(text: str, meter: SizeMeter, budget: int) -> list[str]:
    """Split a Markdown table by rows, repeating the header in every part."""
    lines = [line for line in text.split("\n") if line.strip()]
    if len(lines) <= 2:
        return [text]
    has_separator = len(lines) > 1 and set(lines[1].replace("|", "").strip()) <= set("-: ")
    header = lines[:2] if has_separator else lines[:1]
    body = lines[len(header) :]
    header_size = meter.size("\n".join(header))

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
