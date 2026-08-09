"""Internal document representation.

Every parser converts its source format into a :class:`Document`. The document
carries the raw text plus a list of :class:`Block` objects describing the
structural elements found in the source (headings, paragraphs, code, ...).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ragforge.utils.ids import stable_id


class BlockType(str, Enum):
    """Structural element kinds recognised by the analyzer."""

    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    NUMBERED_LIST = "numbered_list"
    TABLE = "table"
    CODE = "code"
    QUOTE = "quote"
    FRONTMATTER = "frontmatter"
    HORIZONTAL_RULE = "horizontal_rule"
    UNKNOWN = "unknown"

    @property
    def is_prose(self) -> bool:
        return self in {BlockType.PARAGRAPH, BlockType.QUOTE, BlockType.UNKNOWN}

    @property
    def is_atomic(self) -> bool:
        """Blocks that should not be split unless they exceed the hard maximum."""
        return self in {BlockType.CODE, BlockType.TABLE}


class Block(BaseModel):
    """A single structural element of a document."""

    model_config = ConfigDict(extra="forbid")

    type: BlockType = BlockType.PARAGRAPH
    text: str = ""
    level: int = 0
    """Heading depth (1 = ``#``). ``0`` for non-heading blocks."""
    heading_path: list[str] = Field(default_factory=list)
    """Ancestor headings, outermost first, excluding the block itself."""
    language: str | None = None
    """Programming language for code blocks."""
    start_line: int = 0
    end_line: int = 0
    start_offset: int = 0
    end_offset: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_heading(self) -> bool:
        return self.type in {BlockType.HEADING, BlockType.TITLE}

    @property
    def section(self) -> str | None:
        if self.is_heading:
            return self.text.strip() or None
        return self.heading_path[-1] if self.heading_path else None

    @property
    def parent_section(self) -> str | None:
        path = self.heading_path
        if self.is_heading:
            return path[-1] if path else None
        return path[-2] if len(path) >= 2 else None

    def full_path(self) -> list[str]:
        """Heading path including the block itself when it is a heading."""
        if self.is_heading and self.text.strip():
            return [*self.heading_path, self.text.strip()]
        return list(self.heading_path)


class DocumentStructure(BaseModel):
    """Summary of the structural analysis of a document."""

    model_config = ConfigDict(extra="forbid")

    blocks: list[Block] = Field(default_factory=list)
    has_headings: bool = False
    max_heading_depth: int = 0
    block_counts: dict[str, int] = Field(default_factory=dict)

    @property
    def is_structured(self) -> bool:
        return self.has_headings


class Document(BaseModel):
    """Common internal representation for every supported input format."""

    model_config = ConfigDict(extra="forbid")

    id: str = ""
    title: str = ""
    source: str = ""
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    structure: DocumentStructure | None = None

    def model_post_init(self, __context: Any) -> None:
        if not self.id:
            self.id = stable_id("doc", self.source or self.title or self.content[:256])

    @property
    def blocks(self) -> list[Block]:
        return self.structure.blocks if self.structure else []

    def with_content(self, content: str) -> Document:
        """Return a copy with replaced content (used by the cleaning stage)."""
        return self.model_copy(update={"content": content, "structure": None})

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "characters": len(self.content),
            "blocks": len(self.blocks),
        }
