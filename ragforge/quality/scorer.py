"""Heuristic chunk quality scoring.

No LLM required. Four sub-scores are combined into a weighted quality score:

``length``      - how close the chunk is to the configured target size.
``coherence``   - complete sentences, no truncated code, single topic.
``context``     - presence of heading path / title / source metadata.
``information`` - signal density (stopword ratio, alphanumeric ratio, dupes).
"""

from __future__ import annotations

import re

from ragforge.models.chunk import Chunk, ChunkQuality, QualityFlag
from ragforge.models.config import ChunkingConfig, QualityConfig
from ragforge.utils.text import alnum_ratio, is_sentence_end, split_sentences, word_count

_WEIGHTS = {"length": 0.3, "coherence": 0.3, "context": 0.2, "information": 0.2}

_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "he",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "that",
        "the",
        "to",
        "was",
        "were",
        "will",
        "with",
        "this",
        "these",
        "those",
        "or",
        "but",
        "if",
        "then",
        "than",
        "which",
        "who",
        "whom",
        "into",
        "over",
        "under",
    ]
)

_OPENERS = {"(": ")", "[": "]", "{": "}"}


class QualityScorer:
    """Computes per-chunk quality metrics and flags."""

    def __init__(
        self,
        config: QualityConfig | None = None,
        chunking: ChunkingConfig | None = None,
    ) -> None:
        self.config = config or QualityConfig()
        self.chunking = chunking or ChunkingConfig()

    def score_all(self, chunks: list[Chunk]) -> list[Chunk]:
        if not self.config.enabled:
            return chunks
        for chunk in chunks:
            chunk.quality = self.score(chunk)
        return chunks

    # ------------------------------------------------------------------
    def score(self, chunk: Chunk) -> ChunkQuality:
        flags: list[QualityFlag] = []
        content = chunk.content.strip()
        size = chunk.metadata.size or len(content)

        length = self._length_score(size, flags)
        coherence = self._coherence_score(chunk, content, flags)
        context = self._context_score(chunk, flags)
        information = self._information_score(content, flags)

        if chunk.metadata.duplicate_of:
            kind = chunk.metadata.extra.get("duplicate_kind", QualityFlag.DUPLICATE.value)
            flags.append(QualityFlag(kind))

        total = (
            length * _WEIGHTS["length"]
            + coherence * _WEIGHTS["coherence"]
            + context * _WEIGHTS["context"]
            + information * _WEIGHTS["information"]
        )
        return ChunkQuality(
            quality_score=round(total, 4),
            length_score=round(length, 4),
            coherence_score=round(coherence, 4),
            context_score=round(context, 4),
            information_score=round(information, 4),
            flags=_dedupe(flags),
        )

    # ------------------------------------------------------------------
    def _length_score(self, size: int, flags: list[QualityFlag]) -> float:
        cfg = self.chunking
        target = cfg.target_size
        if size < cfg.min_size:
            flags.append(QualityFlag.TOO_SHORT)
            return max(0.0, size / max(cfg.min_size, 1)) * 0.6
        if size > cfg.max_size:
            flags.append(QualityFlag.TOO_LONG)
            overflow = (size - cfg.max_size) / max(cfg.max_size, 1)
            return max(0.0, 0.6 - min(overflow, 0.6))
        # Gaussian-ish falloff around the target.
        deviation = abs(size - target) / max(target, 1)
        return max(0.0, 1.0 - deviation * 0.7)

    def _coherence_score(self, chunk: Chunk, content: str, flags: list[QualityFlag]) -> float:
        score = 1.0
        if not content:
            return 0.0

        content_type = chunk.metadata.content_type
        if content_type == "code":
            if chunk.metadata.extra.get("code_split"):
                flags.append(QualityFlag.CODE_SPLIT)
                score -= 0.3
            if not _fences_balanced(content):
                flags.append(QualityFlag.CODE_SPLIT)
                score -= 0.2
            return max(0.0, score)

        body = _strip_headings(content)
        if body and content_type not in {"table", "list", "heading"}:
            # Structural trailing lines (list items, table rows, fences) are
            # complete units even without terminal punctuation.
            last = _last_meaningful_line(body)
            if last and not _is_structural(last) and not is_sentence_end(last):
                flags.append(QualityFlag.BROKEN_SENTENCE)
                score -= 0.35
            first = body.lstrip()
            if first and first[0].islower() and content_type == "text":
                flags.append(QualityFlag.BROKEN_SENTENCE)
                score -= 0.15
        if not _brackets_balanced(content):
            score -= 0.1
        if not _fences_balanced(content):
            flags.append(QualityFlag.CODE_SPLIT)
            score -= 0.2

        # Structural content (lists, tables, reference entries) is legitimately
        # low in lexical overlap, so the topic-shift heuristic only applies to
        # continuous prose.
        if content_type == "text":
            sentences = split_sentences(body)
            if len(sentences) > 3 and _topic_shift(sentences):
                flags.append(QualityFlag.MIXED_TOPICS)
                score -= 0.1
        return max(0.0, min(1.0, score))

    def _context_score(self, chunk: Chunk, flags: list[QualityFlag]) -> float:
        meta = chunk.metadata
        score = 0.0
        if meta.heading_path:
            score += 0.45 + min(len(meta.heading_path), 3) * 0.05
        if meta.title:
            score += 0.2
        if meta.source:
            score += 0.1
        if chunk.context_prefix:
            score += 0.1
        score = min(1.0, score)

        words = word_count(chunk.content)
        if words < self.config.low_context_word_threshold and not meta.heading_path:
            flags.append(QualityFlag.LOW_CONTEXT)
            score *= 0.5
        elif score < 0.35:
            flags.append(QualityFlag.LOW_CONTEXT)
        return score

    def _information_score(self, content: str, flags: list[QualityFlag]) -> float:
        words = content.split()
        if not words:
            flags.append(QualityFlag.LOW_INFORMATION)
            return 0.0
        lowered = [w.strip(".,;:!?()[]{}\"'").casefold() for w in words]
        meaningful = [w for w in lowered if w and w not in _STOPWORDS]
        density = len(meaningful) / len(words)
        unique_ratio = len(set(meaningful)) / max(len(meaningful), 1)
        symbols = alnum_ratio(content)

        score = 0.45 * min(density / 0.6, 1.0) + 0.35 * unique_ratio + 0.2 * min(symbols / 0.7, 1.0)
        if len(words) < 8 or score < 0.35:
            flags.append(QualityFlag.LOW_INFORMATION)
        return max(0.0, min(1.0, score))


# ----------------------------------------------------------------------
_STRUCTURAL_PREFIXES = ("- ", "* ", "+ ", "|", ">", "```", "~~~")


def _strip_headings(content: str) -> str:
    lines = [line for line in content.split("\n") if not line.lstrip().startswith("#")]
    return "\n".join(lines).strip()


def _last_meaningful_line(body: str) -> str:
    for line in reversed(body.split("\n")):
        if line.strip():
            return line.strip()
    return ""


def _is_structural(line: str) -> bool:
    """List item, table row, quote, code fence or numbered item."""
    if line.startswith(_STRUCTURAL_PREFIXES):
        return True
    return bool(re.match(r"^(?:\d+|[a-zA-Z])[.)]\s", line))


def _fences_balanced(content: str) -> bool:
    fences = sum(1 for line in content.split("\n") if line.lstrip().startswith(("```", "~~~")))
    return fences % 2 == 0


def _brackets_balanced(content: str) -> bool:
    stack: list[str] = []
    for char in content:
        if char in _OPENERS:
            stack.append(_OPENERS[char])
        elif char in {")", "]", "}"}:
            if not stack:
                return False
            if stack.pop() != char:
                return False
    return not stack


def _topic_shift(sentences: list[str]) -> bool:
    """Crude lexical-overlap check between the opening and closing thirds.

    Genuine single-topic prose repeats its subject vocabulary. A complete
    absence of shared content words across a long passage suggests two
    unrelated topics were packed together.
    """
    if len(sentences) < 6:
        return False
    third = max(2, len(sentences) // 3)
    head = _content_words(" ".join(sentences[:third]))
    tail = _content_words(" ".join(sentences[-third:]))
    if len(head) < 5 or len(tail) < 5:
        return False
    overlap = len(head & tail) / min(len(head), len(tail))
    return overlap < 0.05


def _content_words(text: str) -> set[str]:
    return {
        w.strip(".,;:!?()[]{}\"'").casefold()
        for w in text.split()
        if len(w) > 3 and w.casefold() not in _STOPWORDS
    }


def _dedupe(flags: list[QualityFlag]) -> list[QualityFlag]:
    seen: list[QualityFlag] = []
    for flag in flags:
        if flag not in seen:
            seen.append(flag)
    return seen
