# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-09

First public release.

### Added

**Parsers**
- Plain text (`.txt`, `.text`, `.log`, `.rst`) with encoding and BOM detection.
- Markdown (`.md`, `.mdx`, ...) with YAML frontmatter and setext heading support.
- HTML (`.html`, `.htm`) via the standard library, converting to Markdown and
  dropping `script`/`style`/`nav`/`header`/`footer` boilerplate.
- JSON and JSONL (`.json`, `.jsonl`, `.ndjson`) flattened into readable sections.
- CSV and TSV (`.csv`, `.tsv`) in record or table rendering mode.
- PDF (`.pdf`) via optional `pypdf`, with hyphenation repair, paragraph reflow,
  repeated header/footer removal and heading promotion.
- Pluggable parser registry (`register_parser`).

**Preprocessing**
- Configurable cleaner: whitespace, blank lines, Unicode NFKC, typographic
  quotes, zero-width and control characters, navigation text, repeated
  headers/footers, URLs. Fenced code blocks are protected from all of it.
- Structure analyzer producing typed blocks (title, heading, paragraph, list,
  numbered list, table, code, quote) with a resolved heading hierarchy and
  source offsets.

**Chunking**
- Four strategies plus `auto`: `structural`, `recursive`, `sentence`, `code`.
- Size configuration in characters, words or tokens, with a dependency-free
  token estimator and optional exact `tiktoken` counting.
- Boundary-aware overlap (paragraph → sentence → line → word), expressible as a
  percentage or absolute amount, never applied across section boundaries.
- Code blocks split only at logical boundaries and always re-fenced.
- Tables split by rows with the header repeated; lists split at item boundaries.
- Small-chunk merging and per-section heading repetition for self-contained chunks.
- Custom strategies via `register_strategy`.

**Context, quality and deduplication**
- Heading path, section/parent section, parent section id, previous/next chunk
  ids and an optional `context_prefix`.
- Exact (SHA-256) and near-duplicate (MinHash + banded LSH) detection with
  `flag` or `drop` behaviour, global or per-document scope.
- LLM-free quality scoring: length, coherence, context and information
  sub-scores with `TOO_SHORT`, `TOO_LONG`, `LOW_CONTEXT`, `DUPLICATE`,
  `NEAR_DUPLICATE`, `BROKEN_SENTENCE`, `CODE_SPLIT`, `LOW_INFORMATION` and
  `MIXED_TOPICS` flags.
- Dataset validator checking ids, neighbour links, empty content, size bounds
  and duplication ratio.

**Output**
- JSONL, JSON, CSV and Markdown exporters plus `statistics.json` with size
  histogram and breakdowns by document, section and content type.
- Optional embedding pipeline with `hash`, `sentence-transformers`, `ollama`
  and OpenAI-compatible providers behind a common interface.

**Interfaces**
- `ragforge` CLI: `process`, `inspect`, `stats`, `validate`, `convert`, `init`,
  `formats`, `serve`, with Rich progress and tables, `--debug` tracebacks and
  human-readable errors.
- FastAPI REST API: `/process`, `/process/text`, `/jobs`, `/jobs/{id}`,
  `/jobs/{id}/chunks`, `/statistics`, `/validate`, `/preview`, `/export`.
- Dependency-free web inspection UI: upload, configure, browse, search, view
  metadata and quality, highlighted chunk boundaries, distribution charts and
  dataset export.

**Project**
- Full test suite (330+ tests) covering parsers, cleaning, structure, every
  chunking strategy, overlap, deduplication, quality, exporters, the pipeline,
  the CLI, the API and regressions.
- GitHub Actions for lint, test (Linux/macOS/Windows × Python 3.11-3.13) and build.

[Unreleased]: https://github.com/your-org/rag-chunkforge/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/your-org/rag-chunkforge/releases/tag/v0.1.0
