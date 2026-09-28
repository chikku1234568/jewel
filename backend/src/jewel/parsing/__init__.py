"""Parsing uploads to text: PDF (pypdf), ``.txt`` and ``.md`` (UTF-8), ``.docx`` (python-docx).

No OCR: a PDF without a text layer yields empty text, which the upload flow reports as
"No text could be extracted".
"""

from jewel.parsing.base import DocumentParser, ParseError
from jewel.parsing.docx import DocxParser
from jewel.parsing.pdf import PdfParser, pdf_page_count
from jewel.parsing.text import TextParser

_PARSERS: dict[str, DocumentParser] = {
    ".pdf": PdfParser(),
    ".txt": TextParser(),
    ".md": TextParser(),
    ".docx": DocxParser(),
}


def parser_for(extension: str) -> DocumentParser:
    """Return the parser for a lower-case extension such as ``.pdf``."""
    try:
        return _PARSERS[extension]
    except KeyError as exc:
        raise ParseError(f"Unsupported file type: {extension or 'none'}") from exc


__all__ = ["DocumentParser", "ParseError", "parser_for", "pdf_page_count"]
