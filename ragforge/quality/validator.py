"""Dataset-level validation.

Checks a produced chunk collection for structural problems that would hurt a
downstream RAG system: missing IDs, broken neighbour links, empty content,
oversized chunks and excessive duplication.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ragforge.models.chunk import Chunk, QualityFlag
from ragforge.models.config import ForgeConfig


@dataclass(slots=True)
class ValidationIssue:
    level: str
    code: str
    message: str
    chunk_id: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "chunk_id": self.chunk_id,
        }


@dataclass(slots=True)
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)
    checked: int = 0

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, level: str, code: str, message: str, chunk_id: str | None = None) -> None:
        self.issues.append(ValidationIssue(level, code, message, chunk_id))

    def summary(self) -> dict[str, int]:
        counter = Counter(issue.code for issue in self.issues)
        return dict(counter)


class DatasetValidator:
    """Validates a list of chunks against the active configuration."""

    def __init__(self, config: ForgeConfig | None = None) -> None:
        self.config = config or ForgeConfig()

    def validate(self, chunks: list[Chunk]) -> ValidationReport:
        report = ValidationReport(checked=len(chunks))
        if not chunks:
            report.add("warning", "EMPTY_DATASET", "The dataset contains no chunks.")
            return report

        ids = [c.id for c in chunks]
        duplicates = [cid for cid, count in Counter(ids).items() if count > 1]
        for cid in duplicates:
            report.add("error", "DUPLICATE_ID", f"Chunk id '{cid}' appears more than once.", cid)

        known = set(ids)
        max_size = self.config.chunking.max_size
        min_size = self.config.chunking.min_size

        for chunk in chunks:
            if not chunk.id:
                report.add("error", "MISSING_ID", "A chunk has an empty identifier.")
            if not chunk.content.strip():
                report.add("error", "EMPTY_CONTENT", "Chunk content is empty.", chunk.id)
            meta = chunk.metadata
            if not meta.document_id:
                report.add("warning", "MISSING_DOCUMENT_ID", "Chunk has no document id.", chunk.id)
            if meta.previous_chunk and meta.previous_chunk not in known:
                report.add(
                    "error",
                    "BROKEN_NEIGHBOR",
                    f"previous_chunk '{meta.previous_chunk}' does not exist.",
                    chunk.id,
                )
            if meta.next_chunk and meta.next_chunk not in known:
                report.add(
                    "error",
                    "BROKEN_NEIGHBOR",
                    f"next_chunk '{meta.next_chunk}' does not exist.",
                    chunk.id,
                )
            if meta.size > max_size:
                report.add(
                    "warning",
                    "OVERSIZED",
                    f"Chunk exceeds max_size ({meta.size} > {max_size}).",
                    chunk.id,
                )
            if meta.size < min_size:
                report.add(
                    "warning",
                    "UNDERSIZED",
                    f"Chunk is below min_size ({meta.size} < {min_size}).",
                    chunk.id,
                )
            if chunk.quality:
                for flag in chunk.quality.flags:
                    if flag in {QualityFlag.CODE_SPLIT, QualityFlag.BROKEN_SENTENCE}:
                        report.add("warning", flag.value, f"Chunk flagged {flag.value}.", chunk.id)

        duplicate_ratio = sum(1 for c in chunks if c.metadata.duplicate_of) / len(chunks)
        if duplicate_ratio > 0.25:
            report.add(
                "warning",
                "HIGH_DUPLICATION",
                f"{duplicate_ratio:.0%} of chunks are duplicates - consider cleaning the corpus.",
            )
        return report
