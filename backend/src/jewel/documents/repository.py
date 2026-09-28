"""SQL for document rows. Every query is constrained to the owner's ``user_id``."""

import uuid
from typing import Any

import psycopg

from jewel.documents.models import DocumentStatus

_SUMMARY_COLUMNS = "id, filename, uploaded_at, status, error"
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
