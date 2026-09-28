"""Auth routes (stub, NOT mounted yet).

* ``GET /auth/google``: start the authorization-code flow (scopes ``openid``, ``email``,
  ``profile``); store the OAuth ``state`` server-side.
* ``GET /auth/google/callback``: verify ``state``, exchange the code, check the ID token
  (``iss``, ``aud``, ``exp``), create a server session, set an ``httpOnly``, ``Secure``,
  ``SameSite=Lax`` cookie holding the random session id.
* ``POST /auth/logout``: delete the session.
* ``GET /me``: email, name, whether an API key is saved, and its last four characters.

Implementation lives in ``jewel.auth``.
"""

from fastapi import APIRouter

router = APIRouter(tags=["auth"])  # no endpoints yet; not included in the app
