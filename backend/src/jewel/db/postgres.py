"""Postgres access (stub).

Planned tables (every row carries ``user_id`` where it belongs to a user): ``users``,
``sessions``, ``oauth_states``, ``api_keys`` (ciphertext), ``documents``, ``chunks``
(text-search index with embeddings), ``ask_runs`` (question, tool trace, answer).

The Postgres client (``psycopg``) is declared in ``pyproject.toml`` because the store is
decided, but nothing imports it yet. Connection string: ``DATABASE_URL``.
"""
