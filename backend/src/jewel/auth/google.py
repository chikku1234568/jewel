"""Google OAuth authorization-code flow (stub).

TODO(later pass):
* Build the authorization URL with scopes ``openid email profile`` (no Gmail, no Drive)
  and a random ``state`` stored server-side for the round trip.
* On callback: check ``state``, exchange the code with ``GOOGLE_CLIENT_ID`` /
  ``GOOGLE_CLIENT_SECRET`` / ``GOOGLE_REDIRECT_URI``, verify the ID token (``iss``,
  ``aud``, ``exp``), and upsert the user row in Postgres keyed by Google ``sub``.
"""
