"""Document vocabulary and API shapes. Rows live in Postgres (``jewel.db``).

Status contract (handoff to the graph pass):

* ``stored``: bytes saved, parse not started (transient)
* ``parsing``: text extraction running
* ``parsed``: text is in Postgres, graph not built; the success status of the upload flow
* ``failed``: bad file, empty text or parse error; row and file remain, ``error`` is set
* ``extracting`` / ``ready``: set later by the graph pass only
"""

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
"""20 MB per file. Over-cap uploads are rejected and not stored."""

MAX_PDF_PAGES = 50

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

MEDIA_TYPES_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".docx": DOCX_MEDIA_TYPE,
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


class DocumentDetail(DocumentSummary):
    """One document for its owner, including extracted text."""

    media_type: str
    document_date: date | None = None
    extracted_text: str | None = None
