# Examples

A small multi-format corpus you can run the tool against immediately.

```text
examples/
├── input/
│   ├── object-picking.md     Markdown: frontmatter, nested headings, code, table, list, quote
│   ├── retrieval-notes.txt   Plain prose with no structure at all
│   ├── api-reference.html    HTML with nav/footer/script boilerplate to strip
│   ├── faq.json              JSON array of records
│   └── glossary.csv          CSV rendered as one section per row
├── ragforge.yaml             Configuration used below
└── output/                   Generated (git-ignored)
```

## Run it

```bash
ragforge process examples/input -c examples/ragforge.yaml
ragforge stats   examples/output/chunks.jsonl
ragforge inspect examples/output/chunks.jsonl --limit 20
ragforge validate examples/output/chunks.jsonl
```

Or browse the results interactively:

```bash
ragforge serve
```

## Bad chunks vs good chunks

The same source, `examples/input/object-picking.md`, chunked two ways.

### Bad: fixed-size character splitter

```text
--- chunk 3 ---
ns of their parent event. This is what
makes nested events useful: you narrow the selection once, then refine it.

### Resetting the selection

The picked list is reset at the start of every top-level event.

## Example

If the player overlaps an enemy, the enemy can be sel
```

What is wrong:

- starts mid-word (`ns of their parent event`),
- ends mid-word (`can be sel`),
- merges three unrelated sections into one vector,
- carries no metadata, so a retriever cannot tell which document or section it
  came from.

### Good: RAG ChunkForge

Run `ragforge inspect examples/output/chunks.jsonl --chunk 0` to see this:

```json
{
  "id": "doc_e0a9ee4828_chunk_0000",
  "content": "# Object Picking\n\nObject picking determines which instances of an object are selected by conditions. ...\n\n## How it works\n\nWhen a condition is evaluated, GDevelop maintains a list of picked instances. ...\n\n### Example\n\n...\n\n```javascript\n// Approximation of the internal picking logic.\nfunction pickColliding(instances, player) {\n  return instances.filter((instance) => instance.collidesWith(player));\n}\n```",
  "metadata": {
    "title": "GDevelop Documentation",
    "section": "Object picking in sub-events",
    "parent_section": "How it works",
    "heading_path": ["Object Picking", "How it works", "Object picking in sub-events"],
    "content_type": "code",
    "semantic_role": "code",
    "language": "javascript",
    "next_chunk": "doc_e0a9ee4828_chunk_0001",
    "parent_id": "doc_e0a9ee4828_section_7d1cbf53"
  },
  "context_prefix": "Document: GDevelop Documentation\nSection: Object Picking > How it works",
  "quality": { "quality_score": 0.97, "retrieval_score": 1.0, "flags": [] }
}
```

Why it retrieves better:

- one complete concept, whole sentences at both ends,
- the code block is intact and correctly fenced, tagged with its language,
- headings are inside the text, so the chunk explains itself,
- `semantic_role` lets a retriever filter to knowledge only,
- neighbour and parent ids let a retriever expand context on demand.

### Keyword sections become metadata, not chunks

`faq.json` and `glossary.csv` contain short labelled entries. Instead of
producing one useless chunk per term, RAG ChunkForge merges the entries into
usable chunks and records the labels as searchable metadata:

```bash
ragforge inspect examples/output/chunks.jsonl --chunk 0   # see retrieval.* fields
ragforge stats   examples/output/chunks.jsonl             # see the coverage audit
```

The audit confirms nothing was lost:

```text
Information-loss audit
  Destination     Blocks   Words
  knowledge          ...     ...
Retention 100.00% (0 unaccounted blocks)
```

## What each input demonstrates

| File | Demonstrates |
|---|---|
| `object-picking.md` | Heading hierarchy in metadata, code kept intact, table kept intact, small sibling sections merged |
| `retrieval-notes.txt` | Sentence-aware chunking of unstructured prose |
| `api-reference.html` | `nav`/`footer`/`script` removal, HTML tables and `<pre><code>` converted to Markdown |
| `faq.json` | Records become sections; each Q&A stays whole |
| `glossary.csv` | Short rows merged into usefully sized chunks instead of one chunk per term |

## Try different strategies

```bash
ragforge stats examples/input/object-picking.md -s semantic     # default
ragforge stats examples/input/object-picking.md -s structural
ragforge stats examples/input/object-picking.md -s sentence
ragforge stats examples/input/object-picking.md -s code
ragforge stats examples/input/retrieval-notes.txt -s auto --chunk-size 200
```

Compare the `Chunks by semantic role` and `Retrieval terms harvested` tables
between `semantic` and the others to see the classification at work.
