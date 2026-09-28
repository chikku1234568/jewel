"""User rows in Postgres, keyed by the Google subject (``sub``)."""

import uuid
from typing import Any

import psycopg


def upsert_user(conn: psycopg.Connection, google_sub: str, email: str, name: str) -> dict[str, Any]:
    """Insert the user or refresh email/name for an existing Google subject."""
    row = conn.execute(
        """
        INSERT INTO users (id, google_sub, email, name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (google_sub) DO UPDATE SET email = EXCLUDED.email, name = EXCLUDED.name
        RETURNING id, google_sub, email, name, created_at
        """,
        (uuid.uuid4(), google_sub, email, name),
    ).fetchone()
    assert row is not None
    return row
