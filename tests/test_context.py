"""Context enrichment tests."""

from __future__ import annotations

from ragforge.chunking import chunk_text
from ragforge.context import ContextEnricher
from ragforge.models.config import ChunkingConfig, ContextConfig
from ragforge.models.document import Document


def make_chunks(text: str, **kwargs):
    cfg = ChunkingConfig(target_size=60, min_size=10, max_size=140, overlap=0, **kwargs)
    return chunk_text(text, cfg, title="Doc", source="doc.md")


def test_neighbors_are_linked(markdown_doc):
    chunks = ContextEnricher().enrich(make_chunks(markdown_doc))
    assert chunks[0].metadata.previous_chunk is None
    assert chunks[-1].metadata.next_chunk is None
    for index, chunk in enumerate(chunks[1:-1], start=1):
        assert chunk.metadata.previous_chunk == chunks[index - 1].id
        assert chunk.metadata.next_chunk == chunks[index + 1].id


def test_neighbors_can_be_disabled(markdown_doc):
    cfg = ContextConfig(include_neighbors=False)
    chunks = ContextEnricher(cfg).enrich(make_chunks(markdown_doc))
    assert all(c.metadata.previous_chunk is None for c in chunks)
    assert all(c.metadata.next_chunk is None for c in chunks)


def test_parents_group_by_section(markdown_doc):
    chunks = ContextEnricher().enrich(make_chunks(markdown_doc))
    by_parent: dict[str, set[tuple[str, ...]]] = {}
    for chunk in chunks:
        by_parent.setdefault(chunk.metadata.parent_id, set()).add(
            tuple(chunk.metadata.heading_path)
        )
    # Each parent id maps to exactly one heading path.
    assert all(len(paths) == 1 for paths in by_parent.values())
    assert len(by_parent) > 1


def test_document_level_parent(markdown_doc):
    document = Document(id="doc_x", title="T", source="s.md", content=markdown_doc)
    cfg = ContextConfig(parent_level="document")
    chunks = ContextEnricher(cfg).enrich(make_chunks(markdown_doc), document)
    assert all(c.metadata.parent_id == "doc_x" for c in chunks)


def test_parents_can_be_disabled(markdown_doc):
    cfg = ContextConfig(include_parents=False)
    chunks = ContextEnricher(cfg).enrich(make_chunks(markdown_doc))
    assert all(c.metadata.parent_id is None for c in chunks)


def test_context_prefix_contents(markdown_doc):
    chunks = ContextEnricher().enrich(make_chunks(markdown_doc))
    deep = next(c for c in chunks if len(c.metadata.heading_path) >= 2)
    assert deep.context_prefix is not None
    assert "Document: Doc" in deep.context_prefix
    assert "Section: " in deep.context_prefix
    assert " > ".join(deep.metadata.heading_path) in deep.context_prefix
    assert "Source: doc.md" in deep.context_prefix


def test_context_prefix_can_be_disabled(markdown_doc):
    cfg = ContextConfig(include_context_prefix=False)
    chunks = ContextEnricher(cfg).enrich(make_chunks(markdown_doc))
    assert all(c.context_prefix is None for c in chunks)


def test_prepend_context_to_content(markdown_doc):
    cfg = ContextConfig(prepend_context_to_content=True)
    chunks = ContextEnricher(cfg).enrich(make_chunks(markdown_doc))
    assert chunks[0].content.startswith("Document: Doc")
    assert chunks[0].metadata.char_count == len(chunks[0].content)


def test_custom_heading_separator(markdown_doc):
    cfg = ContextConfig(heading_separator=" / ")
    chunks = ContextEnricher(cfg).enrich(make_chunks(markdown_doc))
    deep = next(c for c in chunks if len(c.metadata.heading_path) >= 2)
    assert " / " in deep.context_prefix


def test_text_for_embedding_uses_prefix(markdown_doc):
    chunks = ContextEnricher().enrich(make_chunks(markdown_doc))
    chunk = chunks[0]
    assert chunk.text_for_embedding.startswith(chunk.context_prefix)
    assert chunk.content in chunk.text_for_embedding


def test_enrich_empty_list():
    assert ContextEnricher().enrich([]) == []
