"""Duplicate and near-duplicate chunk detection.

Two passes:

1. **Exact** - SHA-256 of whitespace-normalised, case-folded content.
2. **Near** - MinHash signatures + LSH candidate generation, then an exact
   Jaccard check on the shingle sets to avoid false positives.

Duplicates are flagged by default (``action: flag``) so that no information is
silently lost; ``action: drop`` removes them from the dataset.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ragforge.deduplication.minhash import LshIndex, MinHash, exact_jaccard, shingles
from ragforge.models.chunk import Chunk, QualityFlag
from ragforge.models.config import DeduplicationConfig
from ragforge.utils.ids import content_hash


@dataclass(slots=True)
class DedupResult:
    """Outcome of a deduplication pass."""

    chunks: list[Chunk]
    exact_duplicates: int = 0
    near_duplicates: int = 0
    removed: int = 0
    pairs: list[tuple[str, str, float]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.exact_duplicates + self.near_duplicates


class Deduplicator:
    """Detects duplicated chunks across a corpus."""

    def __init__(self, config: DeduplicationConfig | None = None) -> None:
        self.config = config or DeduplicationConfig()

    def run(self, chunks: list[Chunk]) -> DedupResult:
        cfg = self.config
        if not cfg.enabled or cfg.method == "off" or len(chunks) < 2:
            return DedupResult(chunks=chunks)

        if cfg.scope == "document":
            result = DedupResult(chunks=[])
            grouped: dict[str, list[Chunk]] = {}
            for chunk in chunks:
                grouped.setdefault(chunk.metadata.document_id, []).append(chunk)
            ordered: list[Chunk] = []
            for group in grouped.values():
                sub = self._run_group(group)
                ordered.extend(sub.chunks)
                result.exact_duplicates += sub.exact_duplicates
                result.near_duplicates += sub.near_duplicates
                result.removed += sub.removed
                result.pairs.extend(sub.pairs)
            # Restore the original ordering.
            index = {chunk.id: position for position, chunk in enumerate(chunks)}
            result.chunks = sorted(ordered, key=lambda c: index.get(c.id, 0))
            return result

        return self._run_group(chunks)

    # ------------------------------------------------------------------
    def _run_group(self, chunks: list[Chunk]) -> DedupResult:
        cfg = self.config
        result = DedupResult(chunks=[])
        seen_hashes: dict[str, str] = {}
        eligible: list[Chunk] = []

        # Pass 1: exact duplicates.
        for chunk in chunks:
            if len(chunk.content.strip()) < cfg.min_length:
                continue
            digest = content_hash(chunk.content)
            original = seen_hashes.get(digest)
            if original is None:
                seen_hashes[digest] = chunk.id
                eligible.append(chunk)
                continue
            self._mark(chunk, original, 1.0, QualityFlag.DUPLICATE)
            result.exact_duplicates += 1
            result.pairs.append((chunk.id, original, 1.0))

        # Pass 2: near duplicates via MinHash + LSH.
        if cfg.method == "minhash" and cfg.similarity_threshold < 1.0:
            minhash = MinHash(num_perm=cfg.num_permutations)
            index = LshIndex(num_perm=cfg.num_permutations, threshold=cfg.similarity_threshold)
            signatures: dict[str, tuple[int, ...]] = {}
            shingle_sets: dict[str, set[int]] = {}

            for chunk in eligible:
                if chunk.metadata.duplicate_of:
                    continue
                tokens = shingles(chunk.content, cfg.shingle_size)
                if not tokens:
                    continue
                signature = minhash.signature(tokens)
                for candidate_id in index.query(signature):
                    similarity = exact_jaccard(tokens, shingle_sets[candidate_id])
                    if similarity >= cfg.similarity_threshold:
                        self._mark(chunk, candidate_id, similarity, QualityFlag.NEAR_DUPLICATE)
                        result.near_duplicates += 1
                        result.pairs.append((chunk.id, candidate_id, round(similarity, 4)))
                        break
                if not chunk.metadata.duplicate_of:
                    index.add(chunk.id, signature)
                    signatures[chunk.id] = signature
                    shingle_sets[chunk.id] = tokens

        if cfg.action == "drop":
            kept = [c for c in chunks if not c.metadata.duplicate_of]
            result.removed = len(chunks) - len(kept)
            result.chunks = kept
        else:
            result.chunks = chunks
        return result

    @staticmethod
    def _mark(chunk: Chunk, original_id: str, similarity: float, flag: QualityFlag) -> None:
        chunk.metadata.duplicate_of = original_id
        chunk.metadata.similarity = round(similarity, 4)
        chunk.metadata.extra["duplicate_kind"] = flag.value
