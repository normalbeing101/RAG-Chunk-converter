"""Pipeline result and statistics models."""

from __future__ import annotations

import statistics as pystats
from collections import Counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ragforge.models.chunk import Chunk


class DocumentReport(BaseModel):
    """Per-document processing summary."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    title: str
    source: str
    characters: int = 0
    tokens: int = 0
    blocks: int = 0
    chunks: int = 0
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class Statistics(BaseModel):
    """Aggregate statistics over a processing run."""

    model_config = ConfigDict(extra="forbid")

    project: str = ""
    strategy: str = ""
    unit: str = "tokens"
    documents: int = 0
    failed_documents: int = 0
    original_characters: int = 0
    original_tokens: int = 0
    total_chunks: int = 0
    total_chunk_tokens: int = 0
    average_size: float = 0.0
    median_size: float = 0.0
    min_size: int = 0
    max_size: int = 0
    p95_size: float = 0.0
    stdev_size: float = 0.0
    duplicates: int = 0
    warnings: int = 0
    average_quality: float = 0.0
    size_histogram: list[dict[str, Any]] = Field(default_factory=list)
    chunks_by_document: dict[str, int] = Field(default_factory=dict)
    chunks_by_section: dict[str, int] = Field(default_factory=dict)
    chunks_by_content_type: dict[str, int] = Field(default_factory=dict)
    flag_counts: dict[str, int] = Field(default_factory=dict)
    elapsed_seconds: float = 0.0

    @classmethod
    def from_chunks(
        cls,
        chunks: list[Chunk],
        *,
        reports: list[DocumentReport] | None = None,
        project: str = "",
        strategy: str = "",
        unit: str = "tokens",
        elapsed: float = 0.0,
        bins: int = 12,
    ) -> Statistics:
        reports = reports or []
        sizes = [c.metadata.size for c in chunks] or [0]
        flag_counter: Counter[str] = Counter()
        duplicates = 0
        warned = 0
        quality_scores: list[float] = []
        for chunk in chunks:
            if chunk.quality:
                quality_scores.append(chunk.quality.quality_score)
                if chunk.quality.flags:
                    warned += 1
                for flag in chunk.quality.flags:
                    flag_counter[flag.value] += 1
            if chunk.metadata.duplicate_of:
                duplicates += 1

        ok_reports = [r for r in reports if r.ok]
        return cls(
            project=project,
            strategy=strategy,
            unit=unit,
            documents=len(ok_reports),
            failed_documents=len(reports) - len(ok_reports),
            original_characters=sum(r.characters for r in ok_reports),
            original_tokens=sum(r.tokens for r in ok_reports),
            total_chunks=len(chunks),
            total_chunk_tokens=sum(c.metadata.token_count for c in chunks),
            average_size=round(pystats.fmean(sizes), 2),
            median_size=round(pystats.median(sizes), 2),
            min_size=min(sizes),
            max_size=max(sizes),
            p95_size=round(_percentile(sizes, 95), 2),
            stdev_size=round(pystats.pstdev(sizes), 2) if len(sizes) > 1 else 0.0,
            duplicates=duplicates,
            warnings=warned,
            average_quality=round(pystats.fmean(quality_scores), 4) if quality_scores else 0.0,
            size_histogram=_histogram(sizes, bins=bins),
            chunks_by_document=dict(
                Counter(c.metadata.title or c.metadata.document_id for c in chunks)
            ),
            chunks_by_section=dict(Counter(c.metadata.section or "(no section)" for c in chunks)),
            chunks_by_content_type=dict(Counter(c.metadata.content_type for c in chunks)),
            flag_counts=dict(flag_counter),
            elapsed_seconds=round(elapsed, 3),
        )


class ForgeResult(BaseModel):
    """Everything produced by a pipeline run."""

    model_config = ConfigDict(extra="forbid")

    chunks: list[Chunk] = Field(default_factory=list)
    reports: list[DocumentReport] = Field(default_factory=list)
    statistics: Statistics = Field(default_factory=Statistics)
    outputs: list[str] = Field(default_factory=list)

    @property
    def failed(self) -> list[DocumentReport]:
        return [r for r in self.reports if not r.ok]


def _percentile(values: list[int], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (percent / 100) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _histogram(values: list[int], *, bins: int = 12) -> list[dict[str, Any]]:
    if not values:
        return []
    low, high = min(values), max(values)
    if low == high:
        return [{"start": low, "end": high, "count": len(values)}]
    bins = max(1, bins)
    width = (high - low) / bins
    counts = [0] * bins
    for value in values:
        index = min(int((value - low) / width), bins - 1)
        counts[index] += 1
    return [
        {
            "start": round(low + i * width, 2),
            "end": round(low + (i + 1) * width, 2),
            "count": count,
        }
        for i, count in enumerate(counts)
    ]
