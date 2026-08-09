"""Document parsers.

Importing this package registers all built-in parsers. Third-party parsers can
be added at runtime::

    from ragforge.parsers import Parser, register_parser

    class MyParser(Parser):
        name = "epub"
        extensions = (".epub",)
        def parse_text(self, text, *, source="", title=""): ...

    register_parser(MyParser())
"""

from ragforge.parsers.base import (
    Parser,
    get_parser,
    get_parser_by_name,
    read_text_file,
    register_parser,
    registered_parsers,
    supported_extensions,
)
from ragforge.parsers.csv_parser import CsvParser
from ragforge.parsers.html import HtmlParser
from ragforge.parsers.json_parser import JsonParser
from ragforge.parsers.markdown import MarkdownParser
from ragforge.parsers.pdf import PdfParser
from ragforge.parsers.text import TextParser

__all__ = [
    "CsvParser",
    "HtmlParser",
    "JsonParser",
    "MarkdownParser",
    "Parser",
    "PdfParser",
    "TextParser",
    "get_parser",
    "get_parser_by_name",
    "read_text_file",
    "register_parser",
    "registered_parsers",
    "supported_extensions",
]
