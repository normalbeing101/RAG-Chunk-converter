"""Chunking engine tests: strategies, sizes, overlap, structure preservation."""

from __future__ import annotations

from itertools import pairwise

import pytest

from ragforge.chunking import (
    ChunkingEngine,
    RecursiveSplitter,
    SizeMeter,
    available_strategies,
    build_sections,
    chunk_text,
    split_code_block,
)
from ragforge.errors import ChunkingError
from ragforge.models.config import ChunkingConfig, OverlapUnit, SizeUnit, Strategy
from ragforge.models.document import Document
from ragforge.preprocessing import StructureAnalyzer, analyze


def build(text: str, **kwargs) -> list:
    defaults = {"target_size": 60, "min_size": 10, "max_size": 140, "overlap": 0}
    defaults.update(kwargs)
    return chunk_text(text, ChunkingConfig(**defaults), title="Doc", source="doc.md")


# ---------------------------------------------------------------- basics
def test_empty_document_produces_no_chunks():
    assert build("") == []
    assert build("   \n\n  \t ") == []


def test_tiny_document_single_chunk():
    chunks = build("Hello world.")
    assert len(chunks) == 1
    assert chunks[0].content == "Hello world."
    assert chunks[0].metadata.total_chunks == 1


def test_available_strategies():
    for name in ("structural", "recursive", "sentence", "code", "auto"):
        assert name in available_strategies()


def test_unknown_strategy_raises():
    engine = ChunkingEngine(ChunkingConfig())
    with pytest.raises(ChunkingError):
        engine._build("nope")


@pytest.mark.parametrize("strategy", ["structural", "recursive", "sentence", "code", "auto"])
def test_all_strategies_produce_chunks(markdown_doc, strategy):
    chunks = build(markdown_doc, strategy=Strategy(strategy))
    assert chunks
    assert all(c.content.strip() for c in chunks)
    assert all(c.id for c in chunks)


# ---------------------------------------------------------------- structure
def test_chunks_never_mix_sections(markdown_doc):
    chunks = build(markdown_doc, strategy=Strategy.RECURSIVE)
    for chunk in chunks:
        # Only one section heading body may be present per chunk.
        assert chunk.metadata.heading_path
    picking = [c for c in chunks if c.metadata.section == "How it works"]
    example = [c for c in chunks if c.metadata.section == "Example"]
    assert picking and example
    for chunk in picking:
        assert "overlaps an enemy" not in chunk.content


def test_heading_path_metadata(markdown_doc):
    chunks = build(markdown_doc)
    deep = [
        c
        for c in chunks
        if c.metadata.heading_path
        == ["Object Picking", "How it works", "Object picking in sub-events"]
    ]
    assert deep
    chunk = deep[0]
    assert chunk.metadata.section == "Object picking in sub-events"
    assert chunk.metadata.parent_section == "How it works"


def test_heading_included_in_chunk_content(markdown_doc):
    chunks = build(markdown_doc)
    for chunk in chunks:
        if chunk.metadata.section and chunk.metadata.content_type != "heading":
            assert chunk.metadata.section in chunk.content


def test_build_sections_groups_blocks():
    structure = analyze("# A\n\ntext a\n\n## B\n\ntext b\n\n# C\n\ntext c")
    sections = build_sections(structure.blocks)
    assert [s.title for s in sections] == ["A", "B", "C"]
    assert all(s.content_blocks() for s in sections)


def test_content_before_first_heading_is_kept():
    chunks = build("Preamble sentence here.\n\n# Heading\n\nBody text.")
    assert any("Preamble" in c.content for c in chunks)


# ---------------------------------------------------------------- sizes
def test_target_size_respected(plain_text):
    chunks = build(plain_text, target_size=50, max_size=90, min_size=10)
    for chunk in chunks:
        assert chunk.metadata.size <= 90, chunk.content


def test_exact_chunk_limit_boundary():
    meter = SizeMeter(SizeUnit.CHARACTERS)
    text = "\n\n".join("x" * 40 for _ in range(6))
    chunks = build(text, unit=SizeUnit.CHARACTERS, target_size=100, min_size=10, max_size=100)
    for chunk in chunks:
        assert meter.size(chunk.content) <= 100


@pytest.mark.parametrize("unit", [SizeUnit.CHARACTERS, SizeUnit.WORDS, SizeUnit.TOKENS])
def test_all_units(plain_text, unit):
    sizes = {SizeUnit.CHARACTERS: 400, SizeUnit.WORDS: 60, SizeUnit.TOKENS: 80}
    size = sizes[unit]
    chunks = build(plain_text, unit=unit, target_size=size, min_size=5, max_size=size * 2)
    assert chunks
    assert all(c.metadata.unit == unit.value for c in chunks)
    assert all(c.metadata.size <= size * 2 for c in chunks)


def test_min_size_merging():
    text = "\n\n".join(f"Short paragraph number {i}." for i in range(10))
    chunks = build(text, target_size=60, min_size=30, max_size=120, merge_small_chunks=True)
    assert len(chunks) < 10


def test_large_document_performance():
    text = "\n\n".join(
        f"## Section {i}\n\nThis is paragraph {i} with enough words to be meaningful content."
        for i in range(400)
    )
    chunks = build(text, target_size=120, min_size=20, max_size=250)
    assert len(chunks) > 50
    assert all(c.metadata.size <= 250 for c in chunks)


# ---------------------------------------------------------------- sentences
def test_sentence_strategy_never_splits_mid_sentence():
    text = " ".join(f"Sentence number {i} contains several useful words." for i in range(40))
    chunks = build(text, strategy=Strategy.SENTENCE, target_size=40, min_size=5, max_size=90)
    for chunk in chunks:
        body = chunk.content.strip()
        assert body.endswith(".") or body.endswith("!") or body.endswith("?")


def test_sentence_boundaries_with_abbreviations():
    from ragforge.utils.text import split_sentences

    sentences = split_sentences("Use e.g. this approach. It works with Dr. Smith too. Done.")
    assert len(sentences) == 3


def test_decimal_numbers_not_split():
    from ragforge.utils.text import split_sentences

    assert len(split_sentences("Version 1.5 is out. Upgrade now.")) == 2


# ---------------------------------------------------------------- code
def test_code_block_kept_intact():
    text = "# Title\n\nIntro.\n\n```python\ndef a():\n    return 1\n```\n"
    chunks = build(text, target_size=200, min_size=5, max_size=400)
    code = [c for c in chunks if c.metadata.content_type == "code"]
    assert code
    assert code[0].content.count("```") == 2
    assert code[0].metadata.language == "python"


def test_oversized_code_split_at_logical_boundaries():
    body = "\n\n".join(
        f"def function_{i}(argument):\n    value = argument * {i}\n    return value"
        for i in range(12)
    )
    text = f"```python\n{body}\n```"
    chunks = build(text, target_size=60, min_size=10, max_size=100, strategy=Strategy.CODE)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.content.count("```") % 2 == 0
        assert "def function_" in chunk.content


def test_split_code_block_helper():
    meter = SizeMeter(SizeUnit.TOKENS)
    code = "```python\n" + "\n\n".join(f"def f{i}():\n    return {i}" for i in range(8)) + "\n```"
    parts = split_code_block(code, meter, budget=30, language="python")
    assert len(parts) > 1
    assert all(p.startswith("```python") and p.endswith("```") for p in parts)


def test_code_strategy_marks_content_type():
    text = "# T\n\nWords.\n\n```js\nconst a = 1;\n```\n\nMore words."
    chunks = build(text, strategy=Strategy.CODE, target_size=100, min_size=5, max_size=200)
    types = {c.metadata.content_type for c in chunks}
    assert "code" in types
    assert "text" in types


def test_auto_strategy_picks_code_for_code_heavy():
    text = "\n\n".join(f"```python\ndef f{i}():\n    return {i}\n```" for i in range(6))
    chunks = build(text, strategy=Strategy.AUTO, target_size=100, min_size=5, max_size=200)
    assert chunks[0].metadata.strategy == "code"


def test_auto_strategy_picks_sentence_for_unstructured(plain_text):
    chunks = build(plain_text, strategy=Strategy.AUTO, target_size=80, min_size=5, max_size=160)
    assert chunks[0].metadata.strategy == "sentence"


# ---------------------------------------------------------------- tables/lists
def test_table_kept_intact_when_it_fits(markdown_doc):
    chunks = build(markdown_doc, target_size=300, min_size=10, max_size=600)
    tables = [c for c in chunks if "| Condition | Result |" in c.content]
    assert tables
    assert "| Distance |" in tables[0].content


def test_oversized_table_repeats_header():
    rows = "\n".join(f"| row{i} | value{i} |" for i in range(40))
    text = f"| name | value |\n| --- | --- |\n{rows}"
    chunks = build(text, target_size=60, min_size=10, max_size=100, keep_tables_intact=False)
    assert len(chunks) > 1
    for chunk in chunks:
        assert "| name | value |" in chunk.content


def test_list_splits_at_item_boundaries():
    items = "\n".join(f"- item number {i} with several words of content" for i in range(30))
    chunks = build(items, target_size=50, min_size=10, max_size=90)
    assert len(chunks) > 1
    for chunk in chunks:
        for line in chunk.content.split("\n"):
            if line.strip():
                assert line.lstrip().startswith("-")


# ---------------------------------------------------------------- overlap
def test_overlap_adds_previous_context():
    text = " ".join(f"Sentence {i} has quite a few informative words in it." for i in range(30))
    no_overlap = build(text, target_size=50, min_size=5, max_size=200, overlap=0)
    with_overlap = build(text, target_size=50, min_size=5, max_size=200, overlap=15)
    assert len(with_overlap) >= 2
    assert any(c.metadata.overlap_prefix_chars > 0 for c in with_overlap)
    assert sum(len(c.content) for c in with_overlap) > sum(len(c.content) for c in no_overlap)


def test_overlap_respects_sentence_boundaries():
    text = " ".join(f"Sentence {i} contains meaningful words here." for i in range(30))
    chunks = build(text, target_size=40, min_size=5, max_size=160, overlap=12)
    for chunk in chunks[1:]:
        if chunk.metadata.overlap_prefix_chars:
            prefix = chunk.content[: chunk.metadata.overlap_prefix_chars]
            assert prefix.strip().endswith(".")


def test_overlap_not_applied_across_sections(markdown_doc):
    chunks = build(markdown_doc, target_size=50, min_size=10, max_size=140, overlap=15)
    for previous, current in pairwise(chunks):
        if previous.metadata.heading_path != current.metadata.heading_path:
            assert current.metadata.overlap_prefix_chars == 0


def test_overlap_never_exceeds_max_size():
    text = " ".join(f"Word{i} filler sentence content here." for i in range(60))
    chunks = build(text, target_size=50, min_size=5, max_size=70, overlap=20)
    for chunk in chunks:
        assert chunk.metadata.size <= 70


def test_percentage_overlap():
    cfg = ChunkingConfig(
        target_size=60, min_size=10, max_size=200, overlap=20, overlap_unit=OverlapUnit.PERCENTAGE
    )
    assert cfg.resolved_overlap() == 12
    text = " ".join(f"Sentence {i} with content." for i in range(40))
    assert chunk_text(text, cfg)


def test_zero_overlap_disables_feature():
    text = " ".join(f"Sentence {i} with content words." for i in range(30))
    chunks = build(text, target_size=40, min_size=5, max_size=120, overlap=0)
    assert all(c.metadata.overlap_prefix_chars == 0 for c in chunks)


# ---------------------------------------------------------------- metadata
def test_metadata_is_complete(markdown_doc):
    chunks = build(markdown_doc)
    for index, chunk in enumerate(chunks):
        meta = chunk.metadata
        assert meta.document_id
        assert meta.title == "Doc"
        assert meta.source == "doc.md"
        assert meta.chunk_index == index
        assert meta.total_chunks == len(chunks)
        assert meta.char_count == len(chunk.content)
        assert meta.word_count > 0
        assert meta.token_count > 0
        assert meta.strategy
        assert meta.unit


def test_chunk_ids_are_deterministic(markdown_doc):
    first = [c.id for c in build(markdown_doc)]
    second = [c.id for c in build(markdown_doc)]
    assert first == second
    assert len(set(first)) == len(first)


def test_content_type_classification(markdown_doc):
    chunks = build(markdown_doc, target_size=80, min_size=10, max_size=160)
    types = {c.metadata.content_type for c in chunks}
    assert "text" in types
    # Code is either its own chunk or the dominant part of a mixed one.
    assert types & {"code", "mixed"}
    assert any("```python" in c.content for c in chunks)


# ---------------------------------------------------------------- unicode
def test_unicode_content_preserved():
    text = "# Título\n\nEl símbolo → indica flujo. 中文内容也应该正常工作。\n\nEmoji: 🚀 works."
    chunks = build(text, target_size=40, min_size=5, max_size=120)
    joined = " ".join(c.content for c in chunks)
    assert "→" in joined
    assert "中文内容" in joined
    assert "🚀" in joined


def test_cjk_text_chunking():
    text = "。".join("这是一个测试句子" for _ in range(60)) + "。"
    chunks = build(text, target_size=60, min_size=5, max_size=200)
    assert chunks


# ---------------------------------------------------------------- recursive
def test_recursive_splitter_hierarchy():
    meter = SizeMeter(SizeUnit.WORDS)
    splitter = RecursiveSplitter(meter, target_size=10, max_size=20)
    text = "## H\n\n" + " ".join(f"word{i}" for i in range(60))
    parts = splitter.split(text)
    assert len(parts) > 1
    assert all(meter.size(p) <= 20 for p in parts)


def test_recursive_splitter_short_text_untouched():
    meter = SizeMeter(SizeUnit.WORDS)
    splitter = RecursiveSplitter(meter, target_size=50, max_size=100)
    assert splitter.split("only a few words") == ["only a few words"]


def test_recursive_splitter_empty():
    meter = SizeMeter(SizeUnit.WORDS)
    assert RecursiveSplitter(meter, target_size=10, max_size=20).split("  ") == []


def test_hard_character_fallback_for_unsplittable_text():
    text = "x" * 5000
    chunks = build(text, unit=SizeUnit.CHARACTERS, target_size=500, min_size=50, max_size=1000)
    assert len(chunks) > 1
    assert all(len(c.content) <= 1000 for c in chunks)


# ---------------------------------------------------------------- engine
def test_engine_reuses_document_structure(markdown_doc):
    doc = StructureAnalyzer().analyze(Document(content=markdown_doc, source="a.md", title="A"))
    config = ChunkingConfig(target_size=60, min_size=10, max_size=140, overlap=0)
    chunks = ChunkingEngine(config).chunk_document(doc)
    assert chunks
    assert chunks[0].metadata.document_id == doc.id


def test_custom_strategy_registration():
    from ragforge.chunking import Chunker, register_strategy
    from ragforge.chunking.base import ChunkCandidate

    class OneChunk(Chunker):
        name = "one"

        def chunk(self, document):
            return [ChunkCandidate(text=document.content.strip())]

    register_strategy("one", OneChunk)
    engine = ChunkingEngine(ChunkingConfig(strategy="one", overlap=0))
    chunks = engine.chunk_document(Document(content="a b c", source="x.md"))
    assert len(chunks) == 1
