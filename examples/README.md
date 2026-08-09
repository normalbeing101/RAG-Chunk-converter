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

```json
{
  "id": "doc_e0a9ee4828_chunk_0002",
  "content": "## Example\n\nIf the player overlaps an enemy, the enemy can be selected and an action can modify its health. Only the overlapping instance is affected.\n\n```javascript\n// Approximation of the internal picking logic.\nfunction pickColliding(instances, player) {\n  return instances.filter((instance) => instance.collidesWith(player));\n}\n```",
  "metadata": {
    "title": "GDevelop Documentation",
    "section": "Example",
    "parent_section": "Object Picking",
    "heading_path": ["Object Picking", "Example"],
    "content_type": "code",
    "language": "javascript",
    "previous_chunk": "doc_e0a9ee4828_chunk_0001",
    "next_chunk": "doc_e0a9ee4828_chunk_0003",
    "parent_id": "doc_e0a9ee4828_section_c53fd819"
  },
  "context_prefix": "Document: GDevelop Documentation\nSection: Object Picking > Example",
  "quality": { "quality_score": 0.84, "flags": [] }
}
```

Why it retrieves better:

- one complete concept, whole sentences at both ends,
- the code block is intact and correctly fenced, tagged with its language,
- the heading is inside the text, so the chunk explains itself,
- neighbour and parent ids let a retriever expand context on demand.

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
ragforge stats examples/input/object-picking.md -s structural
ragforge stats examples/input/object-picking.md -s sentence
ragforge stats examples/input/object-picking.md -s code
ragforge stats examples/input/retrieval-notes.txt -s auto --chunk-size 200
```
