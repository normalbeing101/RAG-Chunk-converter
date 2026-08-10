"""Request/response models for the REST API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ragforge.models.chunk import Chunk
from ragforge.models.config import ForgeConfig, SizeUnit, Strategy
from ragforge.models.result import Statistics


class ProcessOptions(BaseModel):
    """Chunking options accepted by ``POST /process``."""

    model_config = ConfigDict(extra="forbid")

    strategy: Strategy = Strategy.SEMANTIC
    target_size: int = Field(default=500, gt=0)
    min_size: int = Field(default=100, ge=0)
    max_size: int = Field(default=800, gt=0)
    overlap: float = Field(default=75, ge=0)
    unit: SizeUnit = SizeUnit.TOKENS
    clean: bool = True
    deduplicate: bool = True
    context_prefix: bool = True
    quality: bool = True
    separate_retrieval_metadata: bool = True
    """Route keyword/tag/alias sections into structured metadata fields."""

    def to_config(self, base: ForgeConfig | None = None) -> ForgeConfig:
        config = (base or ForgeConfig()).model_copy(deep=True)
        config.chunking = type(config.chunking)(
            **{
                **config.chunking.model_dump(),
                "strategy": self.strategy,
                "target_size": self.target_size,
                "min_size": self.min_size,
                "max_size": self.max_size,
                "overlap": self.overlap,
                "unit": self.unit,
            }
        )
        config.cleaning.enabled = self.clean
        config.deduplication.enabled = self.deduplicate
        config.context.include_context_prefix = self.context_prefix
        config.quality.enabled = self.quality
        config.semantics.enabled = self.separate_retrieval_metadata
        config.semantics.separate_retrieval_metadata = self.separate_retrieval_metadata
        return config


class ProcessTextRequest(BaseModel):
    """JSON body for processing raw text."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    title: str = "Pasted document"
    source: str = "inline"
    options: ProcessOptions = Field(default_factory=ProcessOptions)


class JobSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: str
    chunks: int = 0
    documents: int = 0
    created_at: float = 0.0
    title: str = ""
    source: str = ""
    error: str | None = None


class JobResponse(JobSummary):
    """Returned by ``POST /process``."""

    statistics: Statistics | None = None


class ChunkPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    total: int
    offset: int
    limit: int
    chunks: list[Chunk]


class PreviewSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    chunk_index: int
    start: int
    end: int
    section: str | None = None
    content_type: str = "text"


class PreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    documents: list[dict[str, Any]]


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "ok"
    version: str
    jobs: int = 0


class FormatsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_formats: list[str]
    output_formats: list[str]
    strategies: list[str]
    units: list[str]
