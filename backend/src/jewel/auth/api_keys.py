"""Per-user xAI API key at rest (stub).

TODO(later pass): encrypt with an application secret (``KEY_ENCRYPTION_SECRET``) and
store ciphertext only in Postgres; expose "a key is saved" plus the last four characters;
decrypt only server-side when making a model call for that user. Never log the key.
There is no project key serving user traffic.
"""
