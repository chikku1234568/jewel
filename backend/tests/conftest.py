"""Shared fixtures.

Database tests need a real Postgres. Point ``JEWEL_TEST_DATABASE_URL`` at a throwaway
database (the tests truncate its tables). Without it the database tests are skipped
locally, but they FAIL when ``CI`` is set, so CI can never pass by skipping them.

No test calls Google, Neo4j, Kimi or xAI, and no test reads a ``.env`` file.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from jewel.api.app import create_app
from jewel.auth.sessions import SESSION_COOKIE, create_session
from jewel.auth.users import upsert_user
from jewel.config import Settings, get_settings
from jewel.db.postgres import apply_schema, connect

# A local API logs Ask searches unless this is set. Tests leave it off.
os.environ["JEWEL_ASK_LOG"] = ""

TEST_DB_ENV = "JEWEL_TEST_DATABASE_URL"


def _test_settings(upload_dir: Path, database_url: str = "") -> Settings:
    return Settings(_env_file=None).model_copy(
        update={
            "env": "local",
            "database_url": database_url,
            "google_client_id": "test-client-id",
            "google_client_secret": "test-client-secret",
            "google_redirect_uri": "http://localhost:8000/auth/google/callback",
            "frontend_url": "http://localhost:5173",
            "session_secret": "test-session-secret",
            "upload_dir": str(upload_dir),
        }
    )


@pytest.fixture
def upload_dir(tmp_path: Path) -> Path:
    path = tmp_path / "uploads"
    path.mkdir()
    return path


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get(TEST_DB_ENV, "")
    if not url:
        if os.environ.get("CI"):
            pytest.fail(f"{TEST_DB_ENV} must be set in CI; database tests may not be skipped")
        pytest.skip(f"{TEST_DB_ENV} not set; skipping database tests")
    return url


@pytest.fixture
def db(database_url: str) -> Iterator[psycopg.Connection]:
    with connect(database_url) as conn:
        apply_schema(conn)
        conn.execute("TRUNCATE users, sessions, oauth_states, documents CASCADE")
        yield conn


@pytest.fixture
def settings(upload_dir: Path, db: psycopg.Connection, database_url: str) -> Settings:
    return _test_settings(upload_dir, database_url)


@pytest.fixture
def app(settings: Settings):
    application = create_app(settings)
    application.dependency_overrides[get_settings] = lambda: settings
    return application


def make_client(app) -> TestClient:
    return TestClient(app, base_url="http://localhost:8000")


@pytest.fixture
def client(app) -> TestClient:
    return make_client(app)


def sign_in(
    client: TestClient, conn: psycopg.Connection, settings: Settings, sub: str, email: str
) -> dict:
    """Create a user and a session directly (no Google), and give the client the cookie."""
    user = upsert_user(conn, sub, email, email.split("@")[0].title())
    token = create_session(conn, user["id"], settings.session_secret)
    client.cookies.set(SESSION_COOKIE, token)
    return user
