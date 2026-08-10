"""Semantic classification and semantic chunking.

Covers the 25 structural scenarios the chunker must handle correctly, plus the
knowledge-vs-retrieval-metadata separation that motivated the redesign.
"""

from __future__ import annotations

import pytest

from ragforge.chunking import chunk_text
from ragforge.models.config import ChunkingConfig, SemanticsConfig, Strategy
from ragforge.semantics import (
    RoleClassifier,
    SemanticRole,
    TermField,
    extract_terms,
    heading_intent,
    measure_shape,
    normalize_heading,
)


def build(text: str, **kwargs):
    defaults = {
        "strategy": Strategy.SEMANTIC,
        "target_size": 300,
        "min_size": 80,
        "max_size": 600,
        "overlap": 0,
    }
    defaults.update(kwargs)
    return chunk_text(text, ChunkingConfig(**defaults), title="Doc", source="doc.md")


def body_of(chunk) -> str:
    return "\n".join(
        line for line in chunk.content.split("\n") if not line.lstrip().startswith("#")
    ).strip()


# ======================================================================
# Heading intent - domain-agnostic
# ======================================================================
def test_normalize_heading_strips_ordinals_and_markup():
    assert normalize_heading("## 3.1 Keywords") == "keywords"
    assert normalize_heading("**Tags**") == "tags"
    assert normalize_heading("Section 4 - Examples") == "examples"
    assert normalize_heading("`Chunk ID`") == "chunk id"


@pytest.mark.parametrize(
    ("heading", "role"),
    [
        ("Keywords", SemanticRole.RETRIEVAL_TERMS),
        ("Tags", SemanticRole.RETRIEVAL_TERMS),
        ("Alternative Terms and Search Aliases", SemanticRole.RETRIEVAL_TERMS),
        ("Important Entities", SemanticRole.RETRIEVAL_TERMS),
        ("Related Topics", SemanticRole.RETRIEVAL_TERMS),
        ("Metadata", SemanticRole.DOCUMENT_META),
        ("Table of Contents", SemanticRole.NAVIGATION),
        ("Definitions", SemanticRole.DEFINITION),
        ("Procedures", SemanticRole.PROCEDURE),
        ("Examples", SemanticRole.EXAMPLE),
        ("Best Practices", SemanticRole.RULE),
        ("Common Mistakes", SemanticRole.RULE),
        ("API Reference", SemanticRole.REFERENCE),
    ],
)
def test_heading_intent_recognises_organisation_labels(heading, role):
    result = heading_intent(heading)
    assert result is not None
    assert result[0] is role


def test_heading_intent_ignores_subject_matter():
    """Only document-organisation labels are recognised, never domain terms."""
    for heading in ("Photosynthesis", "Kubernetes Ingress", "Baroque Music", "Widgets"):
        assert heading_intent(heading) is None


def test_classifier_has_no_domain_vocabulary():
    """Guard against someone hardcoding the test corpus into the classifier."""
    from pathlib import Path

    source = Path("ragforge/semantics/classifier.py").read_text(encoding="utf-8").casefold()
    for banned in ("gdevelop", "gdjs", "gdcpp", "pixi", "sfml", "event sheet"):
        assert banned not in source, f"domain term {banned!r} leaked into the classifier"


# ======================================================================
# Shape measurement
# ======================================================================
def test_shape_detects_semicolon_term_dump():
    text = "; ".join(f"widget term number {i}" for i in range(40))
    shape = measure_shape(text)
    assert shape.segments >= 30
    assert shape.verb_segment_ratio < 0.25
    assert shape.is_term_list


def test_shape_rejects_prose_with_many_sentences():
    text = " ".join(
        f"The component number {i} initialises its state before the update runs." for i in range(12)
    )
    shape = measure_shape(text)
    assert shape.verb_segment_ratio >= 0.5
    assert not shape.is_term_list


def test_shape_excludes_fenced_code_from_term_detection():
    diagram = "```text\n" + "\n".join(f"Step{i}\n  |\n  v" for i in range(12)) + "\n```"
    shape = measure_shape(diagram)
    assert shape.fenced_fraction > 0.9
    assert not shape.is_term_list


def test_shape_excludes_tables_from_term_detection():
    rows = "\n".join(f"| item{i} | value{i} |" for i in range(20))
    shape = measure_shape(f"| a | b |\n| --- | --- |\n{rows}")
    assert shape.table_fraction > 0.9
    assert not shape.is_term_list


def test_shape_counts_questions():
    text = "\n".join(f"{i}. How does feature {i} behave?" for i in range(1, 9))
    assert measure_shape(text).is_question_list


# ======================================================================
# Term extraction
# ======================================================================
def test_extract_terms_from_semicolons_and_bullets():
    assert extract_terms("alpha; beta; gamma") == ["alpha", "beta", "gamma"]
    assert extract_terms("- alpha\n- beta\n- gamma") == ["alpha", "beta", "gamma"]
    assert extract_terms("`alpha`, `beta`, `gamma`") == ["alpha", "beta", "gamma"]


def test_extract_terms_deduplicates_case_insensitively():
    assert extract_terms("Alpha; alpha; ALPHA; beta") == ["Alpha", "beta"]


# ======================================================================
# Classification decisions
# ======================================================================
def test_keyword_dump_classified_as_retrieval_terms():
    text = "; ".join(f"product feature {i}" for i in range(60))
    result = RoleClassifier().classify_text(text, heading="Keywords")
    assert result.role is SemanticRole.RETRIEVAL_TERMS
    assert result.field is TermField.KEYWORDS
    assert len(result.terms) >= 50


def test_prose_under_a_keywords_heading_stays_knowledge():
    """Shape overrides the heading label."""
    text = (
        "Keywords are chosen to reflect the vocabulary a reader is likely to use. "
        "The engine indexes them separately from the body text. "
        "This keeps the embedding focused on meaning rather than on synonyms."
    )
    result = RoleClassifier().classify_text(text, heading="Keywords")
    assert result.role is SemanticRole.KNOWLEDGE


def test_term_dump_without_a_matching_heading_is_still_detected():
    text = "; ".join(f"alpha variant {i}" for i in range(40))
    result = RoleClassifier().classify_text(text, heading="Overview")
    assert result.role is SemanticRole.RETRIEVAL_TERMS


def test_short_frontmatter_is_document_metadata():
    result = RoleClassifier().classify_text("`doc-001-v2`", heading="Chunk ID")
    assert result.role is SemanticRole.DOCUMENT_META


def test_long_prose_under_metadata_heading_stays_knowledge():
    text = " ".join(
        f"Sentence {i} explains a substantive part of the subject in detail." for i in range(14)
    )
    result = RoleClassifier().classify_text(text, heading="Metadata")
    assert result.role is SemanticRole.KNOWLEDGE


def test_question_list_becomes_query_metadata():
    text = "\n".join(f"{i}. What happens when step {i} runs?" for i in range(1, 12))
    result = RoleClassifier().classify_text(text, heading="Common Questions")
    assert result.role is SemanticRole.RETRIEVAL_TERMS
    assert result.field is TermField.QUESTIONS


def test_classification_can_be_disabled():
    text = "; ".join(f"term {i}" for i in range(40))
    result = RoleClassifier(enabled=False).classify_text(text, heading="Keywords")
    assert result.role is SemanticRole.KNOWLEDGE


# ======================================================================
# 1-25: structural scenarios
# ======================================================================
def test_01_heading_only_section_does_not_produce_a_chunk():
    chunks = build("# Guide\n\n## Empty Section\n\n## Real Section\n\nActual content here.")
    for chunk in chunks:
        assert body_of(chunk), f"heading-only chunk emitted: {chunk.content!r}"


def test_01b_orphan_heading_attaches_to_following_content():
    chunks = build("## Orphan\n\n## Real\n\nThe explanation lives here and is substantive.")
    joined = " ".join(c.content for c in chunks)
    assert "Orphan" in joined
    assert "## Real" in joined


def test_01d_absorbed_ancestor_heading_renders_above_its_child():
    """An empty parent heading belongs above the child heading, not inside the body."""
    chunks = build("## Parent\n\n### Child\n\nThe explanation of the child concept.")
    content = chunks[0].content
    assert "## Parent" in content and "### Child" in content
    assert content.index("## Parent") < content.index("### Child")


def test_01c_trailing_heading_with_no_content_is_preserved():
    chunks = build("# A\n\nBody text that explains something.\n\n## Trailing")
    assert "Trailing" in " ".join(c.content for c in chunks)


def test_02_heading_plus_paragraph_stay_together():
    chunks = build("## Concept\n\nThe concept is explained in this paragraph.")
    assert len(chunks) == 1
    assert "## Concept" in chunks[0].content
    assert "explained" in chunks[0].content


def test_03_multiple_paragraphs_under_one_heading():
    text = "## Topic\n\n" + "\n\n".join(
        f"Paragraph {i} describes an aspect of the topic in a complete sentence." for i in range(4)
    )
    chunks = build(text)
    assert len(chunks) == 1
    assert all(f"Paragraph {i}" in chunks[0].content for i in range(4))


def test_04_nested_headings_recorded_in_path():
    text = "# A\n\nIntro paragraph.\n\n## B\n\nMiddle paragraph.\n\n### C\n\nDeep paragraph here."
    chunks = build(text, target_size=40, min_size=10, max_size=90)
    deep = [c for c in chunks if "Deep paragraph" in c.content]
    assert deep
    assert deep[0].metadata.heading_path[-1] == "C"
    assert "A" in deep[0].metadata.heading_path


def test_05_bullet_list_stays_coherent():
    text = "## Steps\n\n" + "\n".join(
        f"- The system performs operation {i} before continuing." for i in range(6)
    )
    chunks = build(text)
    assert len(chunks) == 1
    assert chunks[0].content.count("- The system") == 6


def test_06_numbered_list_keeps_order():
    text = "## Procedure\n\n" + "\n".join(
        f"{i}. Perform action number {i} and verify the outcome." for i in range(1, 8)
    )
    chunks = build(text)
    joined = " ".join(c.content for c in chunks)
    positions = [joined.index(f"{i}. Perform") for i in range(1, 8)]
    assert positions == sorted(positions)


def test_07_table_stays_intact_when_it_fits():
    text = (
        "## Reference\n\n| Level | Meaning |\n| --- | --- |\n"
        "| HIGH | The claim is directly supported. |\n"
        "| LOW | The claim is inferred. |"
    )
    chunks = build(text)
    assert len(chunks) == 1
    assert "| HIGH |" in chunks[0].content
    assert "| --- |" in chunks[0].content


def test_07b_oversized_table_repeats_its_header():
    rows = "\n".join(f"| name{i} | description number {i} of the row |" for i in range(50))
    text = f"## Big\n\n| name | description |\n| --- | --- |\n{rows}"
    chunks = build(text, target_size=80, min_size=20, max_size=140, keep_tables_intact=False)
    assert len(chunks) > 1
    for chunk in chunks:
        assert "| name | description |" in chunk.content


def test_08_code_block_stays_intact():
    text = (
        "## Usage\n\nCall the function like this.\n\n```python\ndef run(x):\n    return x * 2\n```"
    )
    chunks = build(text)
    assert len(chunks) == 1
    assert chunks[0].content.count("```") == 2
    assert chunks[0].metadata.language == "python"


def test_08b_code_never_split_mid_statement():
    body = "\n\n".join(f"def fn_{i}(a):\n    return a + {i}" for i in range(20))
    chunks = build(f"```python\n{body}\n```", target_size=60, min_size=15, max_size=110)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.content.count("```") % 2 == 0
        assert "def fn_" in chunk.content


def test_09_example_keeps_its_concept():
    text = (
        "## Object Selection\n\nSelection narrows the working set.\n\n"
        "### Example\n\nWhen the filter matches two rows, only those rows are updated."
    )
    chunks = build(text)
    joined = " ".join(c.content for c in chunks)
    assert "Selection narrows" in joined
    assert "only those rows" in joined


def test_10_definitions_keep_term_and_meaning_together():
    text = "## Glossary\n\n### Frame\n\nOne iteration of the update cycle.\n\n### Tick\n\nA synonym for a frame update."
    chunks = build(text)
    for chunk in chunks:
        if "Frame" in chunk.content:
            assert "iteration of the update cycle" in chunk.content


def test_11_procedure_role_detected():
    text = "## How to Deploy\n\n" + "\n".join(
        f"{i}. Run the deployment command for stage {i} and confirm it succeeded."
        for i in range(1, 7)
    )
    chunks = build(text)
    assert chunks[0].metadata.semantic_role == SemanticRole.PROCEDURE.value


def test_12_metadata_section_marked_not_dropped():
    text = "# Doc\n\n## Metadata\n\n### Category\n\nReference.\n\n## Body\n\nThe real explanation lives here."
    chunks = build(text)
    roles = {c.metadata.semantic_role for c in chunks}
    assert SemanticRole.DOCUMENT_META.value in roles
    assert any("Reference." in c.content for c in chunks), "metadata content was lost"


def test_13_keyword_section_becomes_metadata_not_a_chunk():
    keywords = "; ".join(f"search phrase number {i}" for i in range(60))
    text = f"# Doc\n\n## Keywords\n\n{keywords}\n\n## Body\n\nThis paragraph carries the real knowledge."
    chunks = build(text)
    for chunk in chunks:
        assert "search phrase number 30" not in chunk.content
    assert any(len(c.retrieval.keywords) >= 50 for c in chunks)


def test_14_alias_section_becomes_metadata():
    aliases = "; ".join(f"widget alias {i}" for i in range(50))
    text = f"# Doc\n\n## Search Aliases\n\n{aliases}\n\n## Body\n\nThe explanation of the widget behaviour."
    chunks = build(text)
    assert all("widget alias 25" not in c.content for c in chunks)
    assert any(c.retrieval.aliases for c in chunks)


def test_14b_tags_entities_and_related_concepts_map_to_their_fields():
    text = (
        "# Doc\n\n"
        "## Tags\n\n" + ", ".join(f"`tag{i}`" for i in range(12)) + "\n\n"
        "## Important Entities\n\n" + "\n".join(f"- Entity{i}" for i in range(10)) + "\n\n"
        "## Related Topics\n\n" + "; ".join(f"topic {i}" for i in range(10)) + "\n\n"
        "## Body\n\nThe substantive explanation of the subject matter."
    )
    chunks = build(text)
    knowledge = [c for c in chunks if c.is_knowledge]
    assert knowledge
    retrieval = knowledge[0].retrieval
    assert retrieval.tags and retrieval.entities and retrieval.related_concepts


def test_15_mixed_content_section_holds_together():
    text = (
        "## Mixed\n\nIntro sentence explaining the topic.\n\n"
        "- first bullet point of substance\n- second bullet point of substance\n\n"
        "```python\nvalue = compute()\n```\n\nClosing sentence that wraps up."
    )
    chunks = build(text)
    assert len(chunks) == 1
    assert "Intro sentence" in chunks[0].content
    assert "```python" in chunks[0].content
    assert "Closing sentence" in chunks[0].content


def test_16_oversized_section_splits_at_semantic_boundaries():
    paragraphs = "\n\n".join(
        f"Paragraph {i} contains several complete sentences. It explains one aspect "
        f"thoroughly. It then concludes cleanly."
        for i in range(30)
    )
    chunks = build(f"## Long\n\n{paragraphs}", target_size=120, min_size=40, max_size=220)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.metadata.size <= 220
        assert "## Long" in chunk.content  # heading repeated: still self-describing
        assert body_of(chunk).rstrip().endswith(".")


def test_17_tiny_sections_merge():
    text = "# Doc\n\n" + "\n\n".join(f"## T{i}\n\nShort note {i}." for i in range(12))
    chunks = build(text, target_size=200, min_size=100, max_size=400)
    assert len(chunks) < 12
    assert all(f"Short note {i}" in " ".join(c.content for c in chunks) for i in range(12))


def test_18_duplicate_sections_detected():
    """Two identical sections far enough apart to become separate chunks."""
    from ragforge.deduplication import Deduplicator
    from ragforge.models.config import DeduplicationConfig

    para = " ".join(
        f"Sentence {i} explains how the subsystem evaluates its inputs deterministically."
        for i in range(10)
    )
    filler = " ".join(f"Unrelated statement {i} about a different area." for i in range(10))
    text = f"## A\n\n{para}\n\n## Middle\n\n{filler}\n\n## B\n\n{para}"
    chunks = build(text, target_size=100, min_size=40, max_size=180)
    assert len(chunks) >= 3
    result = Deduplicator(DeduplicationConfig()).run(chunks)
    assert result.total >= 1
    assert any(c.metadata.duplicate_of for c in chunks)


def test_19_near_duplicates_detected():
    from ragforge.deduplication import Deduplicator
    from ragforge.models.config import DeduplicationConfig

    base = " ".join(
        f"Sentence {i} states a verifiable fact about the subsystem behaviour." for i in range(12)
    )
    variant = base.replace("Sentence 3", "Sentence three")
    filler = " ".join(f"Different topic sentence {i} entirely." for i in range(12))
    text = f"## A\n\n{base}\n\n## Middle\n\n{filler}\n\n## B\n\n{variant}"
    chunks = build(text, target_size=120, min_size=40, max_size=220)
    result = Deduplicator(DeduplicationConfig(similarity_threshold=0.8)).run(chunks)
    assert result.near_duplicates + result.exact_duplicates >= 1


def test_20_document_without_headings():
    text = " ".join(
        f"Sentence {i} conveys a distinct piece of information about the topic." for i in range(40)
    )
    chunks = build(text, target_size=80, min_size=20, max_size=160)
    assert chunks
    assert all(c.metadata.size <= 160 for c in chunks)


def test_21_deep_heading_hierarchy():
    text = "".join(
        f"\n\n{'#' * d} Level {d}\n\nContent at depth {d} explained fully." for d in range(1, 7)
    )
    chunks = build(text, target_size=40, min_size=10, max_size=100)
    deepest = max(chunks, key=lambda c: len(c.metadata.heading_path))
    assert len(deepest.metadata.heading_path) >= 4


def test_22_unicode_preserved():
    text = "## Título\n\nEl símbolo → indica flujo. 中文内容也应该正常工作。 Emoji: 🚀 works fine."
    chunks = build(text)
    joined = " ".join(c.content for c in chunks)
    assert "→" in joined and "中文内容" in joined and "🚀" in joined


def test_23_empty_document():
    assert build("") == []
    assert build("   \n\n \t ") == []


def test_24_malformed_markdown_does_not_crash():
    for text in (
        "# A\n\n```python\nbroken = 1\n\n# B\n\nMore text after the unclosed fence.",
        "| broken | table\n| no separator",
        "####### seven hashes is not a heading\n\nBody text follows.",
        "- \n- \n- \n\nReal content after empty bullets.",
        "\x00\x07 control characters \x1f here",
    ):
        chunks = build(text)
        assert all(c.content.strip() for c in chunks)


def test_25_very_large_document():
    text = "\n\n".join(
        f"## Section {i}\n\nParagraph {i} contains a reasonable amount of explanatory prose "
        f"so the chunker has genuine work to do here."
        for i in range(600)
    )
    chunks = build(text, target_size=300, min_size=80, max_size=600)
    assert chunks
    assert all(c.metadata.size <= 600 for c in chunks)


# ======================================================================
# Configuration
# ======================================================================
def test_separation_can_be_disabled():
    keywords = "; ".join(f"term {i}" for i in range(50))
    text = f"# Doc\n\n## Keywords\n\n{keywords}\n\n## Body\n\nReal explanatory content lives here."
    from ragforge.chunking.engine import ChunkingEngine
    from ragforge.models.document import Document
    from ragforge.preprocessing import StructureAnalyzer

    document = StructureAnalyzer().analyze(Document(content=text, source="d.md", title="D"))
    engine = ChunkingEngine(
        ChunkingConfig(
            strategy=Strategy.SEMANTIC, target_size=300, min_size=50, max_size=600, overlap=0
        ),
        SemanticsConfig(enabled=False),
    )
    chunks = engine.chunk_document(document)
    assert any("term 25" in c.content for c in chunks)


def test_max_terms_per_field_is_respected():
    from ragforge.chunking.engine import ChunkingEngine
    from ragforge.models.document import Document
    from ragforge.preprocessing import StructureAnalyzer

    keywords = "; ".join(f"term {i}" for i in range(300))
    text = f"# Doc\n\n## Keywords\n\n{keywords}\n\n## Body\n\nReal explanatory content lives here."
    document = StructureAnalyzer().analyze(Document(content=text, source="d.md", title="D"))
    engine = ChunkingEngine(
        ChunkingConfig(
            strategy=Strategy.SEMANTIC, target_size=300, min_size=50, max_size=600, overlap=0
        ),
        SemanticsConfig(max_terms_per_field=25),
    )
    chunks = engine.chunk_document(document)
    assert all(len(c.retrieval.keywords) <= 25 for c in chunks)
