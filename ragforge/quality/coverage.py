"""Information-loss detection.

Answers one question precisely: *did every piece of the source document end up
somewhere?* "Somewhere" means one of four accountable destinations:

``knowledge``
    Text that became part of a retrievable knowledge chunk.
``metadata``
    Document front-matter kept as a role-marked chunk.
``retrieval_terms``
    Keyword / alias / tag text converted into structured metadata fields.
``dropped``
    Anything else - this is the number that must stay at zero.

Accounting is done on **normalised block text**, not raw offsets, because
chunkers legitimately reflow whitespace and repeat headings. A source block is
considered accounted for when a sufficient fraction of its content words appear
in some chunk or in the harvested term set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ragforge.models.chunk import Chunk
from ragforge.models.document import Block, BlockType, Document

_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
_COVERAGE_THRESHOLD = 0.6
"""A block counts as preserved when this share of its words is present."""
_MIN_WORDS_TO_TRACK = 3


@dataclass(slots=True)
class BlockDisposition:
    """What happened to one source block."""

    index: int
    block_type: str
    heading_path: list[str]
    words: int
    chars: int
    destination: str
    coverage: float
    preview: str = ""


@dataclass(slots=True)
class CoverageReport:
    """Whole-document information-loss accounting."""

    document_id: str = ""
    source: str = ""
    source_chars: int = 0
    source_words: int = 0
    source_tokens: int = 0
    blocks_total: int = 0
    blocks_by_destination: dict[str, int] = field(default_factory=dict)
    words_by_destination: dict[str, int] = field(default_factory=dict)
    dropped: list[BlockDisposition] = field(default_factory=list)
    chunk_chars: int = 0
    duplicated_chars: int = 0

    @property
    def dropped_words(self) -> int:
        return self.words_by_destination.get("dropped", 0)

    @property
    def retention(self) -> float:
        """Fraction of source words that reached an accountable destination."""
        if not self.source_words:
            return 1.0
        return 1.0 - self.dropped_words / self.source_words

    @property
    def ok(self) -> bool:
        return not self.dropped

    def summary(self) -> dict[str, object]:
        return {
            "document_id": self.document_id,
            "source": self.source,
            "source_chars": self.source_chars,
            "source_words": self.source_words,
            "source_tokens": self.source_tokens,
            "chunk_chars": self.chunk_chars,
            "duplicated_chars": self.duplicated_chars,
            "blocks_total": self.blocks_total,
            "blocks_by_destination": dict(self.blocks_by_destination),
            "words_by_destination": dict(self.words_by_destination),
            "retention": round(self.retention, 4),
            "dropped_blocks": len(self.dropped),
        }


class CoverageAuditor:
    """Verifies that no meaningful source text disappeared during chunking."""

    def __init__(self, *, threshold: float = _COVERAGE_THRESHOLD) -> None:
        self.threshold = threshold

    def audit(
        self,
        document: Document,
        chunks: list[Chunk],
        *,
        tokenizer=None,
    ) -> CoverageReport:
        report = CoverageReport(
            document_id=document.id,
            source=document.source,
            source_chars=len(document.content),
            source_words=len(_WORD_RE.findall(document.content)),
        )
        if tokenizer is not None:
            report.source_tokens = tokenizer.count_tokens(document.content)

        doc_chunks = [c for c in chunks if c.metadata.document_id == document.id]
        report.chunk_chars = sum(len(c.content) for c in doc_chunks)
        report.duplicated_chars = sum(c.metadata.overlap_prefix_chars for c in doc_chunks)

        knowledge_words = _word_multiset(" ".join(c.content for c in doc_chunks if c.is_knowledge))
        metadata_words = _word_multiset(
            " ".join(c.content for c in doc_chunks if not c.is_knowledge)
        )
        term_words = _word_multiset(
            " ".join(
                term
                for c in doc_chunks
                for term in (*c.retrieval.all_terms(), *c.retrieval.questions)
            )
        )

        blocks = document.blocks
        report.blocks_total = len(blocks)
        for index, block in enumerate(blocks):
            disposition = self._classify_block(
                index, block, knowledge_words, metadata_words, term_words
            )
            report.blocks_by_destination[disposition.destination] = (
                report.blocks_by_destination.get(disposition.destination, 0) + 1
            )
            report.words_by_destination[disposition.destination] = (
                report.words_by_destination.get(disposition.destination, 0) + disposition.words
            )
            if disposition.destination == "dropped":
                report.dropped.append(disposition)
        return report

    # ------------------------------------------------------------------
    def _classify_block(
        self,
        index: int,
        block: Block,
        knowledge: set[str],
        metadata: set[str],
        terms: set[str],
    ) -> BlockDisposition:
        words = _WORD_RE.findall(block.text)
        base = BlockDisposition(
            index=index,
            block_type=block.type.value,
            heading_path=list(block.heading_path),
            words=len(words),
            chars=len(block.text),
            destination="knowledge",
            coverage=1.0,
            preview=" ".join(block.text.split())[:100],
        )
        if len(words) < _MIN_WORDS_TO_TRACK:
            # Too small to measure reliably; treat separators as accounted for.
            base.destination = (
                "knowledge" if block.type is not BlockType.HORIZONTAL_RULE else "ignored"
            )
            return base

        lowered = {w.casefold() for w in words}
        for destination, vocabulary in (
            ("knowledge", knowledge),
            ("metadata", metadata),
            ("retrieval_terms", terms),
        ):
            if not vocabulary:
                continue
            coverage = len(lowered & vocabulary) / len(lowered)
            if coverage >= self.threshold:
                base.destination = destination
                base.coverage = round(coverage, 3)
                return base

        best = max(
            (
                len(lowered & vocab) / len(lowered) if vocab else 0.0
                for vocab in (knowledge, metadata, terms)
            ),
            default=0.0,
        )
        base.destination = "dropped"
        base.coverage = round(best, 3)
        return base


def _word_multiset(text: str) -> set[str]:
    return {w.casefold() for w in _WORD_RE.findall(text)}
