"""Code-aware chunking.

Code blocks are never cut at arbitrary character offsets. When a fenced block
exceeds the hard limit it is split at *logical* boundaries - top-level
definitions, blank-line separated statement groups, or brace boundaries - and
each fragment is re-fenced so downstream consumers still receive valid
Markdown.
"""

from __future__ import annotations

import re

from ragforge.chunking.base import ChunkCandidate, Chunker, SizeMeter
from ragforge.models.document import Block, BlockType, Document

_FENCE_LINE_RE = re.compile(r"^\s*(```+|~~~+)\s*([\w+#.-]*)\s*$")
_PY_BOUNDARY_RE = re.compile(r"^(?:@\w|def\s|class\s|async\s+def\s)")
_C_BOUNDARY_RE = re.compile(
    r"^(?:(?:export\s+)?(?:public|private|protected|static|final|async)\s+)*"
    r"(?:function|class|interface|struct|enum|impl|fn|func|type|const|let|var)\b"
)


def unwrap_fence(text: str) -> tuple[str, str, str]:
    """Return ``(fence, language, body)`` for a fenced block."""
    lines = text.split("\n")
    if not lines:
        return "", "", text
    match = _FENCE_LINE_RE.match(lines[0]) or re.match(r"^\s*(```+|~~~+)\s*([\w+#.-]*)", lines[0])
    if not match:
        return "", "", text
    fence, language = match.group(1), (match.group(2) or "")
    body_lines = lines[1:]
    if body_lines and body_lines[-1].strip().startswith(fence[0] * len(fence)):
        body_lines = body_lines[:-1]
    return fence, language, "\n".join(body_lines)


def rewrap_fence(body: str, fence: str, language: str) -> str:
    if not fence:
        return body
    return f"{fence}{language}\n{body}\n{fence}"


def split_code_block(
    text: str, meter: SizeMeter, *, budget: int, language: str | None = None
) -> list[str]:
    """Split an oversized code block at logical boundaries."""
    fence, fence_lang, body = unwrap_fence(text)
    lang = (language or fence_lang or "").lower()
    if not body.strip():
        return [text]

    overhead = meter.size(rewrap_fence("", fence, fence_lang)) if fence else 0
    inner_budget = max(1, budget - overhead)

    segments = _logical_segments(body, lang)
    packed = _pack_segments(segments, meter, inner_budget)
    if not packed:
        packed = [body]
    return [rewrap_fence(part, fence, fence_lang) if fence else part for part in packed]


def _logical_segments(body: str, language: str) -> list[str]:
    """Group code lines into logically related segments."""
    lines = body.split("\n")
    boundary = _boundary_for(language)
    segments: list[str] = []
    buffer: list[str] = []

    for line in lines:
        is_top_level = bool(line) and not line[:1].isspace()
        starts_definition = is_top_level and bool(boundary.match(line.strip()))
        if starts_definition and buffer and any(item.strip() for item in buffer):
            segments.append("\n".join(buffer).rstrip())
            buffer = []
        buffer.append(line)
    if buffer:
        segments.append("\n".join(buffer).rstrip())

    if len(segments) > 1:
        return [s for s in segments if s.strip()]
    return _split_on_blank_lines(body)


def _split_on_blank_lines(body: str) -> list[str]:
    parts = re.split(r"\n\s*\n", body)
    return [p for p in parts if p.strip()] or [body]


def _boundary_for(language: str) -> re.Pattern[str]:
    if language in {"python", "py", "python3"}:
        return _PY_BOUNDARY_RE
    return _C_BOUNDARY_RE


def _pack_segments(segments: list[str], meter: SizeMeter, budget: int) -> list[str]:
    packed: list[str] = []
    buffer: list[str] = []
    size = 0
    for segment in segments:
        segment_size = meter.size(segment)
        if buffer and size + segment_size > budget:
            packed.append("\n\n".join(buffer))
            buffer, size = [], 0
        if segment_size > budget and not buffer:
            packed.extend(_split_lines_by_budget(segment, meter, budget))
            continue
        buffer.append(segment)
        size += segment_size
    if buffer:
        packed.append("\n\n".join(buffer))
    return [p for p in packed if p.strip()]


def _split_lines_by_budget(segment: str, meter: SizeMeter, budget: int) -> list[str]:
    parts: list[str] = []
    buffer: list[str] = []
    size = 0
    for line in segment.split("\n"):
        line_size = meter.size(line) + 1
        if buffer and size + line_size > budget:
            parts.append("\n".join(buffer))
            buffer, size = [], 0
        buffer.append(line)
        size += line_size
    if buffer:
        parts.append("\n".join(buffer))
    return parts


class CodeChunker(Chunker):
    """Strategy that treats code blocks as first-class chunks.

    Each code block becomes its own chunk (with the surrounding explanatory
    paragraph attached when it fits), while prose is chunked structurally.
    """

    name = "code"

    def chunk(self, document: Document) -> list[ChunkCandidate]:
        blocks = self.blocks_of(document)
        if not blocks:
            return []

        candidates: list[ChunkCandidate] = []
        pending_prose: list[Block] = []
        heading_prefix = ""
        current_path: list[str] = []

        def flush_prose() -> None:
            nonlocal pending_prose
            if not pending_prose:
                return
            from ragforge.chunking.structural import StructuralChunker

            text = "\n\n".join(b.text.strip() for b in pending_prose if b.text.strip())
            if text:
                sub_doc = Document(
                    id=document.id,
                    title=document.title,
                    source=document.source,
                    content=(f"{heading_prefix}\n\n{text}" if heading_prefix else text),
                )
                sub = StructuralChunker(self.config, self.meter, mode="sentence")
                for candidate in sub.chunk(sub_doc):
                    candidate.heading_path = list(current_path)
                    candidates.append(candidate)
            pending_prose = []

        for block in blocks:
            if block.is_heading:
                flush_prose()
                current_path = block.full_path()
                heading_prefix = f"{'#' * block.level} {block.text.strip()}"
                continue
            if block.type is BlockType.CODE:
                flush_prose()
                lead = ""
                text = block.text.strip()
                combined = (
                    f"{heading_prefix}\n\n{lead}\n\n{text}".strip() if heading_prefix else text
                )
                size = self.meter.size(combined)
                if size <= self.config.max_size:
                    pieces = [combined]
                else:
                    pieces = [
                        f"{heading_prefix}\n\n{piece}".strip() if heading_prefix else piece
                        for piece in split_code_block(
                            text,
                            self.meter,
                            budget=self.config.target_size,
                            language=block.language,
                        )
                    ]
                for piece in pieces:
                    candidates.append(
                        ChunkCandidate(
                            text=piece,
                            heading_path=list(current_path),
                            content_type="code",
                            language=block.language,
                            start_offset=block.start_offset,
                            end_offset=block.end_offset,
                            block_types=["code"],
                            metadata={"code_split": len(pieces) > 1},
                        )
                    )
                continue
            pending_prose.append(block)

        flush_prose()
        return [c for c in candidates if c.text.strip()]
