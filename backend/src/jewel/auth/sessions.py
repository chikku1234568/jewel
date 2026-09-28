"""Server-side sessions.

The browser holds a random token in an ``httpOnly``, ``SameSite=Lax`` cookie (``Secure``
unless ``JEWEL_ENV`` is ``local``). Postgres stores only an HMAC-SHA256 of that token keyed
with ``SESSION_SECRET``, plus the user id and an expiry. Logout deletes the row.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
from fastapi import Response

from jewel.config import Settings

SESSION_COOKIE = "jewel_session"
SESSION_TTL = timedelta(days=14)


class SessionConfigError(RuntimeError):
    """Raised when ``SESSION_SECRET`` is missing."""


def _session_id(token: str, secret: str) -> str:
    if not secret:
        raise SessionConfigError("SESSION_SECRET is not configured")
    return hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def create_session(conn: psycopg.Connection, user_id: Any, secret: str) -> str:
    """Create a session row and return the raw token for the cookie."""
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (id, user_id, expires_at) VALUES (%s, %s, %s)",
        (_session_id(token, secret), user_id, datetime.now(UTC) + SESSION_TTL),
    )
    return token


def get_session_user(conn: psycopg.Connection, token: str, secret: str) -> dict[str, Any] | None:
    """Return the user for a live session token, or None."""
    row = conn.execute(
        """
        SELECT u.id, u.email, u.name
        FROM sessions s JOIN users u ON u.id = s.user_id
        WHERE s.id = %s AND s.expires_at > now()
        """,
        (_session_id(token, secret),),
    ).fetchone()
    return row


def delete_session(conn: psycopg.Connection, token: str, secret: str) -> None:
    conn.execute("DELETE FROM sessions WHERE id = %s", (_session_id(token, secret),))


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.env != "local",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.env != "local",
    )
