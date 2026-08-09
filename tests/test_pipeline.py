"""End-to-end pipeline tests."""

from __future__ import annotations

import json

import pytest

from ragforge import Pipeline, process
from ragforge.errors import InputError
from ragforge.models.config import ForgeConfig, OutputFormat, Strategy
from ragforge.pipeline import discover_inputs
from ragforge.utils.progress import CallbackProgress


def test_process_single_file(tmp_path, config, markdown_doc):
    path = tmp_path / "doc.md"
    path.write_text(markdown_doc, encoding="utf-8")
    result = Pipeline(config).run(path, write=False)
    assert result.chunks
    assert result.statistics.documents == 1
    assert result.statistics.total_chunks == len(result.chunks)
    assert all(c.metadata.source.endswith("doc.md") for c in result.chunks)


def test_process_directory(docs_dir, config):
    result = Pipeline(config).run(docs_dir, write=False)
    assert result.statistics.documents >= 5
    sources = {c.metadata.source for c in result.chunks}
    assert any(s.endswith("guide.md") for s in sources)
    assert any(s.endswith("deep.md") for s in sources)
    assert any(s.endswith("data.csv") for s in sources)


def test_non_recursive_directory(docs_dir, config):
    result = Pipeline(config).run(docs_dir, recursive=False, write=False)
    assert not any(c.metadata.source.endswith("deep.md") for c in result.chunks)


def test_missing_path_raises(tmp_path, config):
    with pytest.raises(InputError):
        Pipeline(config).run(tmp_path / "nope.md", write=False)


def test_empty_directory_raises(tmp_path, config):
    (tmp_path / "empty").mkdir()
    with pytest.raises(InputError):
        Pipeline(config).run(tmp_path / "empty", write=False)


def test_unsupported_files_ignored_in_directory(docs_dir, config):
    (docs_dir / "image.png").write_bytes(b"\x89PNG\r\n")
    result = Pipeline(config).run(docs_dir, write=False)
    assert not any(c.metadata.source.endswith(".png") for c in result.chunks)


def test_unsupported_single_file_reported(tmp_path, config):
    path = tmp_path / "thing.xyz"
    path.write_text("data", encoding="utf-8")
    result = Pipeline(config).run(path, write=False)
    assert result.failed
    assert "Unsupported file format" in result.failed[0].error


def test_malformed_input_does_not_abort_run(docs_dir, config):
    (docs_dir / "broken.json").write_text("{ not json", encoding="utf-8")
    result = Pipeline(config).run(docs_dir, write=False)
    assert result.chunks
    assert any("broken.json" in (r.source or "") for r in result.failed)


def test_writes_outputs(tmp_path, docs_dir, config):
    config.output.path = str(tmp_path / "out")
    config.output.format = OutputFormat.JSONL
    result = Pipeline(config).run(docs_dir, write=True)
    assert len(result.outputs) == 2
    dataset = tmp_path / "out" / "chunks.jsonl"
    statistics = tmp_path / "out" / "statistics.json"
    assert dataset.exists() and statistics.exists()
    lines = dataset.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == len(result.chunks)
    assert json.loads(lines[0])["id"]
    assert json.loads(statistics.read_text(encoding="utf-8"))["total_chunks"] == len(result.chunks)


@pytest.mark.parametrize("fmt", ["jsonl", "json", "csv", "markdown"])
def test_all_output_formats(tmp_path, docs_dir, config, fmt):
    config.output.path = str(tmp_path / fmt)
    config.output.format = OutputFormat(fmt)
    result = Pipeline(config).run(docs_dir, write=True)
    assert all(p for p in result.outputs)
    from pathlib import Path

    assert Path(result.outputs[0]).stat().st_size > 0


def test_process_text_helper(config, markdown_doc):
    document, chunks = Pipeline(config).process_text(markdown_doc, title="T", source="s.md")
    assert document.title == "T"
    assert chunks
    assert chunks[0].metadata.title == "T"


def test_neighbors_and_indices_after_dedup(tmp_path, config, markdown_doc):
    path = tmp_path / "dup.md"
    path.write_text(markdown_doc + "\n\n" + markdown_doc, encoding="utf-8")
    config.deduplication.action = "drop"
    result = Pipeline(config).run(path, write=False)
    ids = {c.id for c in result.chunks}
    for index, chunk in enumerate(result.chunks):
        assert chunk.metadata.chunk_index == index
        assert chunk.metadata.total_chunks == len(result.chunks)
        if chunk.metadata.next_chunk:
            assert chunk.metadata.next_chunk in ids
        if chunk.metadata.previous_chunk:
            assert chunk.metadata.previous_chunk in ids


def test_duplicates_flagged_across_documents(tmp_path, config, markdown_doc):
    (tmp_path / "a.md").write_text(markdown_doc, encoding="utf-8")
    (tmp_path / "b.md").write_text(markdown_doc, encoding="utf-8")
    result = Pipeline(config).run(tmp_path, write=False)
    assert result.statistics.duplicates > 0


def test_quality_scores_present(docs_dir, config):
    result = Pipeline(config).run(docs_dir, write=False)
    assert all(c.quality is not None for c in result.chunks)
    assert 0 <= result.statistics.average_quality <= 1


def test_drop_low_quality(docs_dir, config):
    config.quality.drop_low_quality = True
    config.quality.min_quality_score = 0.99
    result = Pipeline(config).run(docs_dir, write=False)
    assert result.statistics.total_chunks == 0 or all(
        c.quality.quality_score >= 0.99 for c in result.chunks
    )


def test_progress_callback(docs_dir, config):
    events: list[tuple[int, int, str]] = []
    reporter = CallbackProgress(lambda done, total, detail: events.append((done, total, detail)))
    Pipeline(config, progress=reporter).run(docs_dir, write=False)
    assert events
    assert events[-1][0] == events[-1][1]


def test_process_helper_function(docs_dir):
    result = process(docs_dir, ForgeConfig(), write=False)
    assert result.statistics.documents >= 5


def test_discover_inputs_deduplicates(docs_dir):
    paths = list(discover_inputs([docs_dir, docs_dir / "guide.md"]))
    assert len(paths) == len({p.resolve() for p in paths})


def test_discover_inputs_skips_vendor_dirs(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.md").write_text("# x", encoding="utf-8")
    (tmp_path / "keep.md").write_text("# keep", encoding="utf-8")
    paths = [p.name for p in discover_inputs(tmp_path)]
    assert paths == ["keep.md"]


def test_empty_document_produces_no_chunks(tmp_path, config):
    path = tmp_path / "empty.md"
    path.write_text("   \n\n  ", encoding="utf-8")
    result = Pipeline(config).run(path, write=False)
    assert result.chunks == []
    assert not result.failed


def test_large_document_streaming(tmp_path, config):
    path = tmp_path / "big.md"
    body = "\n\n".join(
        f"## Section {i}\n\nParagraph {i} contains a reasonable amount of text for chunking."
        for i in range(1500)
    )
    path.write_text(body, encoding="utf-8")
    result = Pipeline(config).run(path, write=False)
    assert result.statistics.total_chunks > 500
    assert result.statistics.elapsed_seconds >= 0


def test_strategy_recorded_in_metadata(tmp_path, config, markdown_doc):
    config.chunking.strategy = Strategy.SENTENCE
    path = tmp_path / "s.md"
    path.write_text(markdown_doc, encoding="utf-8")
    result = Pipeline(config).run(path, write=False)
    assert all(c.metadata.strategy == "sentence" for c in result.chunks)
    assert result.statistics.strategy == "sentence"


def test_iter_chunks_streams(docs_dir, config):
    from collections.abc import Iterator

    stream = Pipeline(config).iter_chunks(docs_dir)
    assert isinstance(stream, Iterator)
    chunks = list(stream)
    assert chunks
    assert all(c.quality is not None for c in chunks)


def test_iter_chunks_skips_broken_documents(docs_dir, config):
    (docs_dir / "broken.json").write_text("{ not json", encoding="utf-8")
    assert list(Pipeline(config).iter_chunks(docs_dir))


def test_stream_to_file_matches_run(tmp_path, docs_dir, config):
    target = tmp_path / "stream" / "chunks.jsonl"
    Pipeline(config).stream_to_file(docs_dir, target)
    lines = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line]
    assert lines
    assert all(record["id"] and record["content"] for record in lines)

    batch = Pipeline(config).run(docs_dir, write=False)
    assert len(lines) >= len(batch.chunks) - 1


def test_embeddings_optional(tmp_path, config, markdown_doc):
    config.embeddings.enabled = True
    config.embeddings.provider = "hash"
    config.embeddings.dimensions = 32
    path = tmp_path / "e.md"
    path.write_text(markdown_doc, encoding="utf-8")
    result = Pipeline(config).run(path, write=False)
    assert all(c.embedding is not None and len(c.embedding) == 32 for c in result.chunks)
