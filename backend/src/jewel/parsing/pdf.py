"""PDF checks with pypdf: page count for the upload cap, and readability.

Text extraction itself is done by MarkItDown (``jewel.parsing.markdown``). pypdf stays
because the 50-page cap must be checked before anything is stored or converted.
"""

import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from jewel.parsing.base import ParseError


def _reader(data: bytes) -> PdfReader:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ParseError("PDF is password-protected")
        return reader
    except ParseError:
        raise
    except (PdfReadError, ValueError, OSError) as exc:
        raise ParseError("Could not read this PDF") from exc


def pdf_page_count(data: bytes) -> int:
    """Number of pages; raises ``ParseError`` if the PDF cannot be read."""
    try:
        return len(_reader(data).pages)
    except ParseError:
        raise
    except Exception as exc:  # pypdf raises assorted errors on malformed files
        raise ParseError("Could not read this PDF") from exc


def check_pdf_readable(data: bytes) -> None:
    """Raise ``ParseError`` for a PDF pypdf cannot open or that needs a password."""
    pdf_page_count(data)
