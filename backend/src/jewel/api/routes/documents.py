"""Document routes (stub, NOT mounted yet). Session required.

* ``POST /documents``: multipart upload of PDF, ``.txt`` or ``.md`` (20 MB cap, 50-page
  PDF cap; over-cap uploads fail and are not stored). Stored immediately, key or not.
* ``GET /documents``: the caller's library (filename, upload time, status, error).
* ``GET /documents/{id}``: metadata plus extracted text, only for the owner.
* ``POST /documents/{id}/build``: run or retry the ingestion pipeline (needs a saved key).
* ``DELETE /documents/{id}``: delete the file, its ``MENTIONS``, the ``RELATED_TO`` rows
  whose ``document_id`` is this document, then entities left with no mention.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/documents", tags=["documents"])  # no endpoints yet
