"""The upload flow for ``POST /documents``.

1. Reject a disallowed type, an over-cap file (20 MB, 20 PDF pages), or bytes that do not
   match the extension, before writing anything. A PDF must carry a PDF header. An Office
   file must be a zip package with no unsafe paths and no huge declared expansion. Text
   and HTML must be UTF-8 without null bytes.
2. Write bytes under ``JEWEL_UPLOAD_DIR`` at an opaque path and insert the row (``stored``).
3. Set ``parsing`` and convert to text: Markdown via MarkItDown, or UTF-8 for ``.txt`` and
   ``.md``. The PDF page cap already ran with pypdf in step 1, before any conversion.
4. Empty or whitespace text -> ``failed`` with "No text could be extracted".
5. Otherwise save ``extracted_text`` and set ``parsed``.

Parse failures keep the row and the file. Each upload is handled on its own; nothing here
touches other documents or the graph.
"""

import logging
import uuid
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

import psycopg

from jewel.documents import repository
from jewel.documents.inspect import UnsafeUpload, check_bytes
from jewel.documents.models import (
    MAX_PDF_PAGES,
    MAX_UPLOAD_BYTES,
    MEDIA_TYPES_BY_EXTENSION,
    DocumentStatus,
)
from jewel.documents.storage import FileStore
from jewel.parsing import ParseError, parser_for, pdf_page_count

logger = logging.getLogger(__name__)

NO_TEXT_ERROR = "No text could be extracted"
UNSUPPORTED_TYPE_ERROR = (
    "Unsupported file type. Upload a PDF, .docx, .pptx, .xlsx, .html, .htm, .txt or .md file."
)
TOO_LARGE_ERROR = "File is larger than 20 MB."


class UploadRejected(Exception):
    """The upload was refused before anything was stored."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def clean_filename(raw: str | None) -> str:
    """Keep only the base name of the client-supplied filename (display only)."""
    name = PureWindowsPath(PurePosixPath(raw or "").name).name.strip()
    return name[:255] or "untitled"


def extension_of(filename: str) -> str:
    return PurePosixPath(filename).suffix.lower()


def check_upload(filename: str, data: bytes) -> str:
    """Validate type and caps; return the extension. Raises ``UploadRejected``."""
    extension = extension_of(filename)
    if extension not in MEDIA_TYPES_BY_EXTENSION:
        raise UploadRejected(415, UNSUPPORTED_TYPE_ERROR)
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadRejected(413, TOO_LARGE_ERROR)
    if extension == ".pdf":
        try:
            pages = pdf_page_count(data)
        except ParseError:
            pages = None  # unreadable PDF: stored, then reported as a parse failure
        if pages is not None and pages > MAX_PDF_PAGES:
            raise UploadRejected(422, f"PDF has {pages} pages; the limit is {MAX_PDF_PAGES} pages.")
    try:
        check_bytes(extension, data)
    except UnsafeUpload as exc:
        raise UploadRejected(422, exc.message) from exc
    return extension


def upload_document(
    conn: psycopg.Connection, store: FileStore, user_id: Any, raw_filename: str | None, data: bytes
) -> uuid.UUID:
    """Run the full upload flow and return the new document id."""
    filename = clean_filename(raw_filename)
    extension = check_upload(filename, data)

    stored_path = store.save(data)
    try:
        document_id = repository.insert_document(
            conn, user_id, filename, MEDIA_TYPES_BY_EXTENSION[extension], stored_path
        )
    except Exception:
        store.delete(stored_path)
        raise

    repository.set_status(conn, document_id, DocumentStatus.PARSING)
    try:
        text = parser_for(extension).extract_text(data, filename)
    except ParseError as exc:
        repository.mark_failed(conn, document_id, str(exc))
        return document_id
    except Exception as exc:  # never leave a row stuck in "parsing"
        logger.warning("parse crashed for document %s: %s", document_id, type(exc).__name__)
        repository.mark_failed(conn, document_id, "Could not parse this file")
        return document_id

    text = text.replace("\x00", "")  # Postgres text cannot hold NUL
    if not text.strip():
        repository.mark_failed(conn, document_id, NO_TEXT_ERROR)
    else:
        repository.mark_parsed(conn, document_id, text)
    return document_id
