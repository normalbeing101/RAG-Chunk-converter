"""Context enrichment.

Adds the metadata that makes a chunk useful when retrieved in isolation:

* a readable ``context_prefix`` (``Document: ... / Section: A > B > C``),
* parent/child relationships (chunk -> section -> document),
* previous/next neighbour identifiers.
"""

from __future__ import annotations

from ragforge.models.chunk import Chunk
from ragforge.models.config import ContextConfig
from ragforge.models.document import Document
from ragforge.utils.ids import section_id


class ContextEnricher:
    """Applies contextual metadata to a document's chunks."""

    def __init__(self, config: ContextConfig | None = None) -> None:
        self.config = config or ContextConfig()

    def enrich(self, chunks: list[Chunk], document: Document | None = None) -> list[Chunk]:
        if not chunks:
            return chunks
        self._assign_parents(chunks, document)
        self._assign_neighbors(chunks)
        self._assign_prefixes(chunks, document)
        return chunks

    # ------------------------------------------------------------------
    def _assign_parents(self, chunks: list[Chunk], document: Document | None) -> None:
        if not self.config.include_parents:
            for chunk in chunks:
                chunk.metadata.parent_id = None
            return

        document_id = document.id if document else (chunks[0].metadata.document_id or "doc")
        if self.config.parent_level == "document":
            for chunk in chunks:
                chunk.metadata.parent_id = document_id
            return

        # Group consecutive chunks sharing the same heading path into a section.
        section_index = 0
        previous_path: list[str] | None = None
        for chunk in chunks:
            path = chunk.metadata.heading_path
            if previous_path is None or path != previous_path:
                section_index += 1
                previous_path = list(path)
            chunk.metadata.parent_id = section_id(document_id, path, section_index)
            chunk.metadata.extra.setdefault("section_index", section_index)

    def _assign_neighbors(self, chunks: list[Chunk]) -> None:
        if not self.config.include_neighbors:
            return
        for index, chunk in enumerate(chunks):
            chunk.metadata.previous_chunk = chunks[index - 1].id if index > 0 else None
            chunk.metadata.next_chunk = chunks[index + 1].id if index + 1 < len(chunks) else None

    def _assign_prefixes(self, chunks: list[Chunk], document: Document | None) -> None:
        cfg = self.config
        if not cfg.include_context_prefix:
            return
        for chunk in chunks:
            prefix = self.build_prefix(chunk, document)
            if not prefix:
                continue
            chunk.context_prefix = prefix
            if cfg.prepend_context_to_content and not chunk.content.startswith(prefix):
                chunk.content = f"{prefix}\n\n{chunk.content}"
                chunk.metadata.char_count = len(chunk.content)

    def build_prefix(self, chunk: Chunk, document: Document | None = None) -> str:
        cfg = self.config
        lines: list[str] = []
        meta = chunk.metadata
        title = meta.title or (document.title if document else "")
        if cfg.include_title and title:
            lines.append(f"Document: {title}")
        if cfg.include_heading_path and meta.heading_path:
            lines.append("Section: " + cfg.heading_separator.join(meta.heading_path))
        if cfg.include_source and meta.source:
            lines.append(f"Source: {meta.source}")
        return "\n".join(lines)


def enrich(
    chunks: list[Chunk], document: Document | None = None, config: ContextConfig | None = None
):
    return ContextEnricher(config).enrich(chunks, document)
