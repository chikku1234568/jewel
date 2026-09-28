"""Server-side sessions (stub).

TODO(later pass): random session id stored in Postgres (derived with ``SESSION_SECRET``
material), sent as an ``httpOnly``, ``Secure``, ``SameSite=Lax`` cookie. Logout deletes the
row. A request dependency resolves the current user id from the session; every
store call takes that id.
"""
