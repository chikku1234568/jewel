"""Google OAuth 2.0 authorization-code flow with OpenID Connect ID-token checks.

* ``create_authorization_url`` stores a random ``state`` (and ID-token ``nonce``) in
  Postgres and returns the Google consent URL with scopes ``openid email profile``.
* ``consume_state`` deletes and returns the nonce for a live state (single use).
* ``exchange_code`` trades the code for tokens at Google's token endpoint.
* ``verify_id_token`` checks the RS256 signature against Google's published keys and the
  ``iss``, ``aud``, ``exp`` (and ``nonce``) claims.

Tests replace ``exchange_code`` and ``fetch_signing_key``; nothing here is called live in
tests.
"""

import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import psycopg

from jewel.config import Settings

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")
SCOPES = "openid email profile"
STATE_TTL = timedelta(minutes=10)
CLOCK_SKEW_SECONDS = 30


class GoogleAuthError(Exception):
    """Sign-in could not be completed (bad code, bad token, provider error)."""


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    name: str


def create_authorization_url(conn: psycopg.Connection, settings: Settings) -> str:
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    conn.execute("DELETE FROM oauth_states WHERE expires_at <= now()")
    conn.execute(
        "INSERT INTO oauth_states (state, nonce, expires_at) VALUES (%s, %s, %s)",
        (state, nonce, datetime.now(UTC) + STATE_TTL),
    )
    query = urllib.parse.urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
            "nonce": nonce,
            "prompt": "select_account",
        }
    )
    return f"{AUTHORIZATION_ENDPOINT}?{query}"


def consume_state(conn: psycopg.Connection, state: str) -> str | None:
    """Delete a live state and return its nonce; None if unknown or expired."""
    row = conn.execute(
        "DELETE FROM oauth_states WHERE state = %s RETURNING nonce, expires_at",
        (state,),
    ).fetchone()
    if row is None or row["expires_at"] <= datetime.now(UTC):
        return None
    return row["nonce"]


def exchange_code(code: str, settings: Settings) -> str:
    """Exchange the authorization code for tokens; return the ID token."""
    body = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode()
    request = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise GoogleAuthError("token exchange failed") from exc
    id_token = payload.get("id_token")
    if not isinstance(id_token, str):
        raise GoogleAuthError("token response had no id_token")
    return id_token


_jwks_client: jwt.PyJWKClient | None = None


def fetch_signing_key(id_token: str) -> Any:
    """Return Google's public key for the token's ``kid`` (keys are cached)."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(JWKS_URL, cache_keys=True)
    try:
        return _jwks_client.get_signing_key_from_jwt(id_token).key
    except jwt.PyJWTError as exc:
        raise GoogleAuthError("could not load Google signing key") from exc


def verify_id_token(
    id_token: str, *, client_id: str, nonce: str, key: Any | None = None
) -> GoogleIdentity:
    """Verify signature, ``iss``, ``aud``, ``exp`` and ``nonce``; return the identity."""
    signing_key = key if key is not None else fetch_signing_key(id_token)
    try:
        claims = jwt.decode(
            id_token,
            signing_key,
            algorithms=["RS256"],
            audience=client_id,
            leeway=CLOCK_SKEW_SECONDS,
            options={"require": ["iss", "aud", "exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise GoogleAuthError(f"invalid ID token: {type(exc).__name__}") from exc
    if claims.get("iss") not in ISSUERS:
        raise GoogleAuthError("invalid ID token issuer")
    if not nonce or claims.get("nonce") != nonce:
        raise GoogleAuthError("invalid ID token nonce")
    email = claims.get("email")
    if not isinstance(email, str) or not email:
        raise GoogleAuthError("ID token has no email")
    name = claims.get("name") if isinstance(claims.get("name"), str) else ""
    return GoogleIdentity(sub=str(claims["sub"]), email=email, name=name or email)
