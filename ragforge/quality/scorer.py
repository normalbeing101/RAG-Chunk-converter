"""Chunk quality scoring.

No LLM required. Five sub-scores are combined, weighted so that **retrieval
usefulness dominates**:

``retrieval``   - would this chunk actually answer a question? (weight 0.30)
``information`` - signal density, and whether the "signal" is prose or a term
                  dump (weight 0.25)
``coherence``   - complete sentences, intact code/tables/lists, one topic
                  (weight 0.20)
``context``     - heading path, title, self-describing content (weight 0.15)
``length``      - proximity to the configured target (weight 0.10)

Length is deliberately the *smallest* weight. In the previous version it was
worth 0.30, which is why a 500-token dump of search aliases outscored a
150-token explanation of a real concept.
"""

from __future__ import annotations

import re

from ragforge.models.chunk import Chunk, ChunkQuality, QualityFlag
from ragforge.models.config import ChunkingConfig, QualityConfig
from ragforge.semantics.classifier import measure_shape
from ragforge.semantics.roles import SemanticRole
from ragforge.utils.text import alnum_ratio, is_sentence_end, split_sentences, word_count

_WEIGHTS = {
    "retrieval": 0.30,
    "information": 0.25,
    "coherence": 0.20,
    "context": 0.15,
    "length": 0.10,
}

_STOPWORDS = frozenset(
    """a an and are as at be by for from he in is it its of on that the to was were
    will with this these those or but if then than which who whom into over under
    can could may might must shall should would do does did has have had not no""".split()
)

_OPENERS = {"(": ")", "[": "]", "{": "}"}
_STRUCTURAL_PREFIXES = ("- ", "* ", "+ ", "|", ">", "```", "~~~")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+\u2022]|\d+[.)])\s+")
_ALIAS_STEM_RE = re.compile(r"[^\w\s]")


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
        body = _strip_headings(content)
        size = chunk.metadata.size or len(content)
        role = _role_of(chunk)
        shape = measure_shape(content)

        length = self._length_score(size, flags)
        coherence = self._coherence_score(chunk, content, body, flags)
        context = self._context_score(chunk, body, flags)
        information = self._information_score(body, shape, flags)
        retrieval = self._retrieval_score(chunk, body, role, shape, flags)

        if chunk.metadata.duplicate_of:
            kind = chunk.metadata.extra.get("duplicate_kind", QualityFlag.DUPLICATE.value)
            flags.append(QualityFlag(kind))

        total = (
            retrieval * _WEIGHTS["retrieval"]
            + information * _WEIGHTS["information"]
            + coherence * _WEIGHTS["coherence"]
            + context * _WEIGHTS["context"]
            + length * _WEIGHTS["length"]
        )
        return ChunkQuality(
            quality_score=round(total, 4),
            length_score=round(length, 4),
            coherence_score=round(coherence, 4),
            context_score=round(context, 4),
            information_score=round(information, 4),
            retrieval_score=round(retrieval, 4),
            flags=_dedupe(flags),
        )

    # ------------------------------------------------------------------
    # Retrieval usefulness - the decisive sub-score
    # ------------------------------------------------------------------
    def _retrieval_score(
        self, chunk: Chunk, body: str, role: SemanticRole, shape, flags: list[QualityFlag]
    ) -> float:
        """Could a retriever return this chunk and satisfy a user question?"""
        if not body.strip():
            flags.append(QualityFlag.HEADING_ONLY)
            return 0.0

        if role is SemanticRole.DOCUMENT_META:
            flags.append(QualityFlag.METADATA_ONLY)
            return 0.15
        if role is SemanticRole.NAVIGATION:
            flags.append(QualityFlag.METADATA_ONLY)
            return 0.1
        if role is SemanticRole.RETRIEVAL_TERMS:
            flags.append(QualityFlag.KEYWORD_HEAVY)
            return 0.15

        # Shape can betray a term dump even when the role says otherwise.
        if shape.is_term_list and shape.fenced_fraction < 0.4:
            flags.append(QualityFlag.KEYWORD_HEAVY)
            if _alias_family_ratio(body) >= 0.55:
                flags.append(QualityFlag.ALIAS_HEAVY)
            return 0.2

        score = 1.0
        words = word_count(body)
        if words < self.config.min_knowledge_words:
            flags.append(QualityFlag.LOW_INFORMATION)
            score -= 0.45

        # Code and examples need their concept to be interpretable alone.
        if role.needs_parent_context and not chunk.metadata.heading_path:
            flags.append(QualityFlag.ORPHANED_CONTEXT)
            score -= 0.3

        # A statement-bearing chunk should contain at least one full sentence.
        sentences = split_sentences(body)
        if not sentences and chunk.metadata.content_type not in {"code", "table", "list"}:
            score -= 0.2
        return max(0.0, min(1.0, score))

    # ------------------------------------------------------------------
    def _length_score(self, size: int, flags: list[QualityFlag]) -> float:
        cfg = self.chunking
        target = cfg.target_size
        if size < cfg.min_size:
            flags.append(QualityFlag.TOO_SHORT)
            return max(0.0, size / max(cfg.min_size, 1)) * 0.6
        if size > cfg.max_size:
            flags.append(QualityFlag.TOO_LONG)
            flags.append(QualityFlag.OVERSIZED)
            overflow = (size - cfg.max_size) / max(cfg.max_size, 1)
            return max(0.0, 0.6 - min(overflow, 0.6))
        deviation = abs(size - target) / max(target, 1)
        return max(0.0, 1.0 - deviation * 0.7)

    def _coherence_score(
        self, chunk: Chunk, content: str, body: str, flags: list[QualityFlag]
    ) -> float:
        score = 1.0
        if not content:
            return 0.0

        content_type = chunk.metadata.content_type
        if not _fences_balanced(content):
            flags.append(QualityFlag.CODE_SPLIT)
            score -= 0.3
        if chunk.metadata.extra.get("code_split"):
            flags.append(QualityFlag.CODE_SPLIT)
            score -= 0.2
        if _table_broken(content):
            flags.append(QualityFlag.FRAGMENTED_TABLE)
            score -= 0.25
        # Only a list that *this pipeline* cut is fragmented. A source document
        # that numbers its rules 1..57 across several headings is intentional.
        if chunk.metadata.extra.get("block_split") and _list_broken(body):
            flags.append(QualityFlag.FRAGMENTED_LIST)
            score -= 0.15

        if body and content_type not in {"table", "list", "code", "heading", "metadata"}:
            last = _last_meaningful_line(body)
            if last and not _is_structural(last) and not is_sentence_end(last):
                flags.append(QualityFlag.BROKEN_SENTENCE)
                score -= 0.3
            first = body.lstrip()
            if first and first[0].islower() and content_type == "text":
                flags.append(QualityFlag.BROKEN_SENTENCE)
                score -= 0.15

        if not _brackets_balanced(content):
            score -= 0.1

        if content_type == "text":
            sentences = split_sentences(body)
            if len(sentences) > 5 and _topic_shift(sentences):
                flags.append(QualityFlag.MIXED_TOPICS)
                score -= 0.1
        return max(0.0, min(1.0, score))

    def _context_score(self, chunk: Chunk, body: str, flags: list[QualityFlag]) -> float:
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
        # A chunk whose own text names its subject is self-describing.
        if meta.section and meta.section.casefold()[:40] in chunk.content.casefold():
            score = min(1.0, score + 0.1)
        score = min(1.0, score)

        words = word_count(body)
        if words < self.config.low_context_word_threshold and not meta.heading_path:
            flags.append(QualityFlag.LOW_CONTEXT)
            score *= 0.5
        elif score < 0.35:
            flags.append(QualityFlag.LOW_CONTEXT)
        return score

    def _information_score(self, body: str, shape, flags: list[QualityFlag]) -> float:
        words = body.split()
        if not words:
            flags.append(QualityFlag.LOW_INFORMATION)
            return 0.0
        lowered = [w.strip(".,;:!?()[]{}\"'`*").casefold() for w in words]
        meaningful = [w for w in lowered if w and w not in _STOPWORDS]
        density = len(meaningful) / len(words)
        unique_ratio = len(set(meaningful)) / max(len(meaningful), 1)
        symbols = alnum_ratio(body)

        score = 0.4 * min(density / 0.6, 1.0) + 0.3 * unique_ratio + 0.15 * min(symbols / 0.7, 1.0)
        # Prose that forms sentences carries more information per token than a
        # comma-separated inventory of the same words.
        score += 0.15 * min(shape.verb_segment_ratio / 0.5, 1.0)

        if len(words) < 8 or score < 0.35:
            flags.append(QualityFlag.LOW_INFORMATION)
        return max(0.0, min(1.0, score))


# ----------------------------------------------------------------------
def _role_of(chunk: Chunk) -> SemanticRole:
    try:
        return SemanticRole(chunk.metadata.semantic_role)
    except ValueError:
        return SemanticRole.KNOWLEDGE


def _strip_headings(content: str) -> str:
    return "\n".join(line for line in content.split("\n") if not _HEADING_RE.match(line)).strip()


def _last_meaningful_line(body: str) -> str:
    for line in reversed(body.split("\n")):
        if line.strip():
            return line.strip()
    return ""


def _is_structural(line: str) -> bool:
    if line.startswith(_STRUCTURAL_PREFIXES):
        return True
    return bool(re.match(r"^(?:\d+|[a-zA-Z])[.)]\s", line))


def _fences_balanced(content: str) -> bool:
    fences = sum(1 for line in content.split("\n") if line.lstrip().startswith(("```", "~~~")))
    return fences % 2 == 0


def _table_broken(content: str) -> bool:
    """A table present without its header separator has lost its column names."""
    rows = [line for line in content.split("\n") if _TABLE_ROW_RE.match(line)]
    if len(rows) < 2:
        return False
    return not any(_TABLE_SEP_RE.match(row) for row in rows[:2])


def _list_broken(body: str) -> bool:
    """A chunk that opens mid-list has been cut away from its introduction."""
    lines = [line for line in body.split("\n") if line.strip()]
    if not lines:
        return False
    first = lines[0]
    if not _LIST_ITEM_RE.match(first):
        return False
    # An opening numbered item other than 1 means the list was cut.
    match = re.match(r"^\s*(\d+)[.)]\s", first)
    return match is not None and match.group(1) not in {"1", "0"}


def _brackets_balanced(content: str) -> bool:
    stack: list[str] = []
    for char in content:
        if char in _OPENERS:
            stack.append(_OPENERS[char])
        elif char in {")", "]", "}"} and (not stack or stack.pop() != char):
            return False
    return not stack


def _alias_family_ratio(body: str) -> float:
    """Fraction of segments that are variations on one shared head term.

    ``GDevelop event order; GDevelop execution order; GDevelop event loop`` is
    an alias family: every segment repeats the same leading token.
    """
    segments = [s.strip() for s in re.split(r"[;\n\u2022]", body) if s.strip()]
    if len(segments) < 5:
        return 0.0
    heads: dict[str, int] = {}
    for segment in segments:
        words = _ALIAS_STEM_RE.sub(" ", segment).split()
        if not words:
            continue
        head = words[0].casefold()
        heads[head] = heads.get(head, 0) + 1
    if not heads:
        return 0.0
    return max(heads.values()) / len(segments)


def _topic_shift(sentences: list[str]) -> bool:
    """Lexical-overlap check between the opening and closing thirds."""
    if len(sentences) < 6:
        return False
    third = max(2, len(sentences) // 3)
    head = _content_words(" ".join(sentences[:third]))
    tail = _content_words(" ".join(sentences[-third:]))
    if len(head) < 5 or len(tail) < 5:
        return False
    return len(head & tail) / min(len(head), len(tail)) < 0.05


def _content_words(text: str) -> set[str]:
    return {
        w.strip(".,;:!?()[]{}\"'`*").casefold()
        for w in text.split()
        if len(w) > 3 and w.casefold() not in _STOPWORDS
    }


def _dedupe(flags: list[QualityFlag]) -> list[QualityFlag]:
    seen: list[QualityFlag] = []
    for flag in flags:
        if flag not in seen:
            seen.append(flag)
    return seen
