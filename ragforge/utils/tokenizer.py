"""Size measurement in characters, words or tokens.

The default tokenizer is dependency-free: it approximates LLM tokenisation by
splitting on word/punctuation boundaries and further splitting long words. It
correlates closely enough with BPE tokenisers for chunk-sizing purposes while
staying fast and deterministic. ``tiktoken:<encoding>`` can be used when exact
counts matter.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Protocol

from ragforge.errors import MissingDependencyError
from ragforge.models.config import SizeUnit

_WORD_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\S+")
# Average characters per BPE sub-word token for English-like text.
_CHARS_PER_TOKEN = 4
# CJK scripts are roughly one token per character.
_CJK_RE = re.compile(r"[\u3000-\u9fff\uac00-\ud7af\uf900-\ufaff]")
_CJK_PROBE_RE = _CJK_RE
# Words no longer than this always cost exactly one token.
_SINGLE_TOKEN_CHARS = _CHARS_PER_TOKEN + 2


def _subwords(length: int) -> int:
    """Number of BPE tokens a word of ``length`` characters typically becomes."""
    if length <= 0:
        return 0
    if length <= _CHARS_PER_TOKEN + 2:
        return 1
    return 1 + (length - _CHARS_PER_TOKEN - 2 + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN


class Tokenizer(Protocol):
    """Minimal interface used by the chunking engine."""

    name: str

    def count(self, text: str, unit: SizeUnit = SizeUnit.TOKENS) -> int: ...

    def count_tokens(self, text: str) -> int: ...


class HeuristicTokenizer:
    """Fast, dependency-free token estimator."""

    name = "heuristic"

    def count_tokens(self, text: str) -> int:
        """Approximate BPE token count.

        Short words map to a single token; longer words split into sub-words.
        CJK characters count individually. Only words long enough to exceed a
        single token are measured in detail, which keeps the common case to one
        regex pass plus a length lookup.
        """
        if not text:
            return 0
        total = 0
        for token in _WORD_RE.findall(text):
            length = len(token)
            if length <= _SINGLE_TOKEN_CHARS:
                total += 1
                continue
            cjk = _CJK_RE.subn("", token)[1] if _CJK_PROBE_RE.search(token) else 0
            total += cjk + _subwords(length - cjk) if cjk else _subwords(length)
        return total

    def count_words(self, text: str) -> int:
        return len(_SPACE_RE.findall(text))

    def count(self, text: str, unit: SizeUnit = SizeUnit.TOKENS) -> int:
        if unit is SizeUnit.CHARACTERS:
            return len(text)
        if unit is SizeUnit.WORDS:
            return self.count_words(text)
        return self.count_tokens(text)


class TiktokenTokenizer(HeuristicTokenizer):
    """Exact BPE token counts via ``tiktoken`` (optional dependency)."""

    def __init__(self, encoding: str = "cl100k_base") -> None:
        try:
            import tiktoken
        except ImportError as exc:  # pragma: no cover - depends on env
            raise MissingDependencyError(
                "tiktoken", "tiktoken tokenizer", extra="rag-chunkforge[tokenizers]"
            ) from exc
        try:
            self._encoding = tiktoken.get_encoding(encoding)
        except Exception:  # pragma: no cover - network/unknown encoding
            self._encoding = tiktoken.get_encoding("cl100k_base")
        self.name = f"tiktoken:{encoding}"

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(self._encoding.encode(text, disallowed_special=()))


@lru_cache(maxsize=8)
def get_tokenizer(spec: str = "heuristic") -> Tokenizer:
    """Return a tokenizer for ``spec`` (``heuristic`` or ``tiktoken:<enc>``)."""
    spec = (spec or "heuristic").strip()
    if spec in {"", "heuristic", "default", "simple"}:
        return HeuristicTokenizer()
    if spec.startswith("tiktoken"):
        _, _, encoding = spec.partition(":")
        return TiktokenTokenizer(encoding or "cl100k_base")
    raise MissingDependencyError(spec, "tokenizer")


def measure(text: str, unit: SizeUnit, tokenizer: Tokenizer | None = None) -> int:
    """Measure ``text`` in the requested unit."""
    tk = tokenizer or get_tokenizer()
    return tk.count(text, unit)
