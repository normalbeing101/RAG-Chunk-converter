"""Duplicate detection."""

from ragforge.deduplication.deduplicator import Deduplicator, DedupResult
from ragforge.deduplication.minhash import LshIndex, MinHash, exact_jaccard, jaccard, shingles

__all__ = [
    "DedupResult",
    "Deduplicator",
    "LshIndex",
    "MinHash",
    "exact_jaccard",
    "jaccard",
    "shingles",
]
