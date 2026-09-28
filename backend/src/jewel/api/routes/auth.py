"""Auth routes (mounted).

* ``GET /auth/google``: start the authorization-code flow (scopes ``openid``, ``email``,
  ``profile``); the OAuth ``state`` is stored server-side.
* ``GET /auth/google/callback``: check ``state``, exchange the code, verify the ID token
  (``iss``, ``aud``, ``exp``, ``nonce``), upsert the user, create a session row, set the
  ``httpOnly``, ``SameSite=Lax`` cookie (``Secure`` unless ``JEWEL_ENV=local``) and redirect
  the browser to ``JEWEL_FRONTEND_URL``. Failures redirect there with ``?signin_error=...``
  and set no cookie.
* ``POST /auth/logout``: delete the session and clear the cookie.
* ``GET /me``: email and name of the signed-in user. No API-key fields.
"""

import logging
import urllib.parse

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import RedirectResponse

from jewel.auth import google
from jewel.auth.dependencies import CurrentUser, SessionCookie
from jewel.auth.sessions import (
    SessionConfigError,
    clear_session_cookie,
    create_session,
    delete_session,
    set_session_cookie,
)
from jewel.auth.users import upsert_user
from jewel.config import Settings
from jewel.db.postgres import AppSettings, DbConn

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


def _frontend_redirect(settings: Settings, error: str | None = None) -> RedirectResponse:
    url = settings.frontend_url or "/"
    if error:
        url = f"{url}?{urllib.parse.urlencode({'signin_error': error})}"
    return RedirectResponse(url, status_code=302)


@router.get("/auth/google")
def start_google_sign_in(conn: DbConn, settings: AppSettings) -> RedirectResponse:
    if not (settings.google_client_id and settings.google_redirect_uri):
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")
    return RedirectResponse(google.create_authorization_url(conn, settings), status_code=302)


@router.get("/auth/google/callback")
def finish_google_sign_in(
    conn: DbConn,
    settings: AppSettings,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error:
        return _frontend_redirect(settings, "google_denied")
    if not code or not state:
        return _frontend_redirect(settings, "missing_code")
    nonce = google.consume_state(conn, state)
    if nonce is None:
        return _frontend_redirect(settings, "invalid_state")
    try:
        id_token = google.exchange_code(code, settings)
        identity = google.verify_id_token(
            id_token, client_id=settings.google_client_id, nonce=nonce
        )
    except google.GoogleAuthError as exc:
        logger.info("Google sign-in rejected: %s", exc)
        return _frontend_redirect(settings, "token_invalid")

    user = upsert_user(conn, identity.sub, identity.email, identity.name)
    try:
        token = create_session(conn, user["id"], settings.session_secret)
    except SessionConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    response = _frontend_redirect(settings)
    set_session_cookie(response, token, settings)
    return response


@router.post("/auth/logout", status_code=204)
def logout(conn: DbConn, settings: AppSettings, session_token: SessionCookie = None) -> Response:
    if session_token and settings.session_secret:
        delete_session(conn, session_token, settings.session_secret)
    response = Response(status_code=204)
    clear_session_cookie(response, settings)
    return response


@router.get("/me")
def me(user: CurrentUser) -> dict[str, str]:
    return {"email": user["email"], "name": user["name"]}
