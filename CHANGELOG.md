# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Semantic role classification** (`ragforge.semantics`). Every section is
  classified as knowledge, definition, procedure, example, rule, reference,
  code, retrieval terms, document metadata or navigation. Classification is
  domain-agnostic: it combines a small vocabulary of document-organisation
  headings with measured textual shape (segment count, mean segment length,
  finite-verb ratio, table/code fractions). Shape overrides the heading, so a
  section headed *Keywords* containing prose stays knowledge, and a section
  headed *Overview* that is really 300 noun phrases is treated as terms.
- **`semantic` chunking strategy, now the default.** Builds concept-level
  semantic units (heading + explanation + definitions + rules + examples),
  merges small related siblings, and splits oversized units only at paragraph
  and sentence boundaries — never inside a definition, table row, list item,
  code block or misconception/correction pair.
- **`RetrievalMetadata` on every chunk.** Keyword, tag, alias, entity,
  related-concept and question sections become structured fields
  (`retrieval.keywords`, `retrieval.aliases`, ...) instead of ordinary
  knowledge chunks. Nothing is discarded; terms are preserved verbatim.
- **Information-loss auditing** (`ragforge.quality.CoverageAuditor`). Every
  source block is routed to `knowledge`, `metadata`, `retrieval_terms` or
  `dropped`, with a retention figure in `statistics.coverage`. `ragforge
  validate` and `ragforge stats` print the audit.
- **`retrieval_score`** quality sub-score answering "would this chunk answer a
  question?", plus flags `HEADING_ONLY`, `METADATA_ONLY`, `KEYWORD_HEAVY`,
  `ALIAS_HEAVY`, `ORPHANED_CONTEXT`, `FRAGMENTED_LIST`, `FRAGMENTED_TABLE`,
  `OVERSIZED`, `UNDERSIZED`.
- **`semantics` configuration section** and `quality.validate_information_loss`.
- CLI `--role` and `--knowledge-only` filters on `inspect`; API equivalents on
  `GET /jobs/{id}/chunks`; coverage exposed on `GET /jobs/{id}/validate`.
- `semantic_role` and `keywords` columns in the CSV export; role and retrieval
  terms in the Markdown report and `inspect` detail view.
- 78 new tests: 25 structural scenarios, classifier behaviour, a
  domain-vocabulary guard, and a BM25 + dense-embedding answerability suite.

### Changed

- **Quality weights rebalanced towards retrieval usefulness.** `length` fell
  from 0.30 to 0.10 and `retrieval` was introduced at 0.30. Previously a
  500-token dump of search aliases scored 0.96 — second-highest in the dataset
  — while a complete 150-token explanation scored 0.76.
- **Overlap rewritten.** It now applies only between pieces of a single split
  unit, inserts carried text *after* the heading, refuses tails that start with
  a heading, list marker, table row or code fence, and skips text the next
  chunk already contains. Previously it spliced a `### Heading` into the middle
  of a sentence and duplicated 12,368 characters across 41 chunks.
- `Strategy.AUTO` now selects `semantic` for structured documents.
- Content-type classification is shared by all strategies
  (`classify_content_type`), so a chunk is labelled identically regardless of
  how it was assembled.

### Fixed

- Tables and fenced diagrams were being misread as keyword lists because their
  lines are short and verb-free.
- Oversized atoms with no internal boundary (one enormous token, a minified
  line) produced a single over-limit chunk instead of being hard-split.
- An orphaned heading followed by a section with its own heading lost its text.
- `FRAGMENTED_LIST` fired on source documents that legitimately number their
  rules across several headings; it now fires only when this pipeline split the
  list.
- Merged units reported their shared ancestor heading path; they now report the
  deepest path they actually cover, so section filters still work.

### Measured on a 96 KB technical document

| Metric | Before | After |
|---|---|---|
| Chunks | 154 | 62 |
| Keyword/alias dump chunks | 10 | 0 |
| Average size | 174 tokens | 317 tokens |
| Overlap characters duplicated | 12,368 | 0 |
| Retrieval terms captured as metadata | 0 | 490 |
| Source retention | not measured | 100.00% |
| Dense top-5 slots polluted by term dumps | 8% | 0% |

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
