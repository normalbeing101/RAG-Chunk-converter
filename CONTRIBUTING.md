# Contributing to RAG ChunkForge

Thanks for taking the time to contribute. This project aims to be a genuinely
useful tool for building production RAG datasets, and that only works with
real-world feedback.

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- **Report bugs** - especially chunking output that looks wrong for a real
  document. Attach a minimal input file if you can.
- **Add a parser** - DOCX, EPUB, notebooks, wiki exports, ...
- **Add a chunking strategy** - semantic, layout-aware, domain-specific.
- **Add an embedding provider.**
- **Improve documentation** - examples of bad vs good chunks are very welcome.

## Development setup

```bash
git clone https://github.com/your-org/rag-chunkforge.git
cd rag-chunkforge

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

## Before you open a pull request

```bash
ruff check ragforge tests          # lint
ruff format ragforge tests         # format
mypy ragforge                      # type check (advisory)
pytest                             # full test suite
pytest --cov=ragforge              # with coverage
```

CI runs the same three workflows (`lint`, `test`, `build`) on Linux, macOS and
Windows for Python 3.11-3.13.

## Code standards

- **Python 3.11+**, type hints everywhere.
- **Pydantic** models for anything structured or user-configurable.
- **No new required dependencies.** New integrations go behind an optional
  extra and must fail with a clear `MissingDependencyError`.
- **Never raise raw exceptions to users.** Use the `RagForgeError` hierarchy
  in `ragforge/errors.py` with an actionable message and, where useful, a hint.
- **Line length 100**, double quotes, `ruff format` output.
- Docstrings explain *why*, not *what*. Avoid inline comments that restate code.

## Adding a parser

1. Subclass `ragforge.parsers.base.Parser`.
2. Set `name` and `extensions`.
3. Implement `parse_text` (and override `parse` for binary formats).
4. Normalise output into Markdown-flavoured text - the structure analyzer
   understands headings, lists, tables, code fences and quotes.
5. Call `register_parser(YourParser())` at module import.
6. Import the module in `ragforge/parsers/__init__.py`.
7. Add tests covering a happy path, an empty file and a malformed file.

```python
from ragforge.parsers.base import Parser, register_parser

class EpubParser(Parser):
    name = "epub"
    extensions = (".epub",)

    def parse_text(self, text, *, source="", title=""):
        return self.build_document(text, source=source, title=title)

register_parser(EpubParser())
```

## Adding a chunking strategy

1. Subclass `ragforge.chunking.base.Chunker` and implement
   `chunk(document) -> list[ChunkCandidate]`.
2. Register it with `register_strategy("my-strategy", MyChunker)`.
3. Respect `self.config` (target/min/max size, unit, code and table settings).
4. Never emit chunks that mix content from different heading paths.

## Testing expectations

Every change should keep the suite green, and:

- **New feature** → tests for the happy path *and* the edge cases.
- **Bug fix** → a regression test in `tests/test_regressions.py` with a short
  comment explaining the original failure.

Edge cases we care about: empty documents, single-character documents, very
large documents, Unicode and CJK text, unbalanced code fences, malformed input,
and exact size-limit boundaries.

## Commit messages

Short, imperative subject lines. Conventional-commit prefixes are welcome but
not required.

```text
fix(chunking): keep heading in every chunk of a section
feat(parsers): add DOCX support
docs: clarify overlap units
```

## Releasing

Maintainers only:

1. Update `CHANGELOG.md`.
2. Bump `version` in `pyproject.toml` and `__version__` in `ragforge/__init__.py`.
3. Tag `vX.Y.Z` and push - the build workflow publishes the artifacts.

## Questions

Open a discussion or an issue. There are no silly questions about chunking -
it is a subtler problem than it looks.
