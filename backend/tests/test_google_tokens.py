"""ID-token checks (signature, iss, aud, exp, nonce) with a locally generated key."""

import time

import pytest

from jewel.auth.google import GoogleAuthError, verify_id_token
from tests.fixtures import make_id_token, rsa_keypair

PRIVATE, PUBLIC = rsa_keypair()


def verify(token: str, key=PUBLIC):
    return verify_id_token(token, client_id="test-client-id", nonce="test-nonce", key=key)


def test_valid_token() -> None:
    identity = verify(make_id_token(PRIVATE))
    assert identity.sub == "google-sub-1"
    assert identity.email == "alice@example.com"
    assert identity.name == "Alice Example"


def test_short_issuer_form_is_accepted() -> None:
    assert verify(make_id_token(PRIVATE, iss="accounts.google.com")).sub == "google-sub-1"


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "someone-else"},
        {"iss": "https://evil.example.com"},
        {"exp": int(time.time()) - 3600},
        {"nonce": "other-nonce"},
        {"nonce": None},
        {"exp": None},
        {"email": None},
    ],
)
def test_rejected_claims(overrides: dict) -> None:
    with pytest.raises(GoogleAuthError):
        verify(make_id_token(PRIVATE, **overrides))


def test_wrong_signing_key() -> None:
    other_private, _ = rsa_keypair()
    with pytest.raises(GoogleAuthError):
        verify(make_id_token(other_private))
