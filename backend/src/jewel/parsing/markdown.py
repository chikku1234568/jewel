"""Office, PDF and HTML uploads to Markdown with MarkItDown.

Each accepted extension maps to exactly one MarkItDown converter, called directly. We do
not use ``MarkItDown().convert()``: that runs a file-type guesser (magika) and then tries
every built-in converter in turn, including zip, image, audio and YouTube handlers this
project does not accept. Calling the one converter keeps the outcome predictable: a
``.pdf`` is read as a PDF or it fails, and nothing falls back to another format.

The Markdown string returned here is what Postgres stores as ``extracted_text`` and what
the quote check compares against later.
"""

import io

from markitdown import StreamInfo
from markitdown.converters import (
    DocxConverter,
    HtmlConverter,
    PdfConverter,
    PptxConverter,
    XlsxConverter,
)

from jewel.parsing.base import ParseError
from jewel.parsing.pdf import check_pdf_readable

# Extension -> (converter, user-facing name used in error messages).
_CONVERTERS = {
    ".pdf": (PdfConverter(), "PDF"),
    ".docx": (DocxConverter(), ".docx file"),
    ".pptx": (PptxConverter(), ".pptx file"),
    ".xlsx": (XlsxConverter(), ".xlsx file"),
    ".html": (HtmlConverter(), "HTML file"),
    ".htm": (HtmlConverter(), "HTML file"),
}

MARKITDOWN_EXTENSIONS = tuple(_CONVERTERS)


class MarkItDownParser:
    """Convert one file type to Markdown. No OCR: a scanned PDF yields empty text."""

    def __init__(self, extension: str) -> None:
        self.extension = extension
        self._converter, self._label = _CONVERTERS[extension]

    def extract_text(self, data: bytes, filename: str) -> str:
        if self.extension == ".pdf":
            # pypdf gives a clear "password-protected" message; pdfminer would not.
            check_pdf_readable(data)
        try:
            result = self._converter.convert(
                io.BytesIO(data), StreamInfo(extension=self.extension, filename=filename)
            )
        except Exception as exc:  # each converter raises its own library's errors
            raise ParseError(f"Could not read this {self._label}") from exc
        return result.markdown or ""
