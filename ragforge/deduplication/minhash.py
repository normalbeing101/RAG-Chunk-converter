"""Dependency-free MinHash + LSH implementation.

Used to find near-duplicate chunks in roughly linear time instead of the naive
O(n^2) pairwise comparison. Signatures are built from character/word shingles
hashed with a family of 64-bit permutations derived from a single SHA-256 seed.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Iterable

_MASK64 = (1 << 64) - 1
_MAX_HASH = (1 << 32) - 1
_WORD_RE = re.compile(r"\w+", re.UNICODE)
# Shingles used per chunk when building a signature. Capping keeps signature
# cost bounded for very large chunks; exact verification still uses the full
# shingle set, so this only affects candidate generation.
_MAX_SHINGLES = 128


def shingles(text: str, size: int = 5) -> set[int]:
    """Hashed word shingles of ``size`` words (falls back to characters)."""
    words = _WORD_RE.findall(text.casefold())
    grams: Iterable[str]
    if len(words) >= size:
        grams = (" ".join(words[i : i + size]) for i in range(len(words) - size + 1))
    elif words:
        grams = (" ".join(words),)
    else:
        cleaned = text.strip().casefold()
        if not cleaned:
            return set()
        grams = (cleaned[i : i + size] for i in range(max(1, len(cleaned) - size + 1)))
    return {
        int.from_bytes(hashlib.blake2b(g.encode("utf-8"), digest_size=4).digest(), "big")
        for g in grams
    }


class MinHash:
    """Fixed-size MinHash signature generator.

    Uses a multiply-shift hash family over 64-bit words (mask instead of
    modulo): the classic ``(a*x + b) mod p`` formulation spends most of its
    time in Python's arbitrary-precision division on large corpora.
    """

    __slots__ = ("_a", "_b", "num_perm")

    def __init__(self, num_perm: int = 64, seed: int = 0x5EED) -> None:
        self.num_perm = num_perm
        self._a: list[int] = []
        self._b: list[int] = []
        for i in range(num_perm):
            digest = hashlib.blake2b(f"{seed}:{i}".encode(), digest_size=16).digest()
            # An odd multiplier keeps the map a bijection over 2**64.
            self._a.append(int.from_bytes(digest[:8], "big") | 1)
            self._b.append(int.from_bytes(digest[8:], "big"))

    def signature(self, tokens: set[int]) -> tuple[int, ...]:
        """Minimum hash value per permutation."""
        if not tokens:
            return (_MAX_HASH,) * self.num_perm
        # Deterministic bound on work: the smallest shingle hashes form a
        # stable random sample of the set. Exact verification still uses the
        # complete shingle set, so recall is unaffected in practice.
        token_list = sorted(tokens)[:_MAX_SHINGLES]
        mask = _MASK64
        return tuple(
            min([(a * token + b) & mask for token in token_list]) >> 32
            for a, b in zip(self._a, self._b, strict=True)
        )


def jaccard(sig_a: tuple[int, ...], sig_b: tuple[int, ...]) -> float:
    """Estimated Jaccard similarity from two signatures."""
    if not sig_a or not sig_b:
        return 0.0
    matches = sum(1 for x, y in zip(sig_a, sig_b, strict=False) if x == y)
    return matches / len(sig_a)


def exact_jaccard(a: set[int], b: set[int]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a) + len(b) - intersection
    return intersection / union if union else 0.0


class LshIndex:
    """Banded LSH index over MinHash signatures.

    The band configuration targets a slightly *lower* similarity than the
    requested threshold: LSH only generates candidates, and every candidate is
    verified with an exact Jaccard comparison afterwards. Biasing towards
    recall therefore costs a few extra comparisons but avoids missed
    duplicates.
    """

    RECALL_MARGIN = 0.1

    def __init__(self, num_perm: int = 64, threshold: float = 0.9) -> None:
        self.num_perm = num_perm
        target = max(0.05, threshold - self.RECALL_MARGIN)
        self.bands, self.rows = _optimal_bands(num_perm, target)
        self._buckets: list[dict[tuple[int, ...], list[str]]] = [
            defaultdict(list) for _ in range(self.bands)
        ]

    def add(self, key: str, signature: tuple[int, ...]) -> None:
        for band in range(self.bands):
            start = band * self.rows
            bucket = signature[start : start + self.rows]
            self._buckets[band][bucket].append(key)

    def query(self, signature: tuple[int, ...]) -> set[str]:
        found: set[str] = set()
        for band in range(self.bands):
            start = band * self.rows
            bucket = signature[start : start + self.rows]
            found.update(self._buckets[band].get(bucket, ()))
        return found


def _optimal_bands(num_perm: int, threshold: float) -> tuple[int, int]:
    """Pick (bands, rows) whose S-curve is closest to ``threshold``."""
    best = (num_perm, 1)
    best_error = float("inf")
    for rows in range(1, num_perm + 1):
        if num_perm % rows:
            continue
        bands = num_perm // rows
        estimate = (1 / bands) ** (1 / rows)
        error = abs(estimate - threshold)
        if error < best_error:
            best_error = error
            best = (bands, rows)
    return best
