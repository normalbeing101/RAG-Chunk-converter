"""Quality scoring and dataset validation tests."""

from __future__ import annotations

from ragforge.models.chunk import Chunk, ChunkMetadata, QualityFlag
from ragforge.models.config import ChunkingConfig, ForgeConfig, QualityConfig
from ragforge.quality import DatasetValidator, QualityScorer

CHUNKING = ChunkingConfig(target_size=100, min_size=40, max_size=200, overlap=0)


def make(content: str, **meta) -> Chunk:
    defaults = {
        "document_id": "d1",
        "title": "Doc",
        "source": "doc.md",
        "heading_path": ["Section"],
        "size": len(content.split()),
    }
    defaults.update(meta)
    return Chunk(id=meta.get("chunk_id", "c1"), content=content, metadata=ChunkMetadata(**defaults))


def score(chunk: Chunk):
    return QualityScorer(QualityConfig(), CHUNKING).score(chunk)


GOOD = (
    "Object picking determines which instances of an object are selected by a condition. "
    "When the condition evaluates, the engine maintains an internal list of picked instances. "
    "Subsequent actions then operate only on those picked instances rather than every object."
)


# ---------------------------------------------------------------- scoring
def test_good_chunk_scores_high():
    quality = score(make(GOOD, size=100))
    assert quality.quality_score > 0.7
    assert QualityFlag.BROKEN_SENTENCE not in quality.flags
    assert QualityFlag.TOO_SHORT not in quality.flags


def test_too_short_flagged():
    quality = score(make("Tiny.", size=2))
    assert QualityFlag.TOO_SHORT in quality.flags
    assert quality.length_score < 0.5


def test_too_long_flagged():
    quality = score(make(GOOD, size=500))
    assert QualityFlag.TOO_LONG in quality.flags


def test_broken_sentence_flagged():
    chunk = make("The object is destroyed when the condition is triggered and the action", size=100)
    assert QualityFlag.BROKEN_SENTENCE in score(chunk).flags


def test_lowercase_start_flagged():
    chunk = make(
        "and then the remaining instances are processed by the following action.", size=100
    )
    assert QualityFlag.BROKEN_SENTENCE in score(chunk).flags


def test_code_split_flagged():
    chunk = make("```python\ndef f():", size=100, content_type="code", extra={"code_split": True})
    assert QualityFlag.CODE_SPLIT in score(chunk).flags


def test_unbalanced_fence_flagged():
    chunk = make("```python\ndef f():\n    return 1", size=100, content_type="code")
    assert QualityFlag.CODE_SPLIT in score(chunk).flags


def test_balanced_code_chunk_ok():
    chunk = make("```python\ndef f():\n    return 1\n```", size=100, content_type="code")
    assert QualityFlag.CODE_SPLIT not in score(chunk).flags


def test_low_context_flagged():
    chunk = make("Short text.", size=100, heading_path=[], title="", source="")
    assert QualityFlag.LOW_CONTEXT in score(chunk).flags


def test_context_score_rewards_heading_path():
    shallow = score(make(GOOD, size=100, heading_path=[]))
    deep = score(make(GOOD, size=100, heading_path=["A", "B", "C"]))
    assert deep.context_score > shallow.context_score


def test_low_information_flagged():
    chunk = make("the the the and and of of of to to to", size=100)
    assert QualityFlag.LOW_INFORMATION in score(chunk).flags


def test_duplicate_flag_propagated():
    chunk = make(GOOD, size=100, duplicate_of="other", extra={"duplicate_kind": "NEAR_DUPLICATE"})
    assert QualityFlag.NEAR_DUPLICATE in score(chunk).flags


def test_table_chunk_not_flagged_as_broken():
    chunk = make("| a | b |\n| --- | --- |\n| 1 | 2 |", size=100, content_type="table")
    assert QualityFlag.BROKEN_SENTENCE not in score(chunk).flags


def test_list_chunk_not_flagged_as_broken():
    chunk = make("- first item\n- second item\n- third item", size=100, content_type="list")
    assert QualityFlag.BROKEN_SENTENCE not in score(chunk).flags


def test_scores_are_bounded():
    for content in ["", "x", GOOD, GOOD * 20, "```\n```"]:
        quality = score(make(content or "x", size=len(content)))
        for value in (
            quality.quality_score,
            quality.length_score,
            quality.coherence_score,
            quality.context_score,
            quality.information_score,
        ):
            assert 0.0 <= value <= 1.0


def test_scoring_disabled():
    chunks = [make(GOOD)]
    QualityScorer(QualityConfig(enabled=False), CHUNKING).score_all(chunks)
    assert chunks[0].quality is None


def test_score_all_assigns_quality():
    chunks = [make(GOOD, chunk_id=f"c{i}") for i in range(3)]
    QualityScorer(QualityConfig(), CHUNKING).score_all(chunks)
    assert all(c.quality is not None for c in chunks)


# ---------------------------------------------------------------- validation
def test_validate_empty_dataset():
    report = DatasetValidator().validate([])
    assert report.ok
    assert any(i.code == "EMPTY_DATASET" for i in report.issues)


def test_validate_detects_duplicate_ids():
    chunks = [make(GOOD, chunk_id="same"), make(GOOD + " More.", chunk_id="same")]
    chunks[0].id = chunks[1].id = "same"
    report = DatasetValidator().validate(chunks)
    assert not report.ok
    assert any(i.code == "DUPLICATE_ID" for i in report.errors)


def test_validate_detects_broken_neighbors():
    chunk = make(GOOD, chunk_id="c1", next_chunk="missing")
    chunk.id = "c1"
    report = DatasetValidator().validate([chunk])
    assert any(i.code == "BROKEN_NEIGHBOR" for i in report.errors)


def test_validate_detects_empty_content():
    chunk = Chunk(id="c1", content="   ")
    report = DatasetValidator().validate([chunk])
    assert any(i.code == "EMPTY_CONTENT" for i in report.errors)


def test_validate_size_warnings():
    config = ForgeConfig()
    config.chunking = CHUNKING
    chunks = [make(GOOD, chunk_id="c1", size=500)]
    chunks[0].id = "c1"
    report = DatasetValidator(config).validate(chunks)
    assert any(i.code == "OVERSIZED" for i in report.warnings)


def test_validate_high_duplication_warning():
    chunks = []
    for i in range(4):
        chunk = make(GOOD, chunk_id=f"c{i}", duplicate_of="c0" if i else None)
        chunk.id = f"c{i}"
        chunks.append(chunk)
    report = DatasetValidator().validate(chunks)
    assert any(i.code == "HIGH_DUPLICATION" for i in report.warnings)


def test_validate_summary_counts():
    chunk = Chunk(id="", content="")
    report = DatasetValidator().validate([chunk])
    summary = report.summary()
    assert summary.get("MISSING_ID") == 1
    assert summary.get("EMPTY_CONTENT") == 1
