"""Sentence-aware chunking.

Guarantees that chunk boundaries always coincide with sentence boundaries.
Sections and paragraphs are still respected: sentences from different sections
are never mixed into the same chunk.
"""

from __future__ import annotations

from ragforge.chunking.base import ChunkCandidate, Chunker, SizeMeter
from ragforge.chunking.structural import StructuralChunker
from ragforge.models.config import ChunkingConfig
from ragforge.models.document import Document


class SentenceChunker(Chunker):
    name = "sentence"

    def __init__(
        self, config: ChunkingConfig | None = None, meter: SizeMeter | None = None
    ) -> None:
        super().__init__(config, meter)
        self._delegate = StructuralChunker(self.config, self.meter, mode="sentence")

    def chunk(self, document: Document) -> list[ChunkCandidate]:
        return self._delegate.chunk(document)
