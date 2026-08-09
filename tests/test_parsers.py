"""Parser tests across every supported format."""

from __future__ import annotations

from pathlib import Path

import pytest

from ragforge.errors import ParseError, UnsupportedFormatError
from ragforge.parsers import (
    CsvParser,
    HtmlParser,
    JsonParser,
    MarkdownParser,
    TextParser,
    get_parser,
    supported_extensions,
)
from ragforge.parsers.base import default_title, read_text_file


# ---------------------------------------------------------------- registry
def test_registry_contains_expected_formats():
    extensions = supported_extensions()
    for expected in (".txt", ".md", ".html", ".json", ".csv", ".pdf"):
        assert expected in extensions


def test_get_parser_by_extension(tmp_path):
    assert isinstance(get_parser(tmp_path / "a.md"), MarkdownParser)
    assert isinstance(get_parser(tmp_path / "a.txt"), TextParser)
    assert isinstance(get_parser(tmp_path / "a.html"), HtmlParser)
    assert isinstance(get_parser(tmp_path / "a.csv"), CsvParser)
    assert isinstance(get_parser(tmp_path / "a.json"), JsonParser)


def test_unsupported_format(tmp_path):
    with pytest.raises(UnsupportedFormatError) as exc:
        get_parser(tmp_path / "a.xyz")
    assert "Unsupported file format" in str(exc.value)
    assert exc.value.hint


def test_default_title():
    assert default_title(Path("my_great-doc.md")) == "My Great Doc"


# ---------------------------------------------------------------- text
def test_text_parser(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("First line\n\nSecond paragraph.", encoding="utf-8")
    doc = TextParser().parse(path)
    assert doc.title == "Notes"
    assert "Second paragraph." in doc.content
    assert doc.metadata["format"] == "text"


def test_text_parser_normalizes_crlf():
    doc = TextParser().parse_text("a\r\nb\rc")
    assert doc.content == "a\nb\nc"


def test_read_text_file_handles_bom(tmp_path):
    path = tmp_path / "bom.txt"
    path.write_bytes("\ufeffhello".encode())
    assert read_text_file(path) == "hello"


def test_read_binary_file_raises(tmp_path):
    path = tmp_path / "bin.txt"
    path.write_bytes(b"\x00\x01\x02binary")
    with pytest.raises(ParseError):
        read_text_file(path)


def test_read_missing_file(tmp_path):
    with pytest.raises(ParseError):
        read_text_file(tmp_path / "missing.txt")


# ---------------------------------------------------------------- markdown
def test_markdown_frontmatter():
    doc = MarkdownParser().parse_text("---\ntitle: My Doc\ntags: [a, b]\n---\n\n# Heading\n\nBody.")
    assert doc.title == "My Doc"
    assert doc.metadata["frontmatter"]["tags"] == ["a", "b"]
    assert doc.content.lstrip().startswith("# Heading")


def test_markdown_setext_headings_normalized():
    doc = MarkdownParser().parse_text("Title\n=====\n\nBody\n\nSection\n-------\n\nMore")
    assert "# Title" in doc.content
    assert "## Section" in doc.content


def test_markdown_title_from_first_heading():
    doc = MarkdownParser().parse_text("Intro text\n\n# Real Title\n\nBody")
    assert doc.title == "Real Title"


def test_markdown_ignores_headings_in_code_fence():
    doc = MarkdownParser().parse_text("```\n# not a heading\n```\n\n# Real\n")
    assert doc.title == "Real"


# ---------------------------------------------------------------- html
def test_html_parser_converts_structure():
    html = """
    <html><head><title>Doc</title>
    <meta name="description" content="desc" /></head>
    <body>
      <nav>Home | About</nav>
      <h1>Title</h1>
      <p>Hello <strong>world</strong>.</p>
      <h2>Code</h2>
      <pre><code class="language-python">print(1)</code></pre>
      <ul><li>one</li><li>two</li></ul>
      <table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>
      <script>evil()</script>
      <footer>Copyright</footer>
    </body></html>
    """
    doc = HtmlParser().parse_text(html)
    assert doc.title == "Doc"
    assert doc.metadata["description"] == "desc"
    assert "# Title" in doc.content
    assert "## Code" in doc.content
    assert "**world**" in doc.content
    assert "- one" in doc.content
    assert "| A | B |" in doc.content
    assert "evil()" not in doc.content
    assert "Home | About" not in doc.content
    assert "Copyright" not in doc.content


def test_html_entities_are_unescaped():
    doc = HtmlParser().parse_text("<p>a &amp; b &lt; c</p>")
    assert "a & b < c" in doc.content


def test_html_without_body_tags():
    doc = HtmlParser().parse_text("<h1>Bare</h1><p>Text</p>")
    assert "# Bare" in doc.content


# ---------------------------------------------------------------- json
def test_json_object_parsing():
    doc = JsonParser().parse_text('{"title": "Cfg", "server": {"host": "x", "port": 1}}')
    assert doc.title == "Cfg"
    assert "host: x" in doc.content
    assert "## server" in doc.content


def test_json_array_becomes_sections():
    doc = JsonParser().parse_text('[{"title": "A", "body": "one"}, {"title": "B", "body": "two"}]')
    assert "## A" in doc.content
    assert "## B" in doc.content
    assert doc.metadata["records"] == 2


def test_jsonl_parsing():
    doc = JsonParser().parse_text('{"title": "A"}\n{"title": "B"}\n')
    assert doc.metadata["format"] == "jsonl"
    assert "## A" in doc.content


def test_malformed_json_raises():
    with pytest.raises(ParseError) as exc:
        JsonParser().parse_text("{not json at all", source="bad.json")
    assert "bad.json" in str(exc.value)


def test_empty_json():
    doc = JsonParser().parse_text("   ")
    assert doc.content == ""


# ---------------------------------------------------------------- csv
def test_csv_records_mode():
    doc = CsvParser().parse_text("name,role\nAda,engineer\nGrace,admiral\n")
    assert "## Ada" in doc.content
    assert "- role: engineer" in doc.content
    assert doc.metadata["rows"] == 2


def test_csv_table_mode():
    doc = CsvParser(mode="table").parse_text("a,b\n1,2\n3,4\n")
    assert "| a | b |" in doc.content
    assert "| 1 | 2 |" in doc.content


def test_tsv_detection():
    doc = CsvParser().parse_text("name\trole\nAda\tengineer\nGrace\tadmiral\n")
    assert "Ada" in doc.content


def test_empty_csv():
    doc = CsvParser().parse_text("")
    assert doc.content == ""
    assert doc.metadata["rows"] == 0


# ---------------------------------------------------------------- pdf
def test_pdf_roundtrip(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    path = tmp_path / "blank.pdf"
    with path.open("wb") as handle:
        writer.write(handle)
    from ragforge.parsers import PdfParser

    with pytest.raises(ParseError) as exc:
        PdfParser().parse(path)
    assert "no extractable text" in str(exc.value)


def test_pdf_corrupted(tmp_path):
    pytest.importorskip("pypdf")
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.4 totally broken")
    from ragforge.parsers import PdfParser

    with pytest.raises(ParseError):
        PdfParser().parse(path)


def test_pdf_text_postprocessing():
    from ragforge.parsers import PdfParser

    doc = PdfParser().parse_text("Intro Section\nThis line is hyph-\nenated across lines.")
    assert "hyphenated" in doc.content


# ---------------------------------------------------------------- custom
def test_custom_parser_registration(tmp_path):
    from ragforge.parsers import Parser, register_parser

    class DummyParser(Parser):
        name = "dummy"
        extensions = (".dummy",)

        def parse_text(self, text, *, source="", title=""):
            return self.build_document(text.upper(), source=source, title=title or "Dummy")

    register_parser(DummyParser())
    assert ".dummy" in supported_extensions()
    path = tmp_path / "a.dummy"
    path.write_text("hi", encoding="utf-8")
    assert get_parser(path).parse(path).content == "HI"
