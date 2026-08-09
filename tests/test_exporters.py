"""Exporter tests."""

from __future__ import annotations

import csv
import json

import pytest

from ragforge.errors import ExportError
from ragforge.exporters import available_formats, get_exporter, write_statistics
from ragforge.models.chunk import Chunk, ChunkMetadata, ChunkQuality, QualityFlag
from ragforge.models.config import OutputConfig
from ragforge.models.result import Statistics


@pytest.fixture
def chunks() -> list[Chunk]:
    return [
        Chunk(
            id=f"c{i}",
            content=f'Chunk {i} content with a comma, a "quote" and a newline.\nSecond line.',
            metadata=ChunkMetadata(
                document_id="d1",
                title="Doc",
                source="doc.md",
                section=f"S{i}",
                heading_path=["Root", f"S{i}"],
                chunk_index=i,
                total_chunks=3,
                content_type="text",
                size=42,
                unit="tokens",
            ),
            quality=ChunkQuality(quality_score=0.8, flags=[QualityFlag.TOO_SHORT] if i else []),
            context_prefix="Document: Doc",
        )
        for i in range(3)
    ]


def test_available_formats():
    assert set(available_formats()) >= {"jsonl", "json", "csv", "markdown"}


def test_unknown_format_raises():
    with pytest.raises(ExportError):
        get_exporter("xml")


# ---------------------------------------------------------------- jsonl
def test_jsonl_export(tmp_path, chunks):
    path = get_exporter("jsonl").write(chunks, tmp_path / "out.jsonl")
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3
    record = json.loads(lines[0])
    assert record["id"] == "c0"
    assert record["metadata"]["heading_path"] == ["Root", "S0"]
    assert record["quality"]["quality_score"] == 0.8
    assert record["context_prefix"] == "Document: Doc"


def test_jsonl_unicode_preserved(tmp_path):
    chunk = Chunk(id="u", content="中文 → 🚀")
    path = get_exporter("jsonl").write([chunk], tmp_path / "u.jsonl")
    assert "中文 → 🚀" in path.read_text(encoding="utf-8")


def test_jsonl_exclude_quality(tmp_path, chunks):
    exporter = get_exporter("jsonl", OutputConfig(include_quality=False))
    path = exporter.write(chunks, tmp_path / "nq.jsonl")
    assert "quality" not in json.loads(path.read_text(encoding="utf-8").split("\n")[0])


def test_jsonl_empty_dataset(tmp_path):
    path = get_exporter("jsonl").write([], tmp_path / "empty.jsonl")
    assert path.read_text(encoding="utf-8") == ""


# ---------------------------------------------------------------- json
def test_json_export(tmp_path, chunks):
    path = get_exporter("json").write(chunks, tmp_path / "out.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert len(payload["documents"]) == 3
    assert payload["documents"][2]["metadata"]["section"] == "S2"


# ---------------------------------------------------------------- csv
def test_csv_export(tmp_path, chunks):
    path = get_exporter("csv").write(chunks, tmp_path / "out.csv")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert list(rows[0]) == [
        "id",
        "document_id",
        "content",
        "title",
        "section",
        "source",
        "chunk_index",
        "content_type",
    ]
    assert "Second line." in rows[0]["content"]


# ---------------------------------------------------------------- markdown
def test_markdown_export(tmp_path, chunks):
    path = get_exporter("markdown").write(chunks, tmp_path / "out.md")
    text = path.read_text(encoding="utf-8")
    assert "# Chunk inspection report" in text
    assert "## `c0`" in text
    assert "Root > S0" in text
    assert "TOO_SHORT" in text


# ---------------------------------------------------------------- misc
def test_directories_are_created(tmp_path, chunks):
    target = tmp_path / "a" / "b" / "out.jsonl"
    get_exporter("jsonl").write(chunks, target)
    assert target.exists()


def test_overwrite_protection(tmp_path, chunks):
    target = tmp_path / "out.jsonl"
    target.write_text("existing", encoding="utf-8")
    exporter = get_exporter("jsonl", OutputConfig(overwrite=False))
    with pytest.raises(ExportError):
        exporter.write(chunks, target)


def test_statistics_export(tmp_path, chunks):
    statistics = Statistics.from_chunks(chunks, project="p", strategy="recursive")
    path = write_statistics(statistics, tmp_path / "statistics.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["total_chunks"] == 3
    assert payload["project"] == "p"
    assert payload["chunks_by_content_type"] == {"text": 3}


def test_statistics_histogram_and_percentiles():
    chunks = [
        Chunk(id=f"c{i}", content="x", metadata=ChunkMetadata(size=i * 10)) for i in range(1, 21)
    ]
    statistics = Statistics.from_chunks(chunks)
    assert statistics.min_size == 10
    assert statistics.max_size == 200
    assert statistics.median_size == 105
    assert statistics.p95_size > statistics.median_size
    assert sum(b["count"] for b in statistics.size_histogram) == 20


def test_statistics_of_empty_dataset():
    statistics = Statistics.from_chunks([])
    assert statistics.total_chunks == 0
    assert statistics.average_size == 0
