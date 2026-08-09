"""Text utilities: whitespace handling, paragraph and sentence segmentation.

Sentence segmentation is rule-based (no spaCy/NLTK dependency) but handles the
cases that matter for technical documentation: abbreviations, decimals,
version numbers, ellipses, inline code, list markers and quoted sentences.
"""

from __future__ import annotations

import re

_ABBREVIATIONS = {
    "e.g",
    "i.e",
    "etc",
    "vs",
    "cf",
    "al",
    "fig",
    "eq",
    "no",
    "approx",
    "resp",
    "mr",
    "mrs",
    "ms",
    "dr",
    "prof",
    "sr",
    "jr",
    "st",
    "inc",
    "ltd",
    "co",
    "jan",
    "feb",
    "mar",
    "apr",
    "jun",
    "jul",
    "aug",
    "sep",
    "sept",
    "oct",
    "nov",
    "dec",
    "mon",
    "tue",
    "wed",
    "thu",
    "fri",
    "sat",
    "sun",
    "u.s",
    "u.k",
    "p.m",
    "a.m",
    "ph.d",
    "b.sc",
    "m.sc",
}

_SENTENCE_END_RE = re.compile(r"[.!?][\"'\u2019\u201d\)\]]*(?=\s|$)")
_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")
_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_TRAILING_SPACE_RE = re.compile(r"[ \t]+(?=\n)")
_NUMBER_PREFIX_RE = re.compile(r"^\d+[.)]\s")
_INLINE_SPACE_RE = re.compile(r"[ \t\u00a0\u2000-\u200a]+")
_LIST_MARKER_RE = re.compile(r"^\s*(?:[-*+\u2022]|\d+[.)]|[a-zA-Z][.)])\s+")
_WORD_RE = re.compile(r"\S+")
_ALNUM_RE = re.compile(r"[^\W_]", re.UNICODE)

_QUOTE_MAP = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u201f": '"',
    "\u2032": "'",
    "\u2033": '"',
    "\u00ab": '"',
    "\u00bb": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
    "\u2026": "...",
}
_QUOTE_TABLE = str.maketrans(_QUOTE_MAP)


def normalize_whitespace(text: str, *, preserve_newlines: bool = True) -> str:
    """Collapse runs of spaces/tabs inside lines.

    Leading indentation is *structural* in Markdown (nested lists, indented
    code blocks) and is therefore preserved, except for cosmetic 1-3 space
    indents in front of ordinary prose.
    """
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    in_list = False
    for line in text.split("\n"):
        stripped = line.lstrip(" \t\u00a0")
        indent = line[: len(line) - len(stripped)]
        body = _INLINE_SPACE_RE.sub(" ", stripped).rstrip()
        if not body:
            lines.append("")
            in_list = False
            continue
        lines.append(_keep_indent(indent, body, in_list=in_list) + body)
        if _LIST_MARKER_RE.match(body) or (in_list and indent):
            in_list = True
        elif not indent:
            in_list = False
    text = "\n".join(lines)
    if not preserve_newlines:
        text = re.sub(r"\s*\n\s*", " ", text)
    return text.strip()


def _keep_indent(indent: str, body: str, *, in_list: bool) -> str:
    """Decide whether a line's leading whitespace is structurally meaningful."""
    if not indent:
        return ""
    width = indent.replace("\t", "    ")
    if len(width) >= 4:
        # Indented code block - preserve verbatim.
        return width
    if in_list:
        # Continuation or nesting inside an active list.
        return width
    if body[:1] in {"-", "*", "+", ">", "|"} or _NUMBER_PREFIX_RE.match(body):
        return width
    return ""


def collapse_blank_lines(text: str, *, max_consecutive: int = 1) -> str:
    """Reduce runs of blank lines to at most ``max_consecutive``."""
    replacement = "\n" * (max_consecutive + 1)
    return _MULTI_BLANK_RE.sub(replacement, text)


def normalize_quotes(text: str) -> str:
    """Convert typographic quotes/dashes into ASCII equivalents."""
    return text.translate(_QUOTE_TABLE)


def split_paragraphs(text: str) -> list[str]:
    """Split on blank lines, dropping empty fragments."""
    return [part.strip() for part in _PARAGRAPH_SPLIT_RE.split(text) if part.strip()]


def word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def is_sentence_end(text: str) -> bool:
    """True when ``text`` ends with terminal punctuation (or a code/list line)."""
    stripped = text.rstrip()
    if not stripped:
        return True
    if stripped[-1] in ".!?:;\u3002\uff01\uff1f":
        return True
    return stripped[-1] in ")]}\"'`\u201d\u2019" and len(stripped) > 1 and stripped[-2] in ".!?"


def starts_lowercase(text: str) -> bool:
    stripped = text.lstrip()
    return bool(stripped) and stripped[0].islower()


def _is_abbreviation(text: str, end: int) -> bool:
    """Check whether the period at ``end - 1`` closes an abbreviation."""
    window = text[max(0, end - 12) : end]
    token = re.split(r"[\s(\[\"']", window)[-1].rstrip(".!?\"')]").casefold()
    if token in _ABBREVIATIONS:
        return True
    # Single initial like "J." or a dotted acronym "U.S.A."
    return bool(re.fullmatch(r"(?:[a-z]\.)+[a-z]?|[a-z]", token))


def split_sentences(text: str) -> list[str]:
    """Split ``text`` into sentences, preserving trailing whitespace semantics.

    List items and lines that look like headings are treated as sentence units
    of their own so that bullet lists never get merged into a single blob.
    """
    if not text.strip():
        return []

    sentences: list[str] = []
    for line_group in _split_list_lines(text):
        sentences.extend(_split_plain_sentences(line_group))
    return [s for s in (part.strip() for part in sentences) if s]


def _split_list_lines(text: str) -> list[str]:
    """Separate list items / short standalone lines from prose runs."""
    lines = text.split("\n")
    groups: list[str] = []
    buffer: list[str] = []
    for line in lines:
        if _LIST_MARKER_RE.match(line) or line.strip().startswith(">"):
            if buffer:
                groups.append("\n".join(buffer))
                buffer = []
            groups.append(line)
        else:
            buffer.append(line)
    if buffer:
        groups.append("\n".join(buffer))
    return [g for g in groups if g.strip()]


def _split_plain_sentences(text: str) -> list[str]:
    if _LIST_MARKER_RE.match(text):
        return [text]
    sentences: list[str] = []
    start = 0
    for match in _SENTENCE_END_RE.finditer(text):
        end = match.end()
        char_before = text[match.start()]
        if char_before == "." and _is_abbreviation(text, match.start() + 1):
            continue
        if _is_decimal(text, match.start()):
            continue
        following = text[end : end + 2].lstrip()
        if char_before == "." and following and following[0].islower():
            # "version 1.0 beta" style continuation - not a boundary.
            continue
        candidate = text[start:end].strip()
        if candidate:
            sentences.append(candidate)
        start = end
    remainder = text[start:].strip()
    if remainder:
        sentences.append(remainder)
    return sentences or ([text.strip()] if text.strip() else [])


def _is_decimal(text: str, dot_index: int) -> bool:
    if text[dot_index] != ".":
        return False
    before = text[dot_index - 1] if dot_index > 0 else ""
    after = text[dot_index + 1] if dot_index + 1 < len(text) else ""
    return before.isdigit() and after.isdigit()


def alnum_ratio(text: str) -> float:
    """Fraction of alphanumeric characters - low values signal noise/tables."""
    if not text:
        return 0.0
    return len(_ALNUM_RE.findall(text)) / len(text)


def truncate(text: str, limit: int = 120) -> str:
    single_line = " ".join(text.split())
    if len(single_line) <= limit:
        return single_line
    # ASCII ellipsis: this text is rendered on consoles whose encoding may not
    # cover U+2026 (legacy Windows cp1252).
    return single_line[: limit - 3].rstrip() + "..."
