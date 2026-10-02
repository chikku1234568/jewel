"""Parsing uploads to text.

* ``.pdf``, ``.docx``, ``.pptx``, ``.xlsx``, ``.html``, ``.htm``: Markdown via MarkItDown.
* ``.txt``, ``.md``: read as UTF-8 text, kept as-is.

No OCR: a PDF without a text layer yields empty text, which the upload flow reports as
"No text could be extracted".
"""

from jewel.parsing.base import DocumentParser, ParseError
from jewel.parsing.markdown import MARKITDOWN_EXTENSIONS, MarkItDownParser
from jewel.parsing.pdf import pdf_page_count
from jewel.parsing.text import TextParser

_PARSERS: dict[str, DocumentParser] = {
    ".txt": TextParser(),
    ".md": TextParser(),
    **{extension: MarkItDownParser(extension) for extension in MARKITDOWN_EXTENSIONS},
}


def parser_for(extension: str) -> DocumentParser:
    """Return the parser for a lower-case extension such as ``.pdf``."""
    try:
        return _PARSERS[extension]
    except KeyError as exc:
        raise ParseError(f"Unsupported file type: {extension or 'none'}") from exc


__all__ = ["DocumentParser", "ParseError", "parser_for", "pdf_page_count"]
