"""Postgres access with psycopg (no ORM).

Connections are opened per request in autocommit mode, so each status change of a
document is visible as soon as it is written. The schema lives in ``schema.sql`` next to
this module and is applied idempotently at app start (when ``DATABASE_URL`` is set) or by
running ``python -m jewel.db.postgres``.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

import psycopg
from fastapi import Depends, HTTPException
from psycopg.rows import dict_row

from jewel.config import Settings, get_settings

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(database_url: str) -> psycopg.Connection:
    """Open an autocommit connection that returns rows as dicts."""
    return psycopg.connect(database_url, autocommit=True, row_factory=dict_row)


def apply_schema(conn: psycopg.Connection) -> None:
    """Create tables and indexes if they do not exist."""
    conn.execute(SCHEMA_PATH.read_text())


def get_db(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[psycopg.Connection]:
    """FastAPI dependency: one connection per request."""
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured")
    with connect(settings.database_url) as conn:
        yield conn


DbConn = Annotated[psycopg.Connection, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


if __name__ == "__main__":
    url = get_settings().database_url
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    with connect(url) as connection:
        apply_schema(connection)
    print("schema applied")
