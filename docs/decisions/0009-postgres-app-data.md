# 0009. Postgres for application data

- **Status:** Accepted (settled by `docs/problem-statement.md`, 2026-09-28)

## Context

Accounts, sessions, OAuth state, document rows and statuses, ciphertext API keys, text
chunks for the comparison, and question traces are relational application data, not graph
data.

## Decision

Use **Postgres** (local image `postgres:17-alpine`) for users, sessions, OAuth state,
documents, ciphertext keys, chunks (with embeddings) and ask runs. File bytes stay on a
local volume. Connection string: `DATABASE_URL`. The `psycopg` client is declared in
`backend/pyproject.toml`; no stub imports it yet.

## Consequences

- Two stores (Postgres + Neo4j) with the user id as the shared key; deleting a document
  touches both.
- Every user-owned row carries `user_id`.
