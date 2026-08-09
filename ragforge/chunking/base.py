"""Chunker interface and shared primitives."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ragforge.models.config import ChunkingConfig, SizeUnit
from ragforge.models.document import Block, BlockType, Document
from ragforge.utils.tokenizer import Tokenizer, get_tokenizer


@dataclass(slots=True)
class ChunkCandidate:
    """Intermediate chunk produced by a strategy, before enrichment."""

    text: str
    heading_path: list[str] = field(default_factory=list)
    content_type: str = "text"
    language: str | None = None
    start_offset: int = 0
    end_offset: int = 0
    block_types: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def section(self) -> str | None:
        return self.heading_path[-1] if self.heading_path else None

    @property
    def parent_section(self) -> str | None:
        return self.heading_path[-2] if len(self.heading_path) >= 2 else None


class SizeMeter:
    """Measures text in the unit configured for a run."""

    __slots__ = ("_tokenizer", "unit")

    def __init__(
        self, unit: SizeUnit = SizeUnit.TOKENS, tokenizer: Tokenizer | None = None
    ) -> None:
        self.unit = unit
        self._tokenizer = tokenizer or get_tokenizer()

    def size(self, text: str) -> int:
        return self._tokenizer.count(text, self.unit)

    def tokens(self, text: str) -> int:
        return self._tokenizer.count_tokens(text)

    def fits(self, text: str, limit: int) -> bool:
        return self.size(text) <= limit

    @property
    def tokenizer(self) -> Tokenizer:
        return self._tokenizer


class Chunker(ABC):
    """Base class for chunking strategies."""

    name: str = "base"

    def __init__(
        self, config: ChunkingConfig | None = None, meter: SizeMeter | None = None
    ) -> None:
        self.config = config or ChunkingConfig()
        self.meter = meter or SizeMeter(self.config.unit, get_tokenizer(self.config.tokenizer))

    @abstractmethod
    def chunk(self, document: Document) -> list[ChunkCandidate]:
        """Produce chunk candidates for ``document``."""

    # -- shared helpers -------------------------------------------------
    def blocks_of(self, document: Document) -> list[Block]:
        if document.structure is not None:
            return document.structure.blocks
        from ragforge.preprocessing.structure import StructureAnalyzer

        return StructureAnalyzer().analyze_text(document.content).blocks

    def content_type_for(self, blocks: list[Block]) -> str:
        """Dominant content type of a set of blocks.

        Shared by every strategy so that a chunk is labelled identically
        regardless of how it was assembled.
        """
        from ragforge.chunking.structural import classify_content_type

        return classify_content_type(
            [(b.type, len(b.text)) for b in blocks if not b.is_heading]
            or [(b.type, len(b.text)) for b in blocks]
        )

    def language_for(self, blocks: list[Block]) -> str | None:
        for block in blocks:
            if block.type is BlockType.CODE and block.language:
                return block.language
        return None
