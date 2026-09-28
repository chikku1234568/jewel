"""Document vocabulary. Records themselves live in Postgres (``jewel.db``).

One file is one document: owner, original filename, media type, upload time, optional
document date, extracted text, status, and an error string on failure.
"""

from enum import StrEnum

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
"""20 MB per file. Over-cap uploads fail with a clear error and are not stored."""

MAX_PDF_PAGES = 50

ACCEPTED_MEDIA_TYPES = ("application/pdf", "text/plain", "text/markdown")


class DocumentStatus(StrEnum):
    STORED = "stored"
    WAITING_FOR_KEY = "waiting_for_key"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    READY = "ready"
    FAILED = "failed"
