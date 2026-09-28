"""Google sign-in, sessions, logout and /me against a real Postgres.

Google is never called: ``exchange_code`` returns a token signed with a local test key
and ``fetch_signing_key`` returns the matching public key, so the real claim checks run.
"""

import urllib.parse

import pytest

from jewel.auth import google
from jewel.auth.sessions import SESSION_COOKIE
from tests.conftest import make_client
from tests.fixtures import make_id_token, rsa_keypair

PRIVATE, PUBLIC = rsa_keypair()


@pytest.fixture
def fake_google(monkeypatch):
    """Make the token exchange return a signed test ID token for the stored nonce."""
    issued: dict = {"claims": {}}

    def fake_exchange(code: str, settings) -> str:
        assert code == "good-code"
        return make_id_token(PRIVATE, nonce=issued["nonce"], **issued["claims"])

    monkeypatch.setattr(google, "exchange_code", fake_exchange)
    monkeypatch.setattr(google, "fetch_signing_key", lambda token: PUBLIC)
    return issued


def start(client, db) -> str:
    response = client.get("/auth/google", follow_redirects=False)
    assert response.status_code == 302
    location = urllib.parse.urlparse(response.headers["location"])
    assert location.netloc == "accounts.google.com"
    params = urllib.parse.parse_qs(location.query)
    assert params["client_id"] == ["test-client-id"]
    assert params["redirect_uri"] == ["http://localhost:8000/auth/google/callback"]
    assert params["response_type"] == ["code"]
    assert params["scope"] == ["openid email profile"]
    state = params["state"][0]
    row = db.execute("SELECT nonce FROM oauth_states WHERE state = %s", (state,)).fetchone()
    assert row is not None and row["nonce"] == params["nonce"][0]
    return state


def callback(client, state: str, code: str = "good-code"):
    return client.get(
        "/auth/google/callback", params={"code": code, "state": state}, follow_redirects=False
    )


def nonce_for(db, state: str) -> str:
    return db.execute("SELECT nonce FROM oauth_states WHERE state = %s", (state,)).fetchone()[
        "nonce"
    ]


def test_full_sign_in_sets_cookie_and_me_works(client, db, fake_google) -> None:
    state = start(client, db)
    fake_google["nonce"] = nonce_for(db, state)
    response = callback(client, state)

    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:5173"
    set_cookie = response.headers["set-cookie"]
    assert f"{SESSION_COOKIE}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "samesite=lax" in set_cookie.lower()
    assert "secure" not in set_cookie.lower()  # JEWEL_ENV=local

    users = db.execute("SELECT google_sub, email, name FROM users").fetchall()
    assert users == [
        {"google_sub": "google-sub-1", "email": "alice@example.com", "name": "Alice Example"}
    ]
    assert db.execute("SELECT count(*) AS n FROM sessions").fetchone()["n"] == 1
    # The cookie token itself is never stored.
    token = client.cookies.get(SESSION_COOKIE)
    assert (
        db.execute("SELECT count(*) AS n FROM sessions WHERE id = %s", (token,)).fetchone()["n"]
        == 0
    )

    me = client.get("/me")
    assert me.status_code == 200
    assert me.json() == {"email": "alice@example.com", "name": "Alice Example"}


def test_state_is_single_use(client, db, fake_google) -> None:
    state = start(client, db)
    fake_google["nonce"] = nonce_for(db, state)
    assert callback(client, state).headers["location"] == "http://localhost:5173"
    replay = make_client(client.app)
    response = callback(replay, state)
    assert "signin_error=invalid_state" in response.headers["location"]
    assert "set-cookie" not in response.headers


def test_second_sign_in_updates_the_same_user(client, db, fake_google) -> None:
    for name in ("Alice Example", "Alice Renamed"):
        state = start(client, db)
        fake_google["nonce"] = nonce_for(db, state)
        fake_google["claims"] = {"name": name}
        callback(client, state)
    rows = db.execute("SELECT name FROM users").fetchall()
    assert rows == [{"name": "Alice Renamed"}]


def test_unknown_state_is_rejected(client, db, fake_google) -> None:
    response = callback(client, "not-a-real-state")
    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:5173?signin_error=invalid_state"
    assert "set-cookie" not in response.headers
    assert db.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 0


def test_bad_audience_is_rejected(client, db, fake_google) -> None:
    state = start(client, db)
    fake_google["nonce"] = nonce_for(db, state)
    fake_google["claims"] = {"aud": "another-client"}
    response = callback(client, state)
    assert "signin_error=token_invalid" in response.headers["location"]
    assert "set-cookie" not in response.headers
    assert db.execute("SELECT count(*) AS n FROM sessions").fetchone()["n"] == 0


def test_google_error_param(client, db) -> None:
    response = client.get(
        "/auth/google/callback", params={"error": "access_denied"}, follow_redirects=False
    )
    assert "signin_error=google_denied" in response.headers["location"]


def test_secure_cookie_outside_local(app, settings, client, db, fake_google) -> None:
    production = settings.model_copy(update={"env": "production"})
    from jewel.config import get_settings

    app.dependency_overrides[get_settings] = lambda: production
    state = start(client, db)
    fake_google["nonce"] = nonce_for(db, state)
    set_cookie = callback(client, state).headers["set-cookie"].lower()
    assert "secure" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie


def test_logout_deletes_session(client, db, fake_google) -> None:
    state = start(client, db)
    fake_google["nonce"] = nonce_for(db, state)
    callback(client, state)
    assert client.get("/me").status_code == 200

    response = client.post("/auth/logout")
    assert response.status_code == 204
    assert db.execute("SELECT count(*) AS n FROM sessions").fetchone()["n"] == 0
    assert client.get("/me").status_code == 401


def test_me_requires_session(client) -> None:
    assert client.get("/me").status_code == 401


def test_forged_cookie_is_rejected(client) -> None:
    client.cookies.set(SESSION_COOKIE, "forged-token")
    assert client.get("/me").status_code == 401


def test_cors_allows_frontend_with_credentials(client) -> None:
    response = client.options(
        "/me",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
    other = client.options(
        "/me",
        headers={"Origin": "http://evil.example.com", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in other.headers
