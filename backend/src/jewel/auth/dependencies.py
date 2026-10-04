"""FastAPI dependency that resolves the signed-in user from the session cookie."""

from typing import Annotated, Any

from fastapi import Cookie, Depends, HTTPException

from jewel.auth.allowlist import email_is_allowed
from jewel.auth.sessions import SESSION_COOKIE, delete_session, get_session_user
from jewel.db.postgres import AppSettings, DbConn

SessionCookie = Annotated[str | None, Cookie(alias=SESSION_COOKIE)]


def current_user(
    conn: DbConn, settings: AppSettings, session_token: SessionCookie = None
) -> dict[str, Any]:
    """Return ``{id, email, name}`` for the session user, or raise 401."""
    if not session_token:
        raise HTTPException(status_code=401, detail="Not signed in")
    user = get_session_user(conn, session_token, settings.session_secret)
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    if not email_is_allowed(settings, user["email"]):
        delete_session(conn, session_token, settings.session_secret)
        raise HTTPException(status_code=401, detail="Not signed in")
    return user


CurrentUser = Annotated[dict[str, Any], Depends(current_user)]
