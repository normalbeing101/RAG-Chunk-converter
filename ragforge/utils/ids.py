"""Deterministic identifier helpers.

IDs are stable across runs so that re-processing the same corpus produces the
same chunk identifiers - important for incremental vector store updates.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def stable_id(prefix: str, *parts: str, length: int = 10) -> str:
    """Return ``<prefix>_<hash>`` derived deterministically from ``parts``."""
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}" if prefix else digest


def content_hash(text: str) -> str:
    """SHA-256 hash of normalised text, used for exact duplicate detection."""
    normalized = " ".join(text.split()).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def chunk_id(document_id: str, index: int, *, width: int = 4) -> str:
    """``doc_abc123_chunk_0042`` style identifier."""
    return f"{document_id}_chunk_{index:0{width}d}"


def section_id(document_id: str, heading_path: list[str], index: int) -> str:
    """Identifier for the logical parent section of a chunk."""
    key = "/".join(heading_path) or "root"
    return stable_id(f"{document_id}_section", key, str(index), length=8)


def slugify(value: str, *, max_length: int = 60) -> str:
    """Lowercase ASCII slug suitable for filenames and human-readable IDs."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = _SLUG_RE.sub("-", ascii_text).strip("-")
    return slug[:max_length] or "untitled"
