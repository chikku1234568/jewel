"""Document routes (mounted). Every route requires a session; the owner is always the
session user, never a client-supplied field.

* ``POST /documents``: multipart upload of one ``.pdf``, ``.docx``, ``.pptx``, ``.xlsx``,
  ``.html``, ``.htm``, ``.txt`` or ``.md`` file. Disallowed types (415), files over 20 MB
  (413), PDFs over 20 pages, and bytes that do not match the extension (422) are rejected
  before anything is stored. Otherwise the file is stored, converted to Markdown text,
  and the row is returned with status
  ``parsed`` or ``failed`` (with ``error``).
* ``GET /documents``: the caller's library (id, filename, uploaded_at, status, error,
  build progress, and ``triples_kept`` from the last finished build).
* ``GET /documents/{id}``: the row with extracted text for the owner; 404 otherwise.
* ``DELETE /documents``: delete every file, chunk row, and graph node for this account.
* ``DELETE /documents/{id}``: delete the row, its stored chunks and the file for the owner,
  and the document's part of the graph when Neo4j is up; 404 otherwise.
* ``POST /documents/{id}/build``: store this file's chunks, extract triples from them in
  the background, and write this file only into the user's graph.
* ``POST /documents/{id}/stop``: stop a running build.
"""

import threading
import uuid

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile
from neo4j import GraphDatabase

from jewel.api.limits import BUILD, UPLOAD, enforce
from jewel.auth.dependencies import CurrentUser
from jewel.db.postgres import AppSettings, DbConn, connect
from jewel.documents import build_queue, repository, service
from jewel.documents.build_queue import PendingBuild
from jewel.documents.models import MAX_UPLOAD_BYTES, DocumentDetail, DocumentSummary
from jewel.documents.storage import FileStore
from jewel.ingestion.extraction_cache import PostgresExtractionCache
from jewel.ingestion.live import BuildCancelled, build_parsed_text
from jewel.kg.neo4j_store import Neo4jGraphStore
from jewel.llm.choices import (
    EmbeddingChoice,
    ExtractionChoice,
    make_chat,
    make_embedder,
)

router = APIRouter(prefix="/documents", tags=["documents"])
_CANCELS: dict[str, tuple[threading.Event, object]] = {}
_CANCELS_LOCK = threading.Lock()

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
    enforce(request, user["id"], UPLOAD)
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


class BuildBody(EmbeddingChoice):
    """Embedding fields stay at the top level. Extraction is the model that reads the file."""

    extraction: ExtractionChoice = ExtractionChoice()


@router.post("/{document_id}/build")
def build(
    document_id: str,
    request: Request,
    user: CurrentUser,
    conn: DbConn,
    settings: AppSettings,
    body: BuildBody | None = None,
) -> DocumentSummary:
    """Turn this document's text into graph nodes. Does not reprocess other files."""
    parsed_id = _parse_id(document_id)
    row = repository.get_document(conn, user["id"], parsed_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    text = row["extracted_text"] or ""
    if not text.strip():
        raise HTTPException(status_code=409, detail="This file has no extracted text to build from")
    driver = getattr(request.app.state, "neo4j", None)
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j is not available")
    if row["status"] in ("extracting", "waiting"):
        raise HTTPException(status_code=409, detail="This file is already being built")
    enforce(request, user["id"], BUILD)
    embedder = make_embedder(body or EmbeddingChoice())
    chat = make_chat(body.extraction if body else ExtractionChoice())
    cancel = threading.Event()
    with _CANCELS_LOCK:
        _CANCELS[str(parsed_id)] = (cancel, chat)
    build_queue.submit(
        conn,
        PendingBuild(
            document_id=parsed_id,
            cancel=cancel,
            kwargs={
                "database_url": settings.database_url,
                "neo4j_uri": settings.neo4j_uri,
                "neo4j_user": settings.neo4j_user,
                "neo4j_password": settings.neo4j_password,
                "document_id": parsed_id,
                "user_id": str(user["id"]),
                "filename": row["filename"],
                "text": text,
                "document_date": row["document_date"],
                "embedder": embedder,
                "chat": chat,
                "cancel": cancel,
            },
        ),
    )
    updated = repository.get_document(conn, user["id"], parsed_id)
    assert updated is not None
    return DocumentSummary.model_validate(updated)


def _report_progress(database_url: str, document_id, done: int, total: int) -> None:
    with connect(database_url) as conn:
        repository.set_build_progress(conn, document_id, done, total)


def _build_in_background(**kwargs) -> None:
    """Run extraction off the request so a long paper does not hit the HTTP timeout."""
    document_id = kwargs["document_id"]
    if kwargs["cancel"].is_set():
        with connect(kwargs["database_url"]) as conn:
            repository.mark_build_failed(conn, document_id, "stopped")
        with _CANCELS_LOCK:
            _CANCELS.pop(str(document_id), None)
        build_queue.promote_later(kwargs["database_url"])
        return
    driver = GraphDatabase.driver(
        kwargs["neo4j_uri"], auth=(kwargs["neo4j_user"], kwargs["neo4j_password"])
    )
    try:
        with connect(kwargs["database_url"]) as conn:
            try:
                kept = build_parsed_text(
                    document_id=str(document_id),
                    user_id=kwargs["user_id"],
                    filename=kwargs["filename"],
                    text=kwargs["text"],
                    document_date=kwargs["document_date"],
                    chat=kwargs["chat"],
                    embedder=kwargs["embedder"],
                    store=Neo4jGraphStore(driver),
                    cache=PostgresExtractionCache(conn),
                    on_progress=lambda done, total: _report_progress(
                        kwargs["database_url"], document_id, done, total
                    ),
                    cancel=kwargs["cancel"],
                    save_chunks=lambda texts: repository.replace_chunks(
                        conn, kwargs["user_id"], document_id, texts
                    ),
                )
                if not kwargs["cancel"].is_set():
                    repository.mark_ready(conn, document_id, kept)
            except BuildCancelled:
                repository.mark_build_failed(conn, document_id, "stopped")
            except Exception as exc:
                repository.mark_build_failed(conn, document_id, str(exc)[:500])
    finally:
        with _CANCELS_LOCK:
            _CANCELS.pop(str(document_id), None)
        driver.close()
        build_queue.promote_later(kwargs["database_url"])


build_queue.set_runner(_build_in_background)


@router.post("/{document_id}/stop")
def stop_build(
    document_id: str, user: CurrentUser, conn: DbConn, settings: AppSettings
) -> DocumentSummary:
    """Stop a build. Passages already sent to the model may still finish."""
    parsed_id = _parse_id(document_id)
    row = repository.get_document(conn, user["id"], parsed_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    with _CANCELS_LOCK:
        running = _CANCELS.get(str(parsed_id))
    if running is not None:
        cancel, chat = running
        cancel.set()
        abort = getattr(chat, "abort", None)
        if abort is not None:
            abort()
    if row["status"] in ("extracting", "waiting"):
        repository.mark_build_failed(conn, parsed_id, "stopped")
        build_queue.discard(str(parsed_id))
        build_queue.promote_later(settings.database_url)
    updated = repository.get_document(conn, user["id"], parsed_id)
    assert updated is not None
    return DocumentSummary.model_validate(updated)


@router.get("/{document_id}")
def get_one(document_id: str, user: CurrentUser, conn: DbConn) -> DocumentDetail:
    row = repository.get_document(conn, user["id"], _parse_id(document_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentDetail.model_validate(row)


def _stop_builds(document_ids: list[str]) -> None:
    """Ask any of these builds to stop. A call already on the wire can still finish."""
    for document_id in document_ids:
        build_queue.discard(document_id)
    with _CANCELS_LOCK:
        running = [_CANCELS.get(document_id) for document_id in document_ids]
    for entry in running:
        if entry is None:
            continue
        cancel, chat = entry
        cancel.set()
        abort = getattr(chat, "abort", None)
        if abort is not None:
            abort()


@router.delete("", status_code=204)
def delete_library(
    request: Request, user: CurrentUser, conn: DbConn, settings: AppSettings
) -> Response:
    """Delete this account's files and knowledge graph. Other accounts are untouched."""
    rows = repository.list_documents(conn, user["id"])
    _stop_builds([str(row["id"]) for row in rows])
    for stored_path in repository.delete_user_documents(conn, user["id"]):
        FileStore(settings.upload_dir).delete(stored_path)
    driver = getattr(request.app.state, "neo4j", None)
    if driver is not None:
        Neo4jGraphStore(driver).delete_user(str(user["id"]))
    return Response(status_code=204)


@router.delete("/{document_id}", status_code=204)
def delete(
    document_id: str, request: Request, user: CurrentUser, conn: DbConn, settings: AppSettings
) -> Response:
    _stop_builds([document_id])
    stored_path = repository.delete_document(conn, user["id"], _parse_id(document_id))
    if stored_path is None:
        raise HTTPException(status_code=404, detail="Document not found")
    FileStore(settings.upload_dir).delete(stored_path)
    driver = getattr(request.app.state, "neo4j", None)
    if driver is not None:
        Neo4jGraphStore(driver).delete_document(str(user["id"]), document_id)
    return Response(status_code=204)
