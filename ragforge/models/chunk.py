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
    # -- retrieval-usefulness flags ------------------------------------
    HEADING_ONLY = "HEADING_ONLY"
    """The chunk carries a heading and no substantive body."""
    METADATA_ONLY = "METADATA_ONLY"
    """The chunk is document front-matter, not knowledge."""
    KEYWORD_HEAVY = "KEYWORD_HEAVY"
    """Dominated by short verb-free segments - a keyword dump."""
    ALIAS_HEAVY = "ALIAS_HEAVY"
    """Dominated by near-synonyms of a single term."""
    ORPHANED_CONTEXT = "ORPHANED_CONTEXT"
    """An example or code block detached from the concept it illustrates."""
    FRAGMENTED_LIST = "FRAGMENTED_LIST"
    """A list was cut across a chunk boundary."""
    FRAGMENTED_TABLE = "FRAGMENTED_TABLE"
    """A table lost its header or was cut mid-row."""
    OVERSIZED = "OVERSIZED"
    UNDERSIZED = "UNDERSIZED"


class ChunkQuality(BaseModel):
    """Heuristic, LLM-free quality metrics for a single chunk."""

    model_config = ConfigDict(extra="forbid")

    quality_score: float = 0.0
    length_score: float = 0.0
    coherence_score: float = 0.0
    context_score: float = 0.0
    information_score: float = 0.0
    retrieval_score: float = 0.0
    """How useful this chunk is as an answer to a question."""
    flags: list[QualityFlag] = Field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return bool(self.flags)


class RetrievalMetadata(BaseModel):
    """Search-support terms kept separate from the embedded knowledge text.

    These come from keyword / tag / alias / entity sections of the source. They
    are preserved verbatim so nothing is lost, but they are *not* concatenated
    into ``content``, because embedding hundreds of near-synonyms produces a
    vector that matches everything and explains nothing.
    """

    model_config = ConfigDict(extra="forbid")

    keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    related_concepts: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    """Questions the surrounding knowledge answers - strong query-side signal."""

    def is_empty(self) -> bool:
        return not any(
            (
                self.keywords,
                self.tags,
                self.aliases,
                self.entities,
                self.related_concepts,
                self.questions,
            )
        )

    def merge(self, other: RetrievalMetadata, *, limit: int = 512) -> None:
        """Absorb another instance, preserving order and dropping repeats."""
        for name in ("keywords", "tags", "aliases", "entities", "related_concepts", "questions"):
            current: list[str] = getattr(self, name)
            seen = {item.casefold() for item in current}
            for item in getattr(other, name):
                key = item.casefold()
                if key not in seen and len(current) < limit:
                    seen.add(key)
                    current.append(item)

    def all_terms(self) -> list[str]:
        return [
            *self.tags,
            *self.keywords,
            *self.aliases,
            *self.entities,
            *self.related_concepts,
        ]


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
    semantic_role: str = "knowledge"
    """See :class:`ragforge.semantics.SemanticRole`."""
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
    retrieval: RetrievalMetadata = Field(default_factory=RetrievalMetadata)
    quality: ChunkQuality | None = None
    context_prefix: str | None = None
    embedding: list[float] | None = None

    @property
    def document_id(self) -> str:
        return self.metadata.document_id

    @property
    def role(self) -> str:
        return self.metadata.semantic_role

    @property
    def is_knowledge(self) -> bool:
        from ragforge.semantics.roles import SemanticRole

        try:
            return SemanticRole(self.metadata.semantic_role).is_knowledge
        except ValueError:
            return True

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
            "semantic_role": meta.semantic_role,
            "keywords": "; ".join(self.retrieval.all_terms()[:40]),
        }

    def to_record(self, *, include_quality: bool = True) -> dict[str, Any]:
        """Canonical JSON/JSONL record."""
        record: dict[str, Any] = {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata.model_dump(exclude_none=False),
        }
        if not self.retrieval.is_empty():
            record["retrieval"] = self.retrieval.model_dump(exclude_defaults=True)
        if self.context_prefix:
            record["context_prefix"] = self.context_prefix
        if include_quality and self.quality is not None:
            record["quality"] = self.quality.model_dump()
        if self.embedding is not None:
            record["embedding"] = self.embedding
        return record
