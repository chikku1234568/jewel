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
    error           text,
    build_done      integer NOT NULL DEFAULT 0,
    build_total     integer NOT NULL DEFAULT 0
);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS build_done integer NOT NULL DEFAULT 0;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS build_total integer NOT NULL DEFAULT 0;
-- Triples written to the graph by this file's last finished build.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS triples_kept integer NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS documents_user_uploaded_idx ON documents (user_id, uploaded_at DESC);

-- Rows the application can actually store. Applied on every start; skipped once present.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'documents_filename_len') THEN
        ALTER TABLE documents ADD CONSTRAINT documents_filename_len
            CHECK (char_length(filename) BETWEEN 1 AND 255);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'documents_stored_path_shape') THEN
        ALTER TABLE documents ADD CONSTRAINT documents_stored_path_shape
            CHECK (stored_path ~ '^[0-9a-f]{32}$');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'documents_media_type_known') THEN
        ALTER TABLE documents ADD CONSTRAINT documents_media_type_known
            CHECK (media_type IN (
                'application/pdf',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'text/html',
                'text/plain',
                'text/markdown'
            ));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'documents_counts_nonneg') THEN
        ALTER TABLE documents ADD CONSTRAINT documents_counts_nonneg
            CHECK (build_done >= 0 AND build_total >= 0 AND triples_kept >= 0);
    END IF;
END $$;

-- The passages a build sent to the extraction model, in order. Written at the start of
-- each build, before any model call; a rebuild replaces them. A statement stores the
-- ordinal of the chunk its quote came from, so read_document can return that chunk.
-- Removed with the document (ON DELETE CASCADE).
CREATE TABLE IF NOT EXISTS document_chunks (
    id           uuid PRIMARY KEY,
    document_id  uuid NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    user_id      uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    ordinal      integer NOT NULL,
    text         text NOT NULL,
    UNIQUE (document_id, ordinal)
);
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'document_chunks_ordinal_nonneg') THEN
        ALTER TABLE document_chunks ADD CONSTRAINT document_chunks_ordinal_nonneg
            CHECK (ordinal >= 0);
    END IF;
END $$;

-- Raw model output for one passage. Keyed by model, prompt, generation settings, and the
-- exact passage text. Shared across users: the same passage extracts the same triples.
-- The source text is not stored again; documents.extracted_text already has the file.
CREATE TABLE IF NOT EXISTS extraction_cache (
    cache_key   text PRIMARY KEY,
    model       text NOT NULL,
    response    text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
