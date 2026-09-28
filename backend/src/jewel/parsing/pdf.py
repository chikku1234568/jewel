"""PDF parsing with pypdf (text layer only, no OCR)."""

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


class PdfParser:
    def extract_text(self, data: bytes, filename: str) -> str:
        reader = _reader(data)
        try:
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:  # malformed content streams
            raise ParseError("Could not extract text from this PDF") from exc
        return "\n\n".join(pages)
