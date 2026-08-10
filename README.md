# RAG ChunkForge

**Intelligent, structure-aware document chunking for production RAG pipelines.**

[![lint](https://github.com/your-org/rag-chunkforge/actions/workflows/lint.yml/badge.svg)](https://github.com/your-org/rag-chunkforge/actions/workflows/lint.yml)
[![test](https://github.com/your-org/rag-chunkforge/actions/workflows/test.yml/badge.svg)](https://github.com/your-org/rag-chunkforge/actions/workflows/test.yml)
[![build](https://github.com/your-org/rag-chunkforge/actions/workflows/build.yml/badge.svg)](https://github.com/your-org/rag-chunkforge/actions/workflows/build.yml)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

RAG ChunkForge turns large documents into **semantically coherent, context-rich
chunks** that actually retrieve well - instead of arbitrary N-character slices.

```text
Large document
      ↓  parse        (.txt .md .html .json .csv .pdf)
      ↓  clean        (unicode, whitespace, boilerplate - all opt-in)
      ↓  analyze      (headings, paragraphs, lists, tables, code, quotes)
      ↓  classify     (knowledge vs keywords/tags/aliases vs front-matter)
      ↓  chunk        (semantic / structural / recursive / sentence / code)
      ↓  enrich       (heading path, parents, neighbours, context prefix)
      ↓  deduplicate  (exact + MinHash near-duplicates)
      ↓  score        (retrieval usefulness, information, coherence, context)
      ↓  audit        (every source block accounted for - zero silent loss)
      ↓  export       (jsonl / json / csv / markdown + statistics)
RAG-ready dataset
```

---

## Table of contents

- [Why intelligent chunking matters](#why-intelligent-chunking-matters)
- [Knowledge vs retrieval metadata](#knowledge-vs-retrieval-metadata)
- [Features](#features)
- [Installation](#installation)
- [Quick start](#quick-start)
- [CLI reference](#cli-reference)
- [Configuration](#configuration)
- [Chunking strategies](#chunking-strategies)
- [Output schema](#output-schema)
- [Python API](#python-api)
- [REST API](#rest-api)
- [Web interface](#web-interface)
- [Architecture](#architecture)
- [Development](#development)
- [Testing](#testing)
- [Contributing](#contributing)
- [Roadmap](#roadmap)
- [License](#license)

---

## Why intelligent chunking matters

Retrieval quality is decided long before the LLM sees anything. A naive
`text[i:i+1000]` splitter destroys exactly the signal your retriever depends on.

### Bad chunk (fixed-size splitter)

```text
...instances of an object are selected by conditions.

## Example

If the player overlaps an enemy, the enemy can be sel
```

Three problems: it starts mid-sentence, it merges two unrelated sections, and it
ends mid-word. Embedded, this vector points at nothing in particular.

### Good chunk (RAG ChunkForge)

```json
{
  "id": "doc_9f1c2a_chunk_0001",
  "content": "## How it works\n\nWhen a condition is evaluated, GDevelop maintains a list of picked instances. Actions can then operate only on those instances.",
  "metadata": {
    "section": "How it works",
    "parent_section": "Object Picking",
    "heading_path": ["Object Picking", "How it works"],
    "content_type": "text",
    "previous_chunk": "doc_9f1c2a_chunk_0000",
    "next_chunk": "doc_9f1c2a_chunk_0002",
    "parent_id": "doc_9f1c2a_section_3b8e1d02"
  },
  "context_prefix": "Document: GDevelop Documentation\nSection: Object Picking > How it works",
  "quality": { "quality_score": 0.91, "flags": [] }
}
```

Self-contained, complete sentences, one topic, and enough metadata for a
retriever to expand context to its neighbours or its parent section.

> **Design principle:** optimise for *retrieval quality*, not chunk size.
> A 650-token chunk containing one complete concept beats a 500-token chunk
> containing three unrelated ones.

---

## Knowledge vs retrieval metadata

Technical documents are full of sections that are useful for *finding*
information but are not information themselves:

```text
## Keywords
event execution order; runtime execution; frame lifecycle; scene lifecycle;
event sheet order; event evaluation pipeline; conditions and actions; ...
(300 more)
```

A naive chunker turns that into a 500-token chunk. It looks great by every
size-based metric - long, coherent, keyword-rich - and it is **useless**. It
answers no question, and because it contains every term in the document, its
embedding sits close to *every* query about the document. It crowds out the
chunks that hold the real answers.

RAG ChunkForge classifies each section by **what it is for**, then routes it:

| Source section | Destination | Result |
|---|---|---|
| Explanations, rules, procedures, examples | `content` | a retrievable knowledge chunk |
| Keywords, tags, aliases, entities, related topics | `retrieval.*` | structured metadata fields |
| Anticipated questions | `retrieval.questions` | query-side matching signal |
| Chunk ID, category, difficulty, authoring notes | role-marked chunk | filterable, not deleted |

**Nothing is discarded.** Every term is preserved verbatim in a structured
field, and the coverage audit proves it:

```text
Information-loss audit
  Destination        Blocks    Words
  knowledge             842   13,741
  retrieval_terms         2        7
Retention 100.00% (13,748 source words, 0 unaccounted block(s))
```

### Measured impact

Same 96 KB document, before and after:

| Metric | Before | After |
|---|---|---|
| Chunks | 154 | **62** |
| Keyword/alias dump chunks | 10 | **0** |
| Average size | 174 tokens | **317 tokens** |
| Overlap chars duplicated | 12,368 | **0** |
| Chunks with >200 duplicated chars | 41 | **0** |
| Retrieval terms captured as metadata | 0 | **490** |
| Source retention | not measured | **100.00%** |
| Dense top-5 slots polluted by term dumps | 8% | **0%** |

That last row is the one that matters. BM25 discounts keyword dumps
automatically through IDF, so lexical search hides the problem — but dense
embedding retrieval, which is what RAG actually uses, does not.

### Classification is domain-agnostic

The classifier never matches subject vocabulary. It combines two signals:

1. **Heading intent** — a small vocabulary of *document-organisation* words
   (`keywords`, `glossary`, `procedure`, `see also`) that authors reuse in
   every field. `Photosynthesis` and `Kubernetes Ingress` match nothing.
2. **Textual shape** — segment count, mean segment length, the fraction of
   segments containing a finite verb, table/code ratios.

**Shape wins.** A section headed *Keywords* that contains real prose is kept as
knowledge; a section headed *Overview* that is really 300 semicolon-separated
noun phrases is extracted as terms. A test asserts no domain term ever leaks
into the classifier source.

---

## Features

| | |
|---|---|
| **6 input formats** | `.txt` `.md` `.html` `.json`/`.jsonl` `.csv`/`.tsv` `.pdf` - pluggable registry |
| **Structure detection** | titles, headings (hierarchy preserved), paragraphs, bullet/numbered lists, tables, fenced & indented code, quotes |
| **Semantic classification** | knowledge / definition / procedure / example / rule / reference / code vs keywords, tags, aliases, entities, front-matter |
| **5 strategies + auto** | `semantic` (default), `structural`, `recursive`, `sentence`, `code`, `auto` |
| **Size units** | characters, words, tokens (heuristic estimator or exact `tiktoken`) |
| **Smart overlap** | only between pieces of one split unit, at paragraph/sentence boundaries, never duplicating headings or fences |
| **Context enrichment** | heading path, parent section id, previous/next chunk, optional `context_prefix` |
| **Deduplication** | exact hashing + MinHash/LSH near-duplicates (sub-quadratic, no external deps) |
| **Quality scoring** | LLM-free, retrieval-weighted: `KEYWORD_HEAVY`, `HEADING_ONLY`, `METADATA_ONLY`, `FRAGMENTED_TABLE`, `ORPHANED_CONTEXT`, ... |
| **Information-loss audit** | every source block routed to knowledge / metadata / terms, with a retention figure |
| **Exports** | JSONL, JSON, CSV, Markdown report, `statistics.json` |
| **Embeddings** | optional, provider-agnostic (`hash`, sentence-transformers, Ollama, OpenAI-compatible) |
| **Interfaces** | polished Typer CLI, FastAPI REST API, zero-build web inspection UI |

Core dependencies: `pydantic`, `typer`, `rich`, `PyYAML`. Everything else is optional.

---

## Installation

```bash
pip install rag-chunkforge              # core
pip install "rag-chunkforge[pdf]"       # + PDF parsing
pip install "rag-chunkforge[api]"       # + REST API and web UI
pip install "rag-chunkforge[all]"       # everything
```

From source:

```bash
git clone https://github.com/your-org/rag-chunkforge.git
cd rag-chunkforge
pip install -e ".[dev]"
```

Requires **Python 3.11+**.

---

## Quick start

```bash
# One document → output/chunks.jsonl + output/statistics.json
ragforge process input/documentation.md

# A whole directory, tuned
ragforge process ./documents/ \
    --strategy recursive \
    --chunk-size 500 \
    --overlap 75 \
    --output chunks.jsonl

# Inspect what you produced
ragforge inspect output/chunks.jsonl --limit 30
ragforge inspect output/chunks.jsonl --chunk doc_9f1c2a_chunk_0007
ragforge inspect output/chunks.jsonl --search "object picking" --flagged
ragforge inspect output/chunks.jsonl --knowledge-only     # hide front-matter
ragforge inspect output/chunks.jsonl --role document_meta # inspect what was set aside

# Statistics and distribution charts
ragforge stats output/chunks.jsonl

# Validate before you embed
ragforge validate output/chunks.jsonl --strict

# Browse in a local web UI
ragforge serve
```

Typical `stats` output:

```text
Documents:        12
Original tokens:  184,230
Generated chunks: 421
Average size:     437 tokens
Median size:      421 tokens
Duplicates:       8
Warnings:         13
```

---

## CLI reference

| Command | Purpose |
|---|---|
| `ragforge process <paths...>` | Chunk files/directories and export a dataset |
| `ragforge inspect <target>` | Browse, search and filter chunks |
| `ragforge stats <target>` | Statistics, size histogram, breakdowns |
| `ragforge validate <target>` | Structural validation of a dataset |
| `ragforge convert <in> <out>` | Convert a dataset between formats |
| `ragforge init [path]` | Write a starter `ragforge.yaml` |
| `ragforge formats` | List input/output formats and strategies |
| `ragforge serve` | Start REST API + web UI |

`<target>` accepts a source document, a directory, **or** an already exported
`.jsonl`/`.json` dataset - the CLI detects which.

### `process` options

```text
-c, --config PATH        YAML/JSON configuration file
-s, --strategy NAME      semantic | structural | recursive | sentence | code | auto
    --chunk-size N       target size
    --min-size N         minimum size
    --max-size N         maximum size
    --overlap N          overlap amount
-u, --unit UNIT          characters | words | tokens
    --tokenizer SPEC     heuristic | tiktoken:cl100k_base
-o, --output PATH        output file or directory
-f, --format FMT         jsonl | json | csv | markdown
    --no-recursive       do not walk subdirectories
    --no-dedup           disable deduplication
    --no-clean           disable text cleaning
    --no-context         disable context enrichment
    --dry-run            process without writing
    --show N             preview N chunks afterwards
-q, --quiet              print only output paths
    --debug              full tracebacks (global flag)
```

Errors are human-readable by default:

```text
Error: Unsupported file format: .xyz
Hint: Supported formats: .csv, .htm, .html, .json, .jsonl, .md, .pdf, .txt, ...

Error: Invalid chunk size: maximum must be greater than minimum (max_size=100, min_size=400).

Error: Unable to parse manual.pdf: document appears corrupted
```

---

## Configuration

Generate one with `ragforge init`. RAG ChunkForge also auto-discovers
`ragforge.yaml` / `ragforge.yml` / `ragforge.json` by walking up from the input
path. CLI flags always win over the file.

```yaml
project:
  name: my-rag-dataset

chunking:
  strategy: semantic       # semantic | structural | recursive | sentence | code | auto
  target_size: 500
  min_size: 100
  max_size: 800
  overlap: 75
  unit: tokens             # characters | words | tokens
  overlap_unit: same       # same | percentage | characters | words | tokens
  tokenizer: heuristic     # or tiktoken:cl100k_base
  keep_code_blocks_intact: true
  keep_tables_intact: true

semantics:
  enabled: true
  separate_retrieval_metadata: true   # keywords/tags/aliases -> metadata fields
  keep_document_metadata: true        # front-matter kept, role-marked
  min_terms: 5                        # segments needed to call it a term list
  max_terms_per_field: 256
  include_terms_in_embedding_text: false

quality:
  validate_information_loss: true     # account for every source block

cleaning:
  normalize_unicode: true
  remove_headers: true
  remove_footers: true
  preserve_code_blocks: true

deduplication:
  enabled: true
  threshold: 0.92          # alias of similarity_threshold
  action: flag             # flag | drop

context:
  include_heading_path: true
  include_source: true
  include_context_prefix: true

output:
  format: jsonl
  path: output
  filename: chunks
```

> There is no universally correct chunk size. Start at 500 tokens / 75 overlap,
> then use `ragforge stats` and `ragforge validate` to tune for your corpus.

---

## Chunking strategies

### `semantic` *(default)*

Five stages:

1. **Classify** every section by semantic role.
2. **Build semantic units** — a heading plus the explanation, definitions,
   rules and examples that belong to the same concept.
3. **Merge** small related units (siblings or parent/child) up to the target
   size. A glossary of 30 one-line terms becomes a handful of usable chunks
   instead of 30 unusable ones.
4. **Split** oversized units at paragraph → sentence boundaries only, never
   inside a definition, table row, list item, code block or
   misconception/correction pair. The heading is repeated on every piece.
5. **Route** keyword/tag/alias sections into `retrieval.*` metadata fields and
   mark front-matter with its role.

Guarantees: no heading-only chunks, no keyword-dump chunks, tables keep their
header, code stays fenced, procedures keep their order.

### `structural`

Splits `document → sections → subsections → paragraphs`. A paragraph is never
split unless it alone exceeds the maximum. Best for well-structured
documentation and handbooks.

### `recursive` *(default)*

Applies the separator hierarchy
`heading → paragraph → line → sentence → word → character`, descending only when
the current unit still exceeds the target, then greedily re-merging small pieces
back toward the target size. Best general-purpose choice.

### `sentence`

Guarantees every boundary is a sentence boundary.

```text
Bad:  "The object is destroyed when the condition is
       triggered and the action..."

Good: "The object is destroyed when the condition is triggered."
      "The action can be executed whenever the condition becomes true."
```

### `code`

Code blocks become first-class chunks and are never blindly cut. Oversized
blocks are split at logical boundaries (`def`/`class`/`function`/`impl`, blank-line
groups) and re-fenced, with `content_type: "code"` and `language` recorded.

### `auto`

Inspects the parsed structure and picks `code`, `semantic` or `sentence`.

All strategies share the same guarantees: chunks never cross a section boundary,
tables keep their header row when split, and lists split at item boundaries.

---

## Output schema

### JSONL (one object per line)

```json
{"id":"doc_9f1c2a_chunk_0042","content":"...","metadata":{...},"quality":{...}}
```

### JSON

```json
{ "documents": [ { "id": "...", "content": "...", "metadata": {} } ] }
```

### CSV columns

```text
id, document_id, content, title, section, source, chunk_index,
content_type, semantic_role, keywords
```

### Markdown

A human-readable inspection report with metadata blocks per chunk.

### Metadata fields

| Field | Description |
|---|---|
| `document_id`, `title`, `source` | provenance |
| `section`, `parent_section`, `heading_path` | structural position |
| `content_type` | `text` `code` `table` `list` `quote` `heading` `mixed` `metadata` |
| `semantic_role` | `knowledge` `definition` `procedure` `example` `rule` `reference` `code` `document_meta` `navigation` |
| `language` | for code chunks |
| `chunk_index`, `total_chunks` | position within the document |
| `strategy`, `unit`, `size` | how it was produced |
| `char_count`, `word_count`, `token_count`, `sentence_count` | measurements |
| `start_offset`, `end_offset` | byte offsets in the cleaned document |
| `overlap_prefix_chars` | characters carried over from the previous chunk |
| `parent_id` | section (or document) parent |
| `previous_chunk`, `next_chunk` | neighbour ids for context expansion |
| `duplicate_of`, `similarity` | deduplication result |

### Retrieval metadata

A separate `retrieval` object holds the search-support terms harvested from
keyword/tag/alias sections. They are **not** concatenated into `content`:

```json
"retrieval": {
  "tags": ["..."],
  "keywords": ["..."],
  "aliases": ["..."],
  "entities": ["..."],
  "related_concepts": ["..."],
  "questions": ["How does object picking affect subsequent actions?"]
}
```

Use them for metadata filtering, hybrid search, or query expansion — all of
which work better than dumping them into the embedded text.

### Quality

`quality` carries `quality_score` plus five sub-scores and any flags:

| Sub-score | Weight | Measures |
|---|---|---|
| `retrieval_score` | 0.30 | Would this chunk answer a question? |
| `information_score` | 0.25 | Signal density, prose vs term inventory |
| `coherence_score` | 0.20 | Complete sentences, intact code/tables/lists |
| `context_score` | 0.15 | Heading path, title, self-description |
| `length_score` | 0.10 | Proximity to the target size |

Length is deliberately the *smallest* weight. When it was worth 0.30, a
500-token dump of search aliases scored 0.96 — second-highest in the whole
dataset — while a real 150-token explanation scored 0.76.

```text
TOO_SHORT  TOO_LONG  OVERSIZED  UNDERSIZED  LOW_CONTEXT
DUPLICATE  NEAR_DUPLICATE  BROKEN_SENTENCE  MIXED_TOPICS  LOW_INFORMATION
HEADING_ONLY  METADATA_ONLY  KEYWORD_HEAVY  ALIAS_HEAVY  ORPHANED_CONTEXT
CODE_SPLIT  FRAGMENTED_LIST  FRAGMENTED_TABLE
```

### Information-loss audit

`statistics.coverage` accounts for every source block:

```json
"coverage": {
  "source_words": 13748,
  "blocks_by_destination": { "knowledge": 842, "retrieval_terms": 2 },
  "words_by_destination":  { "knowledge": 13741, "retrieval_terms": 7 },
  "dropped_blocks": 0,
  "duplicated_chars": 0,
  "retention": 1.0
}
```

`dropped_blocks` must be zero. Anything else means text went missing, and
`ragforge validate` prints exactly which blocks.

---

## Python API

```python
from ragforge import ForgeConfig, Pipeline, chunk_text

# One-liner
chunks = chunk_text("# Title\n\nSome content...")

# Full pipeline
config = ForgeConfig()
config.chunking.target_size = 400
config.chunking.overlap = 60
config.output.format = "jsonl"

result = Pipeline(config).run("./docs/", write=True)

print(result.statistics.total_chunks, result.statistics.average_size)
for chunk in result.chunks[:3]:
    print(chunk.id, chunk.metadata.heading_path, chunk.quality.quality_score)
```

Extending it:

```python
from ragforge.parsers import Parser, register_parser
from ragforge.chunking import Chunker, register_strategy
from ragforge.embeddings import EmbeddingProvider, register_provider

class EpubParser(Parser):
    name = "epub"
    extensions = (".epub",)
    def parse_text(self, text, *, source="", title=""):
        return self.build_document(text, source=source, title=title)

register_parser(EpubParser())
```

---

## REST API

```bash
pip install "rag-chunkforge[api]"
ragforge serve --port 8000
```

| Method | Path | Description |
|---|---|---|
| `POST` | `/process` | Upload a file (or JSON text) + config → job |
| `GET` | `/jobs` | List jobs |
| `GET` | `/jobs/{id}` | Job status and summary |
| `GET` | `/jobs/{id}/chunks` | Paginated chunks (`?search=&limit=&offset=`) |
| `GET` | `/jobs/{id}/statistics` | Statistics payload |
| `GET` | `/jobs/{id}/export?format=jsonl` | Download the dataset |
| `GET` | `/jobs/{id}/preview` | Original text with chunk boundary spans |
| `DELETE` | `/jobs/{id}` | Delete a job |
| `GET` | `/health`, `/formats` | Service metadata |

```bash
curl -F "file=@docs/manual.md" -F "strategy=recursive" -F "target_size=500" \
     http://localhost:8000/process
```

```json
{ "job_id": "abc123", "status": "completed", "chunks": 124 }
```

Interactive docs at `/docs`.

---

## Web interface

`ragforge serve` also hosts a dependency-free (no npm build) developer UI at `/`:

1. upload a document or paste text,
2. pick strategy, size, overlap, unit,
3. process and browse the resulting chunks,
4. full-text search across chunks,
5. inspect metadata, quality scores and flags,
6. see chunk boundaries highlighted over the original document,
7. view size distribution and breakdowns by document / section / content type,
8. export JSONL, JSON, CSV or Markdown.

Clean and developer-focused - a dataset inspector, not a dashboard.

---

## Architecture

```text
ragforge/
├── cli/              Typer CLI + Rich rendering
├── parsers/          txt, markdown, html, json, csv, pdf (+ registry)
├── preprocessing/    cleaner.py, structure.py
├── semantics/        roles.py, classifier.py  (knowledge vs retrieval metadata)
├── chunking/
│   ├── base.py       Chunker interface, SizeMeter
│   ├── semantic.py   role-aware concept chunking (default)
│   ├── structural.py section packing (shared core)
│   ├── recursive.py  separator hierarchy
│   ├── sentence.py   sentence-boundary chunking
│   ├── code.py       code-aware splitting
│   ├── overlap.py    boundary-aware overlap
│   └── engine.py     strategy selection + materialisation
├── context/          heading paths, parents, neighbours, prefixes
├── deduplication/    MinHash + LSH, exact hashing
├── quality/          scorer.py, validator.py, coverage.py
├── embeddings/       provider abstraction + built-ins
├── exporters/        jsonl, json, csv, markdown, statistics
├── models/           Pydantic models (Document, Chunk, Config, Result)
├── utils/            ids, tokenizer, text, progress
├── api/              FastAPI app, schemas, job store, static UI
└── pipeline.py       orchestration
```

**Performance.** Documents are streamed one at a time and released after
chunking, so peak memory tracks the largest single document. Deduplication uses
banded LSH instead of pairwise comparison, keeping it near-linear. Progress is
reported through an abstraction so libraries stay silent and the CLI shows a
Rich progress bar.

---

## Development

```bash
git clone https://github.com/your-org/rag-chunkforge.git
cd rag-chunkforge
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

ruff check ragforge tests
ruff format --check ragforge tests
mypy ragforge
pytest
```

## Testing

```bash
pytest                              # full suite
pytest --cov=ragforge --cov-report=term-missing
pytest tests/test_chunking.py -v
```

The suite covers empty/tiny/huge documents, Unicode, Markdown, code blocks,
tables, lists, nested headings, repeated content, malformed input, overlap
behaviour, exact size limits, metadata preservation, every exporter, directory
processing, the CLI and the REST API. Every fixed bug gets a regression test.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and our
[Code of Conduct](CODE_OF_CONDUCT.md). Issues and PRs welcome - especially new
parsers, chunking strategies and embedding providers.

## Roadmap

- [ ] Semantic chunking with embedding-based boundary detection (optional)
- [ ] Incremental/streaming re-chunking for changed documents only
- [ ] More parsers: DOCX, EPUB, Jupyter notebooks, Confluence exports
- [ ] Direct vector-store writers (Qdrant, Chroma, pgvector)
- [ ] Retrieval-quality benchmark harness
- [ ] Multilingual sentence segmentation improvements

## License

MIT - see [LICENSE](LICENSE).
