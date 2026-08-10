"""Semantic role classification for blocks and sections.

The classifier is **domain-agnostic**. It never matches product names or
subject vocabulary. Two independent signals are combined:

1. **Heading intent** - a small vocabulary of *document-organisation* words
   that authors of technical documents reuse across every domain
   ("keywords", "glossary", "procedure", "examples", "see also"). These are
   structural labels, not subject matter.

2. **Textual shape** - measurable properties of the text itself: how many
   segments it has, how long they are, whether they contain finite verbs,
   the ratio of separators to sentences, list-item length distribution.

Shape is authoritative. A section headed "Keywords" that actually contains
explanatory prose is classified as knowledge; a section headed "Overview" that
is really 300 semicolon-separated noun phrases is classified as retrieval
terms. Heading intent only breaks ties and supplies the target metadata field.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass

from ragforge.models.document import Block, BlockType
from ragforge.semantics.roles import SemanticRole, TermField

# ----------------------------------------------------------------------
# Heading intent vocabulary.
#
# Every entry is a *document-organisation* word, i.e. a label describing the
# role of a section within any document, in any subject area. Adding domain
# vocabulary here would be a bug.
# ----------------------------------------------------------------------
_HEADING_INTENT: list[tuple[re.Pattern[str], SemanticRole, TermField | None]] = [
    # -- retrieval term lists -------------------------------------------
    (re.compile(r"^tags?$"), SemanticRole.RETRIEVAL_TERMS, TermField.TAGS),
    (
        re.compile(r"^(important |primary |main )?keywords?$"),
        SemanticRole.RETRIEVAL_TERMS,
        TermField.KEYWORDS,
    ),
    (re.compile(r"\b(search )?(aliases|alias)\b"), SemanticRole.RETRIEVAL_TERMS, TermField.ALIASES),
    (
        re.compile(r"^alternative (terms|names|phrasings)"),
        SemanticRole.RETRIEVAL_TERMS,
        TermField.ALIASES,
    ),
    (re.compile(r"^synonyms?\b"), SemanticRole.RETRIEVAL_TERMS, TermField.ALIASES),
    (
        re.compile(r"^(search|query) (terms|phrases|strings)$"),
        SemanticRole.RETRIEVAL_TERMS,
        TermField.ALIASES,
    ),
    (re.compile(r"^frequently searched"), SemanticRole.RETRIEVAL_TERMS, TermField.ALIASES),
    (
        re.compile(r"^(important |key |named )?entities$"),
        SemanticRole.RETRIEVAL_TERMS,
        TermField.ENTITIES,
    ),
    (
        re.compile(r"^related (topics|concepts|terms|subjects)"),
        SemanticRole.RETRIEVAL_TERMS,
        TermField.RELATED_CONCEPTS,
    ),
    (
        re.compile(r"^(see also|further reading)$"),
        SemanticRole.RETRIEVAL_TERMS,
        TermField.RELATED_CONCEPTS,
    ),
    (
        re.compile(r"^(common |frequent |typical )?(user )?questions\b"),
        SemanticRole.RETRIEVAL_TERMS,
        TermField.QUESTIONS,
    ),
    (
        re.compile(r"\bthis (document|page|article) answers\b"),
        SemanticRole.RETRIEVAL_TERMS,
        TermField.QUESTIONS,
    ),
    # -- document metadata ----------------------------------------------
    (
        re.compile(r"^(metadata|front ?matter|document (info|information|properties))$"),
        SemanticRole.DOCUMENT_META,
        None,
    ),
    (re.compile(r"^(chunk|document|record|page) id$"), SemanticRole.DOCUMENT_META, None),
    (
        re.compile(
            r"^(category|difficulty|audience|source type|topic|version|status|author|license)$"
        ),
        SemanticRole.DOCUMENT_META,
        None,
    ),
    (
        re.compile(
            r"^(retrieval|indexing|chunking|embedding) (notes?|hints?|guidance|instructions?)"
        ),
        SemanticRole.DOCUMENT_META,
        None,
    ),
    (re.compile(r"^recommended chunk boundaries$"), SemanticRole.DOCUMENT_META, None),
    (re.compile(r"^ai retrieval notes$"), SemanticRole.DOCUMENT_META, None),
    # -- navigation -------------------------------------------------------
    (re.compile(r"^(table of )?contents$"), SemanticRole.NAVIGATION, None),
    (re.compile(r"^(index|navigation|breadcrumbs?|site ?map)$"), SemanticRole.NAVIGATION, None),
    # -- knowledge sub-roles ----------------------------------------------
    (
        re.compile(r"^(definitions?|glossary|terminology|nomenclature)\b"),
        SemanticRole.DEFINITION,
        None,
    ),
    (
        re.compile(
            r"^(procedures?|steps?|how ?to|walkthrough|instructions?|tutorial|recipe|workflow)\b"
        ),
        SemanticRole.PROCEDURE,
        None,
    ),
    (
        re.compile(r"^(examples?|sample[s]?|illustrations?|demos?|use cases?)\b"),
        SemanticRole.EXAMPLE,
        None,
    ),
    (
        re.compile(r"^(rules?|constraints?|requirements?|policies|guidelines?|conventions?)\b"),
        SemanticRole.RULE,
        None,
    ),
    (re.compile(r"^(best practices?|recommendations?|dos and don'?ts)\b"), SemanticRole.RULE, None),
    (
        re.compile(r"^(common )?(mistakes?|pitfalls?|anti-?patterns?|misconceptions?|gotchas?)\b"),
        SemanticRole.RULE,
        None,
    ),
    (re.compile(r"^(warnings?|cautions?|notes?|caveats?|limitations?)\b"), SemanticRole.RULE, None),
    (
        re.compile(
            r"^(reference|api reference|parameters?|options?|specification|comparison|matrix)\b"
        ),
        SemanticRole.REFERENCE,
        None,
    ),
    (re.compile(r"^(edge cases?|special cases?|corner cases?)\b"), SemanticRole.KNOWLEDGE, None),
]

# A leading "3.", "3.1", "A.", "Part 2 -" style ordinal is noise for intent.
_ORDINAL_PREFIX_RE = re.compile(
    r"^\s*(?:(?:part|section|chapter|appendix)\s+)?"
    r"[0-9ivxlcIVXLC]+(?:\.[0-9]+)*"
    r"\s*[.):\-\u2013\u2014]?\s+",
    re.IGNORECASE,
)
_TRAILING_COLON_RE = re.compile(r"\s*:\s*$")
_HASH_PREFIX_RE = re.compile(r"^\s*#{1,6}\s*")

_FENCE_BLOCK_RE = re.compile(r"(?:^|\n)(```|~~~)[^\n]*\n.*?(?:\n\1[ \t]*(?=\n|$)|\Z)", re.DOTALL)
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_SEGMENT_SPLIT_RE = re.compile(r"[;\u2022]|\s+\|\s+|,(?=\s*[A-Z0-9`])")
_SENTENCE_END_RE = re.compile(r"[.!?](?:\s|$)")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+\u2022]|\d+[.)]|[a-zA-Z][.)])\s+(.*)$")
_INLINE_CODE_RE = re.compile(r"`[^`]+`")
_KV_LINE_RE = re.compile(r"^\s*[-*]?\s*\*{0,2}[\w .()/-]{2,40}\*{0,2}\s*:\s+\S")

# Finite-verb markers. Their presence is the strongest signal that a segment is
# a statement rather than a search term. Deliberately generic English function
# words - no subject vocabulary.
_VERB_MARKERS = frozenset(
    """is are was were be been being has have had do does did can could may might
    must shall should will would runs run executes execute happens happen occurs
    occur means mean returns return causes cause requires require allows allow
    prevents prevent uses use contains contain provides provide affects affect
    creates create removes remove becomes become remains remain applies apply
    determines determine defines define specifies specify supports support""".split()
)

_MIN_SEGMENTS_FOR_TERM_LIST = 5
_TERM_SEGMENT_WORDS = 7.0
"""Mean words per segment above which a list is prose, not search terms."""


@dataclass(slots=True)
class Shape:
    """Measured textual properties used for classification."""

    segments: int = 0
    """Number of separator-delimited segments (';', '|', bullets, lines)."""
    sentences: int = 0
    verb_segment_ratio: float = 0.0
    """Fraction of segments containing a finite-verb marker."""
    mean_segment_words: float = 0.0
    list_items: int = 0
    numbered_items: int = 0
    key_value_lines: int = 0
    question_lines: int = 0
    words: int = 0
    code_fraction: float = 0.0
    fenced_fraction: float = 0.0
    """Share of the text occupied by fenced code blocks or diagrams."""
    table_fraction: float = 0.0
    """Share of non-blank lines that are Markdown table rows."""

    @property
    def is_term_list(self) -> bool:
        """Many short, verb-free segments: a keyword/alias/entity dump.

        The 7-word ceiling is empirical: across the technical documents used to
        tune this, genuine term sections average 1.8-6.6 words per segment,
        while bullet lists that carry real statements average 8 or more.
        """
        if self.segments < _MIN_SEGMENTS_FOR_TERM_LIST:
            return False
        if self.table_fraction >= 0.5 or self.fenced_fraction >= 0.5:
            return False
        return self.verb_segment_ratio < 0.25 and self.mean_segment_words <= _TERM_SEGMENT_WORDS

    @property
    def is_question_list(self) -> bool:
        return self.question_lines >= 3 and self.question_lines >= self.segments * 0.6

    @property
    def is_key_value_block(self) -> bool:
        return self.key_value_lines >= 2 and self.key_value_lines >= self.segments * 0.6


@dataclass(slots=True)
class RoleAssignment:
    """Classification result for a block or section."""

    role: SemanticRole = SemanticRole.KNOWLEDGE
    field: TermField | None = None
    confidence: float = 0.5
    reason: str = ""
    terms: list[str] = dataclasses.field(default_factory=list)
    """Extracted individual terms when the role is ``RETRIEVAL_TERMS``."""


# ----------------------------------------------------------------------
# Heading intent
# ----------------------------------------------------------------------
def normalize_heading(text: str) -> str:
    """Strip markers, ordinals, punctuation and markup so intent can match.

    Backticks are unwrapped rather than removed: ``\u0060Chunk ID\u0060`` is still the
    heading "Chunk ID".
    """
    cleaned = _INLINE_CODE_RE.sub(lambda m: m.group(0).strip("`"), text)
    cleaned = _HASH_PREFIX_RE.sub("", cleaned)
    cleaned = cleaned.replace("*", "").replace("_", " ").strip()
    cleaned = _ORDINAL_PREFIX_RE.sub("", cleaned)
    cleaned = _TRAILING_COLON_RE.sub("", cleaned)
    return " ".join(cleaned.split()).casefold()


def heading_intent(text: str) -> tuple[SemanticRole, TermField | None] | None:
    """Return the role a heading suggests, if it is a recognised label."""
    normalized = normalize_heading(text)
    if not normalized:
        return None
    for pattern, role, term_field in _HEADING_INTENT:
        if pattern.search(normalized):
            return role, term_field
    return None


# ----------------------------------------------------------------------
# Shape measurement
# ----------------------------------------------------------------------
def measure_shape(text: str) -> Shape:
    """Measure the structural properties of a piece of text."""
    stripped = text.strip()
    shape = Shape()
    if not stripped:
        return shape

    # Fenced code and textual diagrams are structurally line-oriented and would
    # otherwise register as a huge list of short verb-free "terms". They are
    # measured separately and excluded from the prose shape.
    fenced_chars = 0
    for match in _FENCE_BLOCK_RE.finditer(stripped):
        fenced_chars += len(match.group(0))
    shape.fenced_fraction = fenced_chars / max(len(stripped), 1)
    stripped = _FENCE_BLOCK_RE.sub("\n", stripped).strip()
    if not stripped:
        shape.words = 0
        return shape

    body_lines = [ln for ln in stripped.split("\n") if ln.strip()]
    if body_lines:
        table_rows = sum(1 for ln in body_lines if _TABLE_ROW_RE.match(ln))
        shape.table_fraction = table_rows / len(body_lines)
    prose = "\n".join(ln for ln in body_lines if not ln.lstrip().startswith("#"))
    shape.words = len(prose.split())
    shape.sentences = len(_SENTENCE_END_RE.findall(prose))

    code_chars = sum(len(m.group(0)) for m in _INLINE_CODE_RE.finditer(prose))
    shape.code_fraction = code_chars / max(len(prose), 1)

    segments: list[str] = []
    for line in body_lines:
        if line.lstrip().startswith("#"):
            continue
        item = _LIST_ITEM_RE.match(line)
        if item:
            shape.list_items += 1
            if re.match(r"^\s*\d+[.)]", line):
                shape.numbered_items += 1
            segments.append(item.group(1).strip())
        else:
            segments.extend(p.strip() for p in _SEGMENT_SPLIT_RE.split(line) if p.strip())
        if _KV_LINE_RE.match(line):
            shape.key_value_lines += 1
        if line.rstrip().endswith("?"):
            shape.question_lines += 1

    segments = [s for s in segments if s]
    shape.segments = len(segments)
    if segments:
        with_verb = sum(1 for s in segments if _has_verb(s))
        shape.verb_segment_ratio = with_verb / len(segments)
        shape.mean_segment_words = sum(len(s.split()) for s in segments) / len(segments)
    return shape


def _has_verb(segment: str) -> bool:
    """Heuristic finite-verb detector for a short segment."""
    words = [w.strip("`*_(),.;:\"'").casefold() for w in segment.split()]
    if any(w in _VERB_MARKERS for w in words):
        return True
    # Third-person singular or past tense on a word that is not a plural noun.
    return any(
        len(w) > 4
        and (w.endswith("ed") or (w.endswith("s") and not w.endswith("ss")))
        and w not in _NON_VERB_S
        for w in words
    )


# Common plural nouns / adjectives that would otherwise trip the "-s" rule.
_NON_VERB_S = frozenset(
    """events actions objects variables values names terms items steps notes rules
    types modes states props fields lists tables codes tools files paths users
    cases links tags keys words lines pages parts kinds forms views logs jobs
    hooks nodes edges roles ports hosts flags props others always alias aliases
    classes methods options params args tests specs docs apis sdks""".split()
)


# ----------------------------------------------------------------------
# Term extraction
# ----------------------------------------------------------------------
def extract_terms(text: str, *, limit: int = 256) -> list[str]:
    """Pull the individual terms out of a keyword / alias / tag section."""
    terms: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _LIST_ITEM_RE.match(line)
        candidate_line = match.group(1) if match else line
        for piece in _SEGMENT_SPLIT_RE.split(candidate_line):
            term = piece.strip().strip("`*_.,;\u2022 ").strip()
            if 1 <= len(term) <= 120 and term:
                terms.append(term)
    # Preserve order, drop case-insensitive repeats.
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        key = term.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(term)
        if len(unique) >= limit:
            break
    return unique


# ----------------------------------------------------------------------
# Classification
# ----------------------------------------------------------------------
class RoleClassifier:
    """Assigns a :class:`SemanticRole` to blocks and sections."""

    def __init__(self, *, enabled: bool = True, min_terms: int = 5) -> None:
        self.enabled = enabled
        self.min_terms = min_terms

    # ------------------------------------------------------------------
    def classify_block(self, block: Block, *, heading: str | None = None) -> RoleAssignment:
        """Classify a single block, optionally under a known heading."""
        if not self.enabled:
            return RoleAssignment(role=SemanticRole.KNOWLEDGE, reason="classification disabled")

        if block.type is BlockType.CODE:
            return RoleAssignment(SemanticRole.CODE, confidence=1.0, reason="fenced code block")
        if block.type is BlockType.TABLE:
            return RoleAssignment(SemanticRole.REFERENCE, confidence=0.9, reason="table")

        return self.classify_text(block.text, heading=heading)

    def classify_text(self, text: str, *, heading: str | None = None) -> RoleAssignment:
        """Classify arbitrary text, optionally under a known heading."""
        if not self.enabled:
            return RoleAssignment(role=SemanticRole.KNOWLEDGE, reason="classification disabled")

        stripped = text.strip()
        if not stripped:
            return RoleAssignment(SemanticRole.KNOWLEDGE, confidence=0.0, reason="empty")

        shape = measure_shape(stripped)
        intent = heading_intent(heading) if heading else None
        intent_role = intent[0] if intent else None
        intent_field = intent[1] if intent else None

        # Code and diagrams are knowledge even though they are line-oriented
        # and verb-free; they must never be mistaken for a keyword dump.
        if shape.fenced_fraction >= 0.5:
            return RoleAssignment(
                SemanticRole.CODE,
                confidence=0.9,
                reason=f"{shape.fenced_fraction:.0%} fenced code or diagram",
            )

        # A Markdown table encodes relationships between columns. Its cells are
        # short and verb-free, which would otherwise look exactly like a term
        # list, so tables are recognised before the term-list test runs.
        if shape.table_fraction >= 0.5:
            return RoleAssignment(
                SemanticRole.REFERENCE,
                confidence=0.85,
                reason=f"{shape.table_fraction:.0%} table rows",
            )

        # -- shape decides whether this is a term dump -------------------
        if shape.is_term_list and shape.segments >= self.min_terms:
            terms = extract_terms(stripped)
            if len(terms) >= self.min_terms:
                return RoleAssignment(
                    role=SemanticRole.RETRIEVAL_TERMS,
                    field=intent_field or _infer_field(intent_role, shape),
                    confidence=0.9 if intent_role is SemanticRole.RETRIEVAL_TERMS else 0.7,
                    reason=(
                        f"{shape.segments} segments, "
                        f"{shape.verb_segment_ratio:.0%} contain a verb, "
                        f"mean {shape.mean_segment_words:.1f} words"
                    ),
                    terms=terms,
                )

        # A list of questions is query-side material, not an answer.
        if shape.is_question_list:
            return RoleAssignment(
                role=SemanticRole.RETRIEVAL_TERMS,
                field=TermField.QUESTIONS,
                confidence=0.85,
                reason=f"{shape.question_lines} interrogative lines",
                terms=extract_terms(stripped),
            )

        # -- heading intent, when the shape does not contradict it -------
        if intent_role is SemanticRole.RETRIEVAL_TERMS:
            # Labelled as terms but written as prose: keep the prose.
            if shape.verb_segment_ratio >= 0.5 and shape.sentences >= 2:
                return RoleAssignment(
                    SemanticRole.KNOWLEDGE,
                    confidence=0.7,
                    reason="term-list heading but explanatory prose body",
                )
            terms = extract_terms(stripped)
            if len(terms) >= self.min_terms:
                return RoleAssignment(
                    SemanticRole.RETRIEVAL_TERMS,
                    field=intent_field,
                    confidence=0.8,
                    reason="heading indicates a term list",
                    terms=terms,
                )

        if intent_role is SemanticRole.DOCUMENT_META:
            # Short key/value front-matter is metadata; a long prose section
            # under a "Metadata" heading is still knowledge.
            if shape.words <= 60 or shape.is_key_value_block:
                return RoleAssignment(
                    SemanticRole.DOCUMENT_META,
                    confidence=0.8,
                    reason="short front-matter under a metadata heading",
                )
            return RoleAssignment(
                SemanticRole.KNOWLEDGE,
                confidence=0.6,
                reason="metadata heading but substantial prose",
            )

        if intent_role is SemanticRole.NAVIGATION:
            return RoleAssignment(
                SemanticRole.NAVIGATION, confidence=0.8, reason="navigation heading"
            )

        if intent_role is not None:
            return RoleAssignment(intent_role, confidence=0.7, reason="heading intent")

        # -- shape-only fallbacks ---------------------------------------
        if shape.numbered_items >= 3 and shape.verb_segment_ratio >= 0.4:
            return RoleAssignment(
                SemanticRole.PROCEDURE, confidence=0.6, reason="ordered imperative steps"
            )
        return RoleAssignment(SemanticRole.KNOWLEDGE, confidence=0.5, reason="default")


def _infer_field(role: SemanticRole | None, shape: Shape) -> TermField:
    """Choose a metadata field when the heading did not name one."""
    if shape.question_lines >= 3:
        return TermField.QUESTIONS
    if role is SemanticRole.RETRIEVAL_TERMS:
        return TermField.KEYWORDS
    return TermField.KEYWORDS
