-- jewel application data (Postgres). Idempotent: safe to apply on every start.
-- Applied by jewel.db.postgres.apply_schema().

CREATE TABLE IF NOT EXISTS users (
    id          uuid PRIMARY KEY,
    google_sub  text NOT NULL UNIQUE,
    email       text NOT NULL,
    name        text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- sessions.id is an HMAC-SHA256 (keyed with SESSION_SECRET) of the random token held in
-- the browser cookie; the raw token is never stored.
CREATE TABLE IF NOT EXISTS sessions (
    id          text PRIMARY KEY,
    user_id     uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    expires_at  timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions (user_id);

-- OAuth round-trip state (and the ID-token nonce), single use, short-lived.
CREATE TABLE IF NOT EXISTS oauth_states (
    state       text PRIMARY KEY,
    nonce       text NOT NULL,
    expires_at  timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id              uuid PRIMARY KEY,
    user_id         uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    filename        text NOT NULL,
    media_type      text NOT NULL,
    stored_path     text NOT NULL,          -- opaque server-generated name under JEWEL_UPLOAD_DIR
    uploaded_at     timestamptz NOT NULL DEFAULT now(),
    document_date   date,                   -- null in this pass (no date guessing)
    extracted_text  text,
    status          text NOT NULL CHECK (
        status IN ('stored', 'parsing', 'parsed', 'failed', 'extracting', 'ready')
    ),
    error           text
);
CREATE INDEX IF NOT EXISTS documents_user_uploaded_idx ON documents (user_id, uploaded_at DESC);
