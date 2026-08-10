"""Regression tests.

Each test here pins the behaviour of a bug found during development so it
cannot silently return. Add a new test whenever you fix a bug.
"""

from __future__ import annotations

from ragforge.chunking import chunk_text
from ragforge.deduplication.minhash import LshIndex, MinHash, exact_jaccard, shingles
from ragforge.models.config import ChunkingConfig, CleaningConfig, SizeUnit, Strategy
from ragforge.preprocessing import clean_text
from ragforge.quality import DatasetValidator
from ragforge.utils.text import normalize_whitespace
from ragforge.utils.tokenizer import get_tokenizer


def build(text: str, **kwargs):
    defaults = {"target_size": 60, "min_size": 10, "max_size": 140, "overlap": 0}
    defaults.update(kwargs)
    return chunk_text(text, ChunkingConfig(**defaults))


def test_code_placeholder_is_restored_after_cleaning():
    """Placeholders used to protect code survived into the output when the
    NUL-based sentinel was stripped by the control-character filter."""
    text = "Intro\n\n```python\ndef f():\n    x  =  1\n\n\n    return x\n```\n\nOutro"
    out = clean_text(text)
    assert "RFCODE" not in out
    assert "\ue000" not in out
    assert "    x  =  1" in out
    assert out.count("```") == 2


def test_code_placeholder_survives_unicode_normalization():
    cfg = CleaningConfig(normalize_unicode=True, normalize_quotes=True)
    out = clean_text("A\n\n```\nkeep  me\n```\n\nB", cfg)
    assert "keep  me" in out


def test_heuristic_tokenizer_does_not_overcount_short_words():
    """Words up to six characters must count as a single token; the original
    ceil(len/4) formula reported 'hello world' as four tokens."""
    tk = get_tokenizer()
    assert tk.count_tokens("hello world") == 2
    assert tk.count_tokens("one two three") == 3
    assert tk.count_tokens("a") == 1
    assert tk.count_tokens("internationalization") > 3


def test_normalize_whitespace_strips_cosmetic_indent():
    assert normalize_whitespace("a  \t b \n c ") == "a b\nc"


def test_normalize_whitespace_preserves_markdown_indentation():
    text = "- item\n  continued\n\n    indented code"
    out = normalize_whitespace(text)
    assert "  continued" in out
    assert "    indented code" in out


def test_content_type_prefers_specialised_blocks_over_prose():
    """A short paragraph followed by a code block used to be labelled 'mixed',
    hiding code chunks from content-type filters."""
    text = "# Title\n\nIntro.\n\n```python\ndef a():\n    return 1\n```\n"
    chunks = build(text, target_size=200, min_size=5, max_size=400)
    assert chunks[0].metadata.content_type == "code"
    assert chunks[0].metadata.language == "python"


def test_lsh_recall_margin_finds_threshold_boundary_duplicates():
    """Banding tuned exactly at the threshold missed genuine duplicates; the
    index now biases towards recall and verifies candidates exactly."""
    base = " ".join(
        f"Sentence number {i} explains a distinct aspect of retrieval augmented generation."
        for i in range(12)
    )
    variant = base.replace("Sentence number 3", "Sentence number three")
    a, b = shingles(base, 5), shingles(variant, 5)
    assert exact_jaccard(a, b) >= 0.8
    mh = MinHash(64)
    index = LshIndex(64, 0.9)
    index.add("a", mh.signature(a))
    assert "a" in index.query(mh.signature(b))


def test_validation_issue_is_json_serializable():
    """ValidationIssue uses slots, so ``__dict__`` is unavailable; the API
    relies on ``to_dict``."""
    report = DatasetValidator().validate([])
    for issue in report.issues:
        payload = issue.to_dict()
        assert set(payload) == {"level", "code", "message", "chunk_id"}


def test_custom_strategy_name_accepted_in_config():
    """ChunkingConfig.strategy used to be a strict enum, which made registered
    custom strategies unusable from configuration."""
    from ragforge.chunking import Chunker, register_strategy
    from ragforge.chunking.base import ChunkCandidate

    class Whole(Chunker):
        name = "whole"

        def chunk(self, document):
            return [ChunkCandidate(text=document.content.strip())]

    register_strategy("whole", Whole)
    config = ChunkingConfig(strategy="whole", overlap=0)
    assert config.strategy_name == "whole"
    assert len(chunk_text("a b c", config)) == 1


def test_builtin_strategy_string_is_coerced_to_enum():
    config = ChunkingConfig(strategy="sentence")
    assert config.strategy is Strategy.SENTENCE
    assert config.strategy_name == "sentence"


def test_heading_repeated_in_every_chunk_of_a_section():
    """Only the first chunk of a section used to carry its heading, leaving
    later chunks context-free when retrieved alone."""
    body = " ".join(f"Sentence {i} carries a fair amount of information." for i in range(40))
    chunks = build(f"# Guide\n\n## Details\n\n{body}", target_size=50, min_size=10, max_size=90)
    details = [c for c in chunks if c.metadata.section == "Details"]
    assert len(details) > 1
    assert all("## Details" in c.content for c in details)


def test_overlap_does_not_duplicate_headings():
    body = " ".join(f"Sentence {i} has content worth reading." for i in range(40))
    chunks = build(f"## Section\n\n{body}", target_size=50, min_size=10, max_size=120, overlap=12)
    for chunk in chunks:
        assert chunk.content.count("## Section") == 1


def test_unclosed_code_fence_does_not_swallow_document():
    chunks = build("# A\n\n```python\nbroken = 1\n\n# B\n\nMore text after.")
    assert chunks
    assert any("More text after." in c.content for c in chunks)


def test_single_oversized_word_does_not_loop_forever():
    chunks = build("x" * 4000, unit=SizeUnit.CHARACTERS, target_size=200, min_size=20, max_size=400)
    assert 1 < len(chunks) < 100
    assert "".join(c.content for c in chunks).count("x") == 4000


def test_empty_sections_do_not_create_empty_chunks():
    chunks = build("# A\n\n## B\n\n## C\n\nOnly this section has text.")
    assert all(c.content.strip() for c in chunks)


def test_truncate_is_ascii_safe():
    """`ragforge stats`/`inspect` crashed with UnicodeEncodeError on cp1252
    Windows consoles; truncation used U+2026."""
    from ragforge.utils.text import truncate

    result = truncate("x" * 200, 40)
    assert len(result) == 40
    assert result.encode("cp1252")


def test_histogram_falls_back_to_ascii_on_legacy_encodings():
    """The size histogram used U+2588, which cp1252 cannot encode."""
    from ragforge.cli import render

    assert render.supports_unicode("cp1252") is False
    assert render.supports_unicode("utf-8") is True
    assert render.BAR_CHAR and render.ARROW


def test_parser_title_prefers_document_over_filename(tmp_path):
    """Markdown frontmatter and HTML <title> were being overwritten by a title
    derived from the filename."""
    from ragforge.parsers import get_parser

    md = tmp_path / "object-picking.md"
    md.write_text(
        "---\ntitle: GDevelop Documentation\n---\n\n# Object Picking\n\nBody.\n", encoding="utf-8"
    )
    assert get_parser(md).parse(md).title == "GDevelop Documentation"

    html = tmp_path / "page.html"
    html.write_text(
        "<html><head><title>Widget API</title></head><body><p>x</p></body></html>", encoding="utf-8"
    )
    assert get_parser(html).parse(html).title == "Widget API"

    txt = tmp_path / "release_notes.txt"
    txt.write_text("Some content without a self-declared title.\n", encoding="utf-8")
    assert get_parser(txt).parse(txt).title == "Release Notes"


def test_small_sibling_sections_are_merged():
    """Glossary/FAQ style documents produced one tiny chunk per heading."""
    text = "\n\n".join(f"## Term {i}\n\nA short definition of term {i}." for i in range(12))
    chunks = build(text, target_size=120, min_size=60, max_size=200)
    assert len(chunks) < 12
    assert all(c.metadata.size <= 200 for c in chunks)


def test_merged_sections_keep_every_heading_inline():
    """Merging small siblings must not lose either heading from the text."""
    text = "# Guide\n\n## Alpha\n\nShort one.\n\n## Beta\n\nShort two."
    chunks = build(text, target_size=200, min_size=100, max_size=300)
    merged = [c for c in chunks if "Beta" in c.content and "Alpha" in c.content]
    for chunk in merged:
        # Both headings survive verbatim, so the chunk stays self-describing.
        assert "## Alpha" in chunk.content
        assert "## Beta" in chunk.content
        assert chunk.metadata.extra.get("merged_sections")


def test_reindexing_keeps_neighbor_links_valid_after_drop(tmp_path, markdown_doc):
    """Dropping duplicates without re-linking left dangling neighbour ids."""
    from ragforge import Pipeline
    from ragforge.models.config import ForgeConfig

    path = tmp_path / "dup.md"
    path.write_text(markdown_doc + "\n\n" + markdown_doc, encoding="utf-8")
    config = ForgeConfig()
    config.chunking = ChunkingConfig(target_size=60, min_size=10, max_size=140, overlap=0)
    config.deduplication.action = "drop"
    result = Pipeline(config).run(path, write=False)
    report = DatasetValidator(config).validate(result.chunks)
    assert not [i for i in report.errors if i.code == "BROKEN_NEIGHBOR"]
