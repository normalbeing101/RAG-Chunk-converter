"""Shared fixtures."""

from __future__ import annotations

import pytest

from ragforge.models.config import ChunkingConfig, ForgeConfig, SizeUnit

MARKDOWN_DOC = """\
# Object Picking

Object picking determines which instances of an object are selected by conditions.

## How it works

When a condition is evaluated, GDevelop maintains a list of picked instances.
Actions can then operate only on those instances.

### Object picking in sub-events

Sub-events inherit the picked instances of their parent event.

## Example

If the player overlaps an enemy, the enemy can be selected and an action can modify its health.

```python
def pick(objects, condition):
    return [obj for obj in objects if condition(obj)]
```

| Condition | Result |
| --- | --- |
| Overlap | Picks colliding instances |
| Distance | Picks nearby instances |

- First bullet item
- Second bullet item
- Third bullet item

> Picking is reset at the start of each event.
"""

PLAIN_TEXT = (
    "Retrieval augmented generation combines a retriever with a generator. "
    "The retriever selects relevant passages from a corpus. "
    "The generator conditions its output on those passages. "
    "Chunking quality therefore determines answer quality. "
) * 8


@pytest.fixture
def markdown_doc() -> str:
    return MARKDOWN_DOC


@pytest.fixture
def plain_text() -> str:
    return PLAIN_TEXT


@pytest.fixture
def small_chunking() -> ChunkingConfig:
    return ChunkingConfig(
        target_size=60,
        min_size=10,
        max_size=140,
        overlap=10,
        unit=SizeUnit.TOKENS,
    )


@pytest.fixture
def config(small_chunking: ChunkingConfig) -> ForgeConfig:
    cfg = ForgeConfig()
    cfg.chunking = small_chunking
    return cfg


@pytest.fixture
def docs_dir(tmp_path, markdown_doc, plain_text):
    """A small corpus covering several formats."""
    root = tmp_path / "docs"
    root.mkdir()
    (root / "guide.md").write_text(markdown_doc, encoding="utf-8")
    (root / "notes.txt").write_text(plain_text, encoding="utf-8")
    (root / "page.html").write_text(
        "<html><head><title>Page</title></head><body>"
        "<nav>Home | Docs</nav><h1>Hello</h1><p>First paragraph of the page.</p>"
        "<h2>Details</h2><p>Second paragraph with more information.</p>"
        "</body></html>",
        encoding="utf-8",
    )
    (root / "data.csv").write_text(
        "name,role,notes\nAda,engineer,Wrote the first algorithm\nGrace,admiral,Built the compiler\n",
        encoding="utf-8",
    )
    (root / "records.json").write_text(
        '[{"title": "Alpha", "body": "First record body."},'
        ' {"title": "Beta", "body": "Second record body."}]',
        encoding="utf-8",
    )
    nested = root / "nested"
    nested.mkdir()
    (nested / "deep.md").write_text("# Deep\n\nNested document content here.\n", encoding="utf-8")
    return root
