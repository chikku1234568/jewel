"""Document vocabulary and API shapes. Rows live in Postgres (``jewel.db``).

Status contract (handoff to the graph pass):

* ``stored``: bytes saved, parse not started (transient)
* ``parsing``: text extraction running
* ``parsed``: Markdown text is in Postgres, graph not built; the success status of the upload flow
* ``failed``: bad file, empty text or parse error; row and file remain, ``error`` is set
* ``extracting`` / ``ready``: set later by the graph pass only
"""

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
"""20 MB per file. Over-cap uploads are rejected and not stored."""

MAX_PDF_PAGES = 20

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# The only accepted uploads. Anything else is rejected (415) before it is stored.
MEDIA_TYPES_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".docx": DOCX_MEDIA_TYPE,
    ".pptx": PPTX_MEDIA_TYPE,
    ".xlsx": XLSX_MEDIA_TYPE,
    ".html": "text/html",
    ".htm": "text/html",
    ".txt": "text/plain",
    ".md": "text/markdown",
}

ACCEPTED_MEDIA_TYPES = tuple(MEDIA_TYPES_BY_EXTENSION.values())


class DocumentStatus(StrEnum):
    STORED = "stored"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"
    EXTRACTING = "extracting"
    READY = "ready"


class DocumentSummary(BaseModel):
    """A library row. No extracted text."""

    id: UUID
    filename: str
    uploaded_at: datetime
    status: DocumentStatus
    error: str | None = None
    build_done: int = 0
    build_total: int = 0
    triples_kept: int = 0


class DocumentDetail(DocumentSummary):
    """One document for its owner, including extracted text."""

    media_type: str
    document_date: date | None = None
    extracted_text: str | None = None
