"""SQL for document rows. Every query is constrained to the owner's ``user_id``."""

import uuid
from typing import Any

import psycopg

from jewel.documents.models import DocumentStatus

_SUMMARY_COLUMNS = "id, filename, uploaded_at, status, error, build_done, build_total, triples_kept"
_DETAIL_COLUMNS = f"{_SUMMARY_COLUMNS}, media_type, document_date, extracted_text"


def insert_document(
    conn: psycopg.Connection, user_id: Any, filename: str, media_type: str, stored_path: str
) -> uuid.UUID:
    document_id = uuid.uuid4()
    conn.execute(
        """
        INSERT INTO documents (id, user_id, filename, media_type, stored_path, status)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (document_id, user_id, filename, media_type, stored_path, DocumentStatus.STORED),
    )
    return document_id


def set_status(conn: psycopg.Connection, document_id: uuid.UUID, status: DocumentStatus) -> None:
    conn.execute("UPDATE documents SET status = %s WHERE id = %s", (status, document_id))


def mark_parsed(conn: psycopg.Connection, document_id: uuid.UUID, text: str) -> None:
    conn.execute(
        "UPDATE documents SET status = %s, extracted_text = %s, error = NULL WHERE id = %s",
        (DocumentStatus.PARSED, text, document_id),
    )


def mark_extracting(conn: psycopg.Connection, document_id: uuid.UUID) -> None:
    conn.execute(
        """
        UPDATE documents
        SET status = %s, error = NULL, build_done = 0, build_total = 0, triples_kept = 0
        WHERE id = %s
        """,
        (DocumentStatus.EXTRACTING, document_id),
    )


def set_build_progress(
    conn: psycopg.Connection, document_id: uuid.UUID, done: int, total: int
) -> None:
    conn.execute(
        """
        UPDATE documents SET build_done = %s, build_total = %s
        WHERE id = %s AND status = %s
        """,
        (done, total, document_id, DocumentStatus.EXTRACTING),
    )


def mark_ready(conn: psycopg.Connection, document_id: uuid.UUID, triples_kept: int) -> None:
    conn.execute(
        "UPDATE documents SET status = %s, error = NULL, triples_kept = %s WHERE id = %s",
        (DocumentStatus.READY, triples_kept, document_id),
    )


def mark_build_failed(conn: psycopg.Connection, document_id: uuid.UUID, error: str) -> None:
    conn.execute(
        "UPDATE documents SET status = %s, error = %s WHERE id = %s",
        (DocumentStatus.FAILED, error, document_id),
    )


def mark_failed(conn: psycopg.Connection, document_id: uuid.UUID, error: str) -> None:
    conn.execute(
        "UPDATE documents SET status = %s, error = %s WHERE id = %s",
        (DocumentStatus.FAILED, error, document_id),
    )


def list_documents(conn: psycopg.Connection, user_id: Any) -> list[dict[str, Any]]:
    return conn.execute(
        f"SELECT {_SUMMARY_COLUMNS} FROM documents WHERE user_id = %s "
        "ORDER BY uploaded_at DESC, id",
        (user_id,),
    ).fetchall()


def get_document(
    conn: psycopg.Connection, user_id: Any, document_id: uuid.UUID
) -> dict[str, Any] | None:
    return conn.execute(
        f"SELECT {_DETAIL_COLUMNS} FROM documents WHERE id = %s AND user_id = %s",
        (document_id, user_id),
    ).fetchone()


def delete_document(conn: psycopg.Connection, user_id: Any, document_id: uuid.UUID) -> str | None:
    """Delete the caller's row; return its stored path, or None if not theirs."""
    row = conn.execute(
        "DELETE FROM documents WHERE id = %s AND user_id = %s RETURNING stored_path",
        (document_id, user_id),
    ).fetchone()
    return row["stored_path"] if row else None


def replace_chunks(
    conn: psycopg.Connection, user_id: Any, document_id: uuid.UUID, texts: list[str]
) -> None:
    """Store this build's chunks as ordinals 0..n-1, replacing any from an earlier build."""
    with conn.transaction():
        conn.execute(
            "DELETE FROM document_chunks WHERE document_id = %s AND user_id = %s",
            (document_id, user_id),
        )
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO document_chunks (id, document_id, user_id, ordinal, text)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (uuid.uuid4(), document_id, user_id, ordinal, text)
                    for ordinal, text in enumerate(texts)
                ],
            )


def chunk_texts(conn: psycopg.Connection, user_id: Any, document_id: str) -> dict[int, str]:
    """Stored chunks of the caller's document by ordinal; empty if none or not theirs."""
    try:
        parsed = uuid.UUID(document_id)
    except ValueError:
        return {}
    rows = conn.execute(
        "SELECT ordinal, text FROM document_chunks WHERE document_id = %s AND user_id = %s",
        (parsed, user_id),
    ).fetchall()
    return {row["ordinal"]: row["text"] for row in rows}
