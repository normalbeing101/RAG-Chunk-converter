"""Text cleaning and normalisation.

Cleaning is deliberately conservative: fenced code blocks are protected from
every transformation, and aggressive operations (header/footer stripping, URL
removal, quote normalisation) are opt-in.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from ragforge.models.config import CleaningConfig
from ragforge.models.document import Document
from ragforge.utils.text import collapse_blank_lines, normalize_quotes, normalize_whitespace

_CODE_FENCE_RE = re.compile(r"(^|\n)(```|~~~)[^\n]*\n.*?(?:\n\2[ \t]*(?=\n|$)|\Z)", re.DOTALL)
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\ufeff\u2060]")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_NAV_PATTERNS = (
    re.compile(
        r"^\s*(?:home|back to top|next|previous|skip to (?:main )?content)\s*[|>»]*\s*$", re.I
    ),
    re.compile(r"^\s*(?:table of contents|contents|menu|navigation|breadcrumbs?)\s*$", re.I),
    re.compile(r"^\s*(?:share (?:this|on)|follow us|subscribe|cookie(?:s)? policy)\b.*$", re.I),
    re.compile(r"^\s*(?:\[[^\]]+\]\([^)]*\)\s*[|·•]\s*){2,}\[[^\]]+\]\([^)]*\)\s*$"),
)
# Private-use codepoints survive unicode normalisation and control-char stripping.
_PLACEHOLDER = "\ue000RFCODE{}\ue001"


class TextCleaner:
    """Applies the configured normalisation steps to a document."""

    def __init__(self, config: CleaningConfig | None = None) -> None:
        self.config = config or CleaningConfig()

    def clean_document(self, document: Document) -> Document:
        if not self.config.enabled:
            return document
        cleaned = self.clean(document.content)
        if cleaned == document.content:
            return document
        return document.with_content(cleaned)

    def clean(self, text: str) -> str:
        if not text or not self.config.enabled:
            return text or ""

        cfg = self.config
        protected: list[str] = []
        if cfg.preserve_code_blocks:
            text = _protect_code(text, protected)

        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = _ZERO_WIDTH_RE.sub("", text)
        text = _CONTROL_RE.sub("", text)

        if cfg.normalize_unicode:
            text = unicodedata.normalize(cfg.unicode_form, text)
        if cfg.normalize_quotes:
            text = normalize_quotes(text)
        if cfg.remove_navigation:
            text = _strip_navigation(text)
        if cfg.remove_headers or cfg.remove_footers:
            text = _strip_repeated_lines(
                text,
                threshold=cfg.repeated_line_threshold,
                min_repeats=cfg.min_repeats_for_boilerplate,
                headers=cfg.remove_headers,
                footers=cfg.remove_footers,
            )
        if cfg.remove_urls:
            text = _URL_RE.sub("", text)
        if cfg.normalize_whitespace:
            text = normalize_whitespace(text)
        if cfg.collapse_blank_lines:
            text = collapse_blank_lines(text, max_consecutive=1)

        if protected:
            text = _restore_code(text, protected)
        return text.strip()


def _protect_code(text: str, store: list[str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        store.append(match.group(0))
        return match.group(1) + _PLACEHOLDER.format(len(store) - 1)

    return _CODE_FENCE_RE.sub(_replace, text)


def _restore_code(text: str, store: list[str]) -> str:
    for index, snippet in enumerate(store):
        placeholder = _PLACEHOLDER.format(index)
        # The snippet keeps its own leading newline from the capture group.
        text = text.replace(placeholder, snippet.lstrip("\n"))
    return text


def _strip_navigation(text: str) -> str:
    kept = []
    for line in text.split("\n"):
        if any(pattern.match(line) for pattern in _NAV_PATTERNS):
            continue
        kept.append(line)
    return "\n".join(kept)


def _strip_repeated_lines(
    text: str,
    *,
    threshold: float,
    min_repeats: int,
    headers: bool,
    footers: bool,
) -> str:
    """Remove short lines that repeat across many page/section boundaries."""
    sections = re.split(r"\n\s*\n\s*\n|\f", text)
    if len(sections) < min_repeats:
        sections = [text]

    counter: Counter[str] = Counter()
    for section in sections:
        lines = [line.strip() for line in section.split("\n") if line.strip()]
        candidates: list[str] = []
        if headers:
            candidates.extend(lines[:2])
        if footers:
            candidates.extend(lines[-2:])
        for line in candidates:
            if 3 <= len(line) <= 120 and not line.startswith("#"):
                counter[line] += 1

    limit = max(min_repeats, int(len(sections) * threshold))
    boilerplate = {line for line, count in counter.items() if count >= limit}
    if not boilerplate:
        return text
    return "\n".join(line for line in text.split("\n") if line.strip() not in boilerplate)


def clean_text(text: str, config: CleaningConfig | None = None) -> str:
    """Convenience wrapper used by tests and the API."""
    return TextCleaner(config).clean(text)
