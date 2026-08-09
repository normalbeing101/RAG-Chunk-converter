"""Chunk model: the unit produced by the chunking engine."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class QualityFlag(str, Enum):
    """Warnings attached to chunks that may hurt retrieval quality."""

    TOO_SHORT = "TOO_SHORT"
    TOO_LONG = "TOO_LONG"
    LOW_CONTEXT = "LOW_CONTEXT"
    DUPLICATE = "DUPLICATE"
    NEAR_DUPLICATE = "NEAR_DUPLICATE"
    BROKEN_SENTENCE = "BROKEN_SENTENCE"
    CODE_SPLIT = "CODE_SPLIT"
    LOW_INFORMATION = "LOW_INFORMATION"
    MIXED_TOPICS = "MIXED_TOPICS"


class ChunkQuality(BaseModel):
    """Heuristic, LLM-free quality metrics for a single chunk."""

    model_config = ConfigDict(extra="forbid")

    quality_score: float = 0.0
    length_score: float = 0.0
    coherence_score: float = 0.0
    context_score: float = 0.0
    information_score: float = 0.0
    flags: list[QualityFlag] = Field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return bool(self.flags)


class ChunkMetadata(BaseModel):
    """Contextual metadata carried by every chunk."""

    model_config = ConfigDict(extra="allow")

    document_id: str = ""
    title: str = ""
    source: str = ""
    section: str | None = None
    parent_section: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    content_type: str = "text"
    language: str | None = None
    chunk_index: int = 0
    total_chunks: int = 0
    strategy: str = ""
    unit: str = "tokens"
    size: int = 0
    char_count: int = 0
    word_count: int = 0
    token_count: int = 0
    sentence_count: int = 0
    start_offset: int = 0
    end_offset: int = 0
    overlap_prefix_chars: int = 0
    parent_id: str | None = None
    previous_chunk: str | None = None
    next_chunk: str | None = None
    duplicate_of: str | None = None
    similarity: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    """A retrieval-ready piece of a document."""

    model_config = ConfigDict(extra="forbid")

    id: str
    content: str
    metadata: ChunkMetadata = Field(default_factory=ChunkMetadata)
    quality: ChunkQuality | None = None
    context_prefix: str | None = None
    embedding: list[float] | None = None

    @property
    def document_id(self) -> str:
        return self.metadata.document_id

    @property
    def text_for_embedding(self) -> str:
        """Content prefixed with contextual header when enrichment is enabled."""
        if self.context_prefix:
            return f"{self.context_prefix}\n\n{self.content}"
        return self.content

    def flat_record(self) -> dict[str, Any]:
        """Flat dict used for CSV export and table rendering."""
        meta = self.metadata
        return {
            "id": self.id,
            "document_id": meta.document_id,
            "content": self.content,
            "title": meta.title,
            "section": meta.section or "",
            "source": meta.source,
            "chunk_index": meta.chunk_index,
            "content_type": meta.content_type,
        }

    def to_record(self, *, include_quality: bool = True) -> dict[str, Any]:
        """Canonical JSON/JSONL record."""
        record: dict[str, Any] = {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata.model_dump(exclude_none=False),
        }
        if self.context_prefix:
            record["context_prefix"] = self.context_prefix
        if include_quality and self.quality is not None:
            record["quality"] = self.quality.model_dump()
        if self.embedding is not None:
            record["embedding"] = self.embedding
        return record
