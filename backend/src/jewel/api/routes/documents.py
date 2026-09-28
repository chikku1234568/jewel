"""Document routes (mounted). Every route requires a session; the owner is always the
session user, never a client-supplied field.

* ``POST /documents``: multipart upload of one ``.pdf``, ``.txt``, ``.md`` or ``.docx``
  file. Disallowed types (415), files over 20 MB (413) and PDFs over 50 pages (422) are
  rejected before anything is stored. Otherwise the file is stored, parsed, and the row
  is returned with status ``parsed`` or ``failed`` (with ``error``).
* ``GET /documents``: the caller's library (id, filename, uploaded_at, status, error).
* ``GET /documents/{id}``: the row with extracted text for the owner; 404 otherwise.
* ``DELETE /documents/{id}``: delete the row and the file for the owner; 404 otherwise.
  Does not touch Neo4j.

``POST /documents/{id}/build`` belongs to the graph pass and is not implemented here.
"""

import uuid

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile

from jewel.auth.dependencies import CurrentUser
from jewel.db.postgres import AppSettings, DbConn
from jewel.documents import repository, service
from jewel.documents.models import MAX_UPLOAD_BYTES, DocumentDetail, DocumentSummary
from jewel.documents.storage import FileStore

router = APIRouter(prefix="/documents", tags=["documents"])

# Multipart framing adds a little on top of the file itself.
_MULTIPART_OVERHEAD = 1024 * 1024


def _parse_id(document_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc


@router.post("", status_code=201)
def upload(
    request: Request, file: UploadFile, user: CurrentUser, conn: DbConn, settings: AppSettings
) -> DocumentSummary:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES + _MULTIPART_OVERHEAD:
        raise HTTPException(status_code=413, detail=service.TOO_LARGE_ERROR)
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    try:
        document_id = service.upload_document(
            conn, FileStore(settings.upload_dir), user["id"], file.filename, data
        )
    except service.UploadRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    row = repository.get_document(conn, user["id"], document_id)
    assert row is not None
    return DocumentSummary.model_validate(row)


@router.get("")
def list_library(user: CurrentUser, conn: DbConn) -> list[DocumentSummary]:
    return [DocumentSummary.model_validate(r) for r in repository.list_documents(conn, user["id"])]


@router.get("/{document_id}")
def get_one(document_id: str, user: CurrentUser, conn: DbConn) -> DocumentDetail:
    row = repository.get_document(conn, user["id"], _parse_id(document_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentDetail.model_validate(row)


@router.delete("/{document_id}", status_code=204)
def delete(document_id: str, user: CurrentUser, conn: DbConn, settings: AppSettings) -> Response:
    stored_path = repository.delete_document(conn, user["id"], _parse_id(document_id))
    if stored_path is None:
        raise HTTPException(status_code=404, detail="Document not found")
    FileStore(settings.upload_dir).delete(stored_path)
    return Response(status_code=204)
