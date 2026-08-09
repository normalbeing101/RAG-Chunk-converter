"""Tests for data models and configuration."""

from __future__ import annotations

import pytest

from ragforge.errors import ConfigError
from ragforge.models.chunk import Chunk, ChunkMetadata, ChunkQuality, QualityFlag
from ragforge.models.config import (
    ChunkingConfig,
    ForgeConfig,
    OverlapUnit,
    SizeUnit,
    Strategy,
)
from ragforge.models.document import Block, BlockType, Document


def test_document_gets_stable_id():
    a = Document(title="T", source="a.md", content="hello")
    b = Document(title="T", source="a.md", content="hello")
    assert a.id == b.id
    assert a.id.startswith("doc_")


def test_document_with_content_resets_structure():
    doc = Document(source="a.md", content="x")
    doc = doc.model_copy(update={"structure": None})
    updated = doc.with_content("y")
    assert updated.content == "y"
    assert updated.structure is None


def test_block_section_helpers():
    heading = Block(type=BlockType.HEADING, text="Child", level=2, heading_path=["Parent"])
    assert heading.section == "Child"
    assert heading.parent_section == "Parent"
    assert heading.full_path() == ["Parent", "Child"]

    paragraph = Block(type=BlockType.PARAGRAPH, text="body", heading_path=["Parent", "Child"])
    assert paragraph.section == "Child"
    assert paragraph.parent_section == "Parent"
    assert paragraph.full_path() == ["Parent", "Child"]


def test_block_type_flags():
    assert BlockType.CODE.is_atomic
    assert BlockType.TABLE.is_atomic
    assert BlockType.PARAGRAPH.is_prose
    assert not BlockType.CODE.is_prose


def test_chunk_record_roundtrip():
    chunk = Chunk(
        id="c1",
        content="hello",
        metadata=ChunkMetadata(document_id="d1", title="T", source="s.md"),
        quality=ChunkQuality(quality_score=0.5, flags=[QualityFlag.TOO_SHORT]),
        context_prefix="Document: T",
    )
    record = chunk.to_record()
    assert record["id"] == "c1"
    assert record["metadata"]["document_id"] == "d1"
    assert record["quality"]["flags"] == ["TOO_SHORT"]
    assert record["context_prefix"] == "Document: T"
    assert chunk.text_for_embedding.startswith("Document: T")

    flat = chunk.flat_record()
    assert set(flat) == {
        "id",
        "document_id",
        "content",
        "title",
        "section",
        "source",
        "chunk_index",
        "content_type",
    }


def test_chunk_record_without_quality():
    chunk = Chunk(id="c", content="x")
    record = chunk.to_record(include_quality=False)
    assert "quality" not in record


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_size": 400, "max_size": 100, "target_size": 200},
        {"target_size": 900, "max_size": 800, "min_size": 100},
        {"target_size": 50, "min_size": 100, "max_size": 800},
    ],
)
def test_invalid_sizes_raise_config_error(kwargs):
    with pytest.raises(ConfigError):
        ChunkingConfig(**kwargs)


def test_overlap_must_be_smaller_than_target():
    with pytest.raises(ConfigError):
        ChunkingConfig(target_size=100, overlap=100, min_size=10, max_size=200)


def test_percentage_overlap_resolution():
    cfg = ChunkingConfig(target_size=500, overlap=15, overlap_unit=OverlapUnit.PERCENTAGE)
    assert cfg.resolved_overlap() == 75


def test_percentage_overlap_over_100_rejected():
    with pytest.raises(ConfigError):
        ChunkingConfig(overlap=150, overlap_unit=OverlapUnit.PERCENTAGE)


def test_config_from_mapping_with_aliases():
    cfg = ForgeConfig.from_mapping(
        {
            "chunking": {"chunk_size": 300, "min_size": 50, "max_size": 600},
            "deduplication": {"threshold": 0.8},
        }
    )
    assert cfg.chunking.target_size == 300
    assert cfg.deduplication.similarity_threshold == 0.8


def test_config_rejects_unknown_keys():
    with pytest.raises(ConfigError):
        ForgeConfig.from_mapping({"chunking": {"nope": 1}})


def test_config_load_yaml(tmp_path):
    path = tmp_path / "ragforge.yaml"
    path.write_text(
        "project:\n  name: demo\nchunking:\n  strategy: sentence\n  target_size: 200\n"
        "  min_size: 20\n  max_size: 400\n  overlap: 20\n",
        encoding="utf-8",
    )
    cfg = ForgeConfig.load(path)
    assert cfg.project.name == "demo"
    assert cfg.chunking.strategy is Strategy.SENTENCE
    assert cfg.chunking.unit is SizeUnit.TOKENS


def test_config_load_json(tmp_path):
    path = tmp_path / "ragforge.json"
    path.write_text('{"project": {"name": "j"}}', encoding="utf-8")
    assert ForgeConfig.load(path).project.name == "j"


def test_config_load_missing_file(tmp_path):
    with pytest.raises(ConfigError):
        ForgeConfig.load(tmp_path / "nope.yaml")


def test_config_load_bad_extension(tmp_path):
    path = tmp_path / "conf.ini"
    path.write_text("x=1", encoding="utf-8")
    with pytest.raises(ConfigError):
        ForgeConfig.load(path)


def test_config_discovery(tmp_path):
    (tmp_path / "ragforge.yaml").write_text("project:\n  name: found\n", encoding="utf-8")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    cfg = ForgeConfig.discover(nested)
    assert cfg is not None
    assert cfg.project.name == "found"


def test_config_to_yaml_roundtrip():
    cfg = ForgeConfig()
    text = cfg.to_yaml()
    assert "chunking:" in text
    import yaml

    assert ForgeConfig.from_mapping(yaml.safe_load(text)).chunking.target_size == 500
