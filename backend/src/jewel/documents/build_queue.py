"""Which files may extract right now.

A Build click records ``waiting`` and keeps the model client in this process. Up to two
files extract at once, and only one of them belongs to any single account: two files from
the same person share entity names. Each extracting file still runs its own passage
workers, because each person brings their own model key.

The model key is not written to Postgres. After a restart the unfinished rows are marked
failed and the person builds again. Cached passages are skipped.
"""

import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import psycopg

from jewel.db.postgres import connect
from jewel.documents.models import DocumentStatus

logger = logging.getLogger(__name__)

# Two files at once fits the 8 GB VM. A third click stays waiting.
MAX_EXTRACTING = 2
# Serializes the claim so two clicks cannot both pass the count check.
_LOCK_KEY = 7481931
RESTART_ERROR = "jewel restarted before this build finished. Build again."

Runner = Callable[..., None]


@dataclass
class PendingBuild:
    document_id: uuid.UUID
    cancel: threading.Event
    kwargs: dict[str, Any]


_pending: dict[str, PendingBuild] = {}
_pending_lock = threading.Lock()
_runner: Runner | None = None


def set_runner(runner: Runner) -> None:
    """The route module registers the function that actually extracts a file."""
    global _runner
    _runner = runner


def remember(pending: PendingBuild) -> None:
    with _pending_lock:
        _pending[str(pending.document_id)] = pending


def discard(document_id: str) -> None:
    with _pending_lock:
        _pending.pop(document_id, None)


def submit(conn: psycopg.Connection, pending: PendingBuild) -> None:
    """Queue one file and start it immediately when a slot is free."""
    remember(pending)
    from jewel.documents import repository

    repository.mark_waiting(conn, pending.document_id)
    promote(conn)


def promote(conn: psycopg.Connection) -> None:
    """Start every waiting file that fits the two-file, one-per-account cap."""
    while True:
        claimed = _claim(conn)
        if claimed is None:
            return
        with _pending_lock:
            pending = _pending.pop(str(claimed), None)
        if pending is None:
            _fail_if_extracting(conn, claimed, RESTART_ERROR)
            continue
        if pending.cancel.is_set() or _runner is None:
            _fail_if_extracting(conn, claimed, "stopped")
            continue
        threading.Thread(target=_runner, kwargs=pending.kwargs, daemon=True).start()


def promote_later(database_url: str) -> None:
    """A finished build calls this so the next waiting file can start."""
    with connect(database_url) as conn:
        promote(conn)


def fail_interrupted(conn: psycopg.Connection) -> None:
    """Startup: the in-memory model clients are gone, so unfinished builds cannot resume."""
    conn.execute(
        """
        UPDATE documents
        SET status = %s, error = %s
        WHERE status IN (%s, %s)
        """,
        (
            DocumentStatus.FAILED,
            RESTART_ERROR,
            DocumentStatus.WAITING,
            DocumentStatus.EXTRACTING,
        ),
    )


def run_loop(stop: threading.Event, database_url: str) -> None:
    """Pick up a waiting file if a slot freed without a click, about every two seconds."""
    while not stop.wait(2):
        try:
            promote_later(database_url)
        except Exception:
            logger.exception("build queue could not start a waiting file")


def _claim(conn: psycopg.Connection) -> uuid.UUID | None:
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_LOCK_KEY,))
        row = conn.execute(
            """
            SELECT id FROM documents
            WHERE status = %s
              AND user_id NOT IN (
                  SELECT user_id FROM documents WHERE status = %s
              )
              AND (SELECT count(*) FROM documents WHERE status = %s) < %s
            ORDER BY build_requested_at NULLS LAST, id
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """,
            (
                DocumentStatus.WAITING,
                DocumentStatus.EXTRACTING,
                DocumentStatus.EXTRACTING,
                MAX_EXTRACTING,
            ),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE documents SET status = %s WHERE id = %s",
            (DocumentStatus.EXTRACTING, row["id"]),
        )
        return row["id"]


def _fail_if_extracting(conn: psycopg.Connection, document_id: uuid.UUID, error: str) -> None:
    conn.execute(
        """
        UPDATE documents SET status = %s, error = %s
        WHERE id = %s AND status = %s
        """,
        (DocumentStatus.FAILED, error, document_id, DocumentStatus.EXTRACTING),
    )
