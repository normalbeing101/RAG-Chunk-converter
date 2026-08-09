"""Cleaning and structural analysis tests."""

from __future__ import annotations

from ragforge.models.config import CleaningConfig
from ragforge.models.document import BlockType
from ragforge.preprocessing import StructureAnalyzer, TextCleaner, analyze, clean_text


# ---------------------------------------------------------------- cleaning
def test_collapse_blank_lines_and_whitespace():
    out = clean_text("a  \t b\n\n\n\n\nc   ")
    assert out == "a b\n\nc"


def test_unicode_normalization():
    cfg = CleaningConfig(normalize_unicode=True)
    assert clean_text("ﬁle", cfg) == "file"


def test_quote_normalization_optional():
    text = "\u201cquoted\u201d and \u2019apostrophe\u2019"
    assert "\u201c" in clean_text(text, CleaningConfig(normalize_quotes=False))
    assert '"quoted"' in clean_text(text, CleaningConfig(normalize_quotes=True))


def test_code_blocks_are_preserved_exactly():
    text = "Intro\n\n```python\ndef f():\n    x  =  1\n\n\n    return x\n```\n\nOutro"
    out = clean_text(text)
    assert "    x  =  1" in out
    assert "```python" in out
    assert out.count("```") == 2


def test_cleaning_disabled_is_noop():
    text = "a  \n\n\n\nb"
    assert clean_text(text, CleaningConfig(enabled=False)) == text


def test_navigation_removal():
    cfg = CleaningConfig(remove_navigation=True)
    out = clean_text("Skip to content\nReal content here.\nBack to top", cfg)
    assert "Real content here." in out
    assert "Skip to content" not in out
    assert "Back to top" not in out


def test_repeated_header_removal():
    cfg = CleaningConfig(remove_headers=True, remove_footers=True, min_repeats_for_boilerplate=2)
    page = "ACME CONFIDENTIAL\nContent {}\nPage footer\n"
    text = "\n\n\n".join(page.format(i) for i in range(6))
    out = TextCleaner(cfg).clean(text)
    assert "ACME CONFIDENTIAL" not in out
    assert "Content 3" in out


def test_url_removal_optional():
    cfg = CleaningConfig(remove_urls=True)
    assert "https://" not in clean_text("see https://example.com now", cfg)


def test_zero_width_and_control_chars_removed():
    assert clean_text("a\u200bb\x07c") == "abc"


def test_empty_input():
    assert clean_text("") == ""


# ---------------------------------------------------------------- structure
def test_heading_hierarchy(markdown_doc):
    structure = analyze(markdown_doc)
    assert structure.has_headings
    assert structure.max_heading_depth == 3
    deep = [
        b
        for b in structure.blocks
        if b.heading_path == ["Object Picking", "How it works", "Object picking in sub-events"]
    ]
    assert deep, "expected blocks under the third-level heading"


def test_block_types_detected(markdown_doc):
    structure = analyze(markdown_doc)
    types = {b.type for b in structure.blocks}
    assert BlockType.CODE in types
    assert BlockType.TABLE in types
    assert BlockType.LIST in types
    assert BlockType.QUOTE in types
    assert BlockType.PARAGRAPH in types


def test_code_block_language_and_integrity():
    structure = analyze("```python\nprint('hi')\nprint('there')\n```")
    code = [b for b in structure.blocks if b.type is BlockType.CODE]
    assert len(code) == 1
    assert code[0].language == "python"
    assert code[0].metadata["closed"] is True
    assert code[0].text.count("```") == 2


def test_unclosed_code_block():
    structure = analyze("```js\nlet a = 1;\n")
    code = [b for b in structure.blocks if b.type is BlockType.CODE]
    assert code and code[0].metadata["closed"] is False


def test_headings_inside_code_not_treated_as_headings():
    structure = analyze("```\n# fake heading\n```\n\n# real heading\n")
    headings = [b for b in structure.blocks if b.is_heading]
    assert len(headings) == 1
    assert headings[0].text == "real heading"


def test_numbered_list_detected():
    structure = analyze("1. first\n2. second\n3. third\n")
    assert structure.blocks[0].type is BlockType.NUMBERED_LIST
    assert structure.blocks[0].metadata["items"] == 3


def test_table_requires_two_rows():
    structure = analyze("| just one |\n")
    assert structure.blocks[0].type is not BlockType.TABLE


def test_table_detection_with_header():
    structure = analyze("| a | b |\n| --- | --- |\n| 1 | 2 |\n")
    table = structure.blocks[0]
    assert table.type is BlockType.TABLE
    assert table.metadata["has_header"] is True
    assert table.metadata["rows"] == 3


def test_first_heading_is_title():
    structure = analyze("# Title\n\nBody\n\n## Second\n\nMore")
    assert structure.blocks[0].type is BlockType.TITLE
    assert structure.blocks[2].type is BlockType.HEADING


def test_offsets_are_consistent():
    text = "# H\n\nParagraph one.\n\nParagraph two.\n"
    structure = analyze(text)
    for block in structure.blocks:
        assert text[block.start_offset : block.start_offset + 3].strip()
        assert block.end_offset >= block.start_offset


def test_empty_document_structure():
    structure = analyze("")
    assert structure.blocks == []
    assert not structure.has_headings


def test_analyzer_attaches_structure_to_document(markdown_doc):
    from ragforge.models.document import Document

    doc = Document(content=markdown_doc, source="a.md")
    analyzed = StructureAnalyzer().analyze(doc)
    assert analyzed.structure is not None
    assert len(analyzed.blocks) > 5


def test_horizontal_rule_skipped():
    structure = analyze("a\n\n---\n\nb")
    assert all(b.type is not BlockType.HORIZONTAL_RULE for b in structure.blocks)
    assert len(structure.blocks) == 2


def test_indented_code_block():
    structure = analyze("Intro:\n\n    code line one\n    code line two\n\nAfter")
    assert any(b.type is BlockType.CODE for b in structure.blocks)
