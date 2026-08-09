"""CLI tests using Typer's runner."""

from __future__ import annotations

import contextlib
import json

import pytest
from typer.testing import CliRunner

from ragforge import __version__
from ragforge.cli.main import app

runner = CliRunner()


def run(*args: str):
    return runner.invoke(app, list(args))


def output(result) -> str:
    """Combined stdout + stderr (errors are written to stderr by design)."""
    text = result.stdout or ""
    with contextlib.suppress(ValueError):  # streams may not be separated
        text += result.stderr or ""
    return text


# ---------------------------------------------------------------- meta
def test_version():
    result = run("--version")
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_lists_commands():
    result = run("--help")
    assert result.exit_code == 0
    for command in ("process", "inspect", "stats", "validate", "init", "serve"):
        assert command in result.stdout


def test_formats_command():
    result = run("formats")
    assert result.exit_code == 0
    assert ".md" in result.stdout
    assert "jsonl" in result.stdout
    assert "recursive" in result.stdout


# ---------------------------------------------------------------- process
def test_process_single_file(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    out = tmp_path / "out"
    result = run("process", str(source), "-o", str(out), "--chunk-size", "80", "--overlap", "10")
    assert result.exit_code == 0, result.stdout
    dataset = out / "chunks.jsonl"
    assert dataset.exists()
    lines = dataset.read_text(encoding="utf-8").strip().split("\n")
    assert lines and json.loads(lines[0])["id"]
    assert (out / "statistics.json").exists()


def test_process_directory(docs_dir, tmp_path):
    out = tmp_path / "corpus"
    result = run("process", str(docs_dir), "-o", str(out))
    assert result.exit_code == 0, result.stdout
    assert (out / "chunks.jsonl").exists()
    assert "Generated chunks" in result.stdout


def test_process_output_file_infers_format(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    target = tmp_path / "result" / "dataset.csv"
    result = run("process", str(source), "-o", str(target))
    assert result.exit_code == 0, result.stdout
    assert target.exists()
    assert target.read_text(encoding="utf-8").startswith("id,document_id,content")


@pytest.mark.parametrize("strategy", ["structural", "recursive", "sentence", "code", "auto"])
def test_process_strategies(tmp_path, markdown_doc, strategy):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    result = run("process", str(source), "-s", strategy, "-o", str(tmp_path / strategy))
    assert result.exit_code == 0, result.stdout


def test_process_dry_run_writes_nothing(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    out = tmp_path / "none"
    result = run("process", str(source), "-o", str(out), "--dry-run")
    assert result.exit_code == 0
    assert not out.exists()


def test_process_quiet_prints_paths(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    result = run("process", str(source), "-o", str(tmp_path / "q"), "--quiet")
    assert result.exit_code == 0
    assert "chunks.jsonl" in result.stdout
    assert "Generated chunks" not in result.stdout


def test_process_missing_input_is_friendly(tmp_path):
    result = run("process", str(tmp_path / "nope.md"))
    assert result.exit_code == 1
    text = output(result)
    assert "Error:" in text
    assert "Traceback" not in text


def test_debug_flag_shows_traceback(tmp_path):
    result = run("--debug", "process", str(tmp_path / "nope.md"))
    assert result.exit_code == 1
    assert isinstance(result.exception, BaseException)


def test_process_invalid_sizes(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    result = run("process", str(source), "--min-size", "900", "--max-size", "100")
    assert result.exit_code == 1
    assert "maximum must be greater than minimum" in output(result)


def test_process_unsupported_file(tmp_path):
    source = tmp_path / "a.xyz"
    source.write_text("data", encoding="utf-8")
    result = run("process", str(source), "-o", str(tmp_path / "o"))
    assert result.exit_code == 1
    assert "Unsupported file format" in output(result)


def test_process_with_config_file(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    config = tmp_path / "ragforge.yaml"
    config.write_text(
        "project:\n  name: cfg-test\nchunking:\n  target_size: 70\n  min_size: 10\n"
        f"  max_size: 200\n  overlap: 5\noutput:\n  path: {json.dumps(str(tmp_path / 'cfgout'))}\n"
        "  format: json\n",
        encoding="utf-8",
    )
    result = run("process", str(source), "-c", str(config))
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "cfgout" / "chunks.json").exists()
    assert "cfg-test" in result.stdout


def test_process_bad_config(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    config = tmp_path / "bad.yaml"
    config.write_text("chunking:\n  unknown_key: 1\n", encoding="utf-8")
    result = run("process", str(source), "-c", str(config))
    assert result.exit_code == 1
    assert "Error:" in output(result)


def test_process_show_preview(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    result = run("process", str(source), "-o", str(tmp_path / "p"), "--show", "5")
    assert result.exit_code == 0
    assert "Chunks (" in result.stdout


# ---------------------------------------------------------------- inspect
def test_inspect_source_document(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    result = run("inspect", str(source), "--limit", "5")
    assert result.exit_code == 0
    assert "Chunks (" in result.stdout


def test_inspect_dataset(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    out = tmp_path / "out"
    run("process", str(source), "-o", str(out))
    result = run("inspect", str(out / "chunks.jsonl"))
    assert result.exit_code == 0
    assert "Chunks (" in result.stdout


def test_inspect_search_filter(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    result = run("inspect", str(source), "--search", "sub-events")
    assert result.exit_code == 0
    assert "Chunks (1)" in result.stdout or "Chunks (2)" in result.stdout


def test_inspect_no_matches(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    result = run("inspect", str(source), "--search", "zzzznotpresent")
    assert result.exit_code == 0
    assert "No chunks matched" in result.stdout


def test_inspect_single_chunk_by_index(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    result = run("inspect", str(source), "--chunk", "0")
    assert result.exit_code == 0
    assert "Content" in result.stdout
    assert "Heading path" in result.stdout


def test_inspect_missing_chunk(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    result = run("inspect", str(source), "--chunk", "nonexistent-id")
    assert result.exit_code == 1


def test_inspect_section_filter(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    result = run("inspect", str(source), "--section", "Example")
    assert result.exit_code == 0


# ---------------------------------------------------------------- stats
def test_stats_command(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    result = run("stats", str(source))
    assert result.exit_code == 0
    assert "Generated chunks" in result.stdout
    assert "distribution" in result.stdout


def test_stats_json_output(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    result = run("stats", str(source), "--json")
    assert result.exit_code == 0
    assert '"total_chunks"' in result.stdout


def test_stats_save(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    target = tmp_path / "s" / "statistics.json"
    result = run("stats", str(source), "--save", str(target))
    assert result.exit_code == 0
    assert json.loads(target.read_text(encoding="utf-8"))["total_chunks"] > 0


# ---------------------------------------------------------------- validate
def test_validate_good_dataset(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    out = tmp_path / "out"
    run("process", str(source), "-o", str(out), "--chunk-size", "80")
    result = run("validate", str(out / "chunks.jsonl"))
    assert result.exit_code == 0


def test_validate_broken_dataset(tmp_path):
    dataset = tmp_path / "broken.jsonl"
    dataset.write_text(
        json.dumps({"id": "a", "content": "", "metadata": {"next_chunk": "ghost"}}) + "\n",
        encoding="utf-8",
    )
    result = run("validate", str(dataset))
    assert result.exit_code == 1
    assert "EMPTY_CONTENT" in result.stdout


def test_validate_malformed_dataset(tmp_path):
    dataset = tmp_path / "bad.jsonl"
    dataset.write_text("{not json}\n", encoding="utf-8")
    result = run("validate", str(dataset))
    assert result.exit_code == 1
    assert "Error:" in output(result)


# ---------------------------------------------------------------- convert
def test_convert_jsonl_to_csv(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    out = tmp_path / "out"
    run("process", str(source), "-o", str(out))
    target = tmp_path / "converted.csv"
    result = run("convert", str(out / "chunks.jsonl"), str(target))
    assert result.exit_code == 0
    assert target.read_text(encoding="utf-8").startswith("id,document_id")


def test_convert_to_markdown(tmp_path, markdown_doc):
    source = tmp_path / "doc.md"
    source.write_text(markdown_doc, encoding="utf-8")
    out = tmp_path / "out"
    run("process", str(source), "-o", str(out))
    target = tmp_path / "report.md"
    result = run("convert", str(out / "chunks.jsonl"), str(target))
    assert result.exit_code == 0
    assert "# Chunk inspection report" in target.read_text(encoding="utf-8")


# ---------------------------------------------------------------- init
def test_init_creates_config(tmp_path):
    target = tmp_path / "ragforge.yaml"
    result = run("init", str(target))
    assert result.exit_code == 0
    text = target.read_text(encoding="utf-8")
    assert "strategy: recursive" in text

    import yaml

    from ragforge.models.config import ForgeConfig

    assert ForgeConfig.from_mapping(yaml.safe_load(text)).chunking.target_size == 500


def test_init_refuses_overwrite(tmp_path):
    target = tmp_path / "ragforge.yaml"
    target.write_text("existing", encoding="utf-8")
    assert run("init", str(target)).exit_code == 1
    assert run("init", str(target), "--force").exit_code == 0
