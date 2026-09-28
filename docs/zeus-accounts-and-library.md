# Task: Google sign-in and the document library

You are implementing the next pass of **jewel** (`https://github.com/chikku1234568/jewel`, branch off current `main`). The repo is a scaffold: `GET /health` is the only mounted route, and the page is a placeholder. Do not re-open product decisions. Do not implement the knowledge graph, embeddings, PageRank, or the agent.

Another session owns the graph build and the agent. Stay inside the files listed under **Your files**. Leave the rest untouched.

## What jewel is

A person signs in with Google, uploads their own files, and later gets a knowledge graph of those files plus one agent that searches that graph. This pass stops at: they are signed in, their files are stored, and the text has been extracted. The graph does not exist yet.

Decisions already locked, so you do not invent alternatives:

- Free, one user, their own files. No teams, billing, sharing, Gmail, or Drive.
- Google is the only sign-in. Authorization-code flow. Scopes `openid`, `email`, `profile`.
- Postgres holds users, sessions, and document rows. Neo4j is not yours.
- Accepted files: `.pdf`, `.md`, `.txt`, `.docx`. Cap 20 MB. PDF cap 50 pages. No OCR, no PowerPoint, Excel, HTML, EPUB, or images.
- A PDF with no text layer fails with a clear error. The file is kept.
- Building the graph does **not** use the user's API key. A local open-source model does that in a later pass. Do not add `waiting_for_key` to the upload flow. Do not require a key before upload or parse.
- The agent, later, is one LangGraph agent (`langchain.agents.create_agent`) with tools `search_graph` and `read_document`. Tests for that agent use Kimi (`KIMI_API_KEY` in `.env`, base URL `https://api.moonshot.ai/v1`). Embeddings will be local `BAAI/bge-base-en-v1.5`. Extraction will be local Qwen via Ollama. None of that is this pass. Do not read or copy `.env`.
- A second upload must not reprocess the first file. Your API stores each file on its own. Do not add a "rebuild all documents" action.
- Redis stays out. Do not bring back `jewel.cache`.

Ignore stale comments that say extraction uses the user's xAI key, or that `JEWEL_LLM_MODEL` / `https://api.x.ai/v1` is the embedding path. Those comments predate the decisions above. Do not "fix" them by wiring xAI.

## Status contract

This is the handoff to the graph pass. Use these statuses and no others for the paths you own.

| Status | Who sets it | Meaning |
|---|---|---|
| `parsing` | you | Text extraction is running |
| `parsed` | you | Text is in Postgres. The graph has not been built. **This is the success status for this pass.** |
| `failed` | you | Bad type, over size, over page cap, empty text, or a parse error. The row and the file remain. `error` is a short string the library can show. |
| `extracting` | graph pass, later | Do not set this |
| `ready` | graph pass, later | Graph for this file is written. Do not set this |

Add `parsed` to `DocumentStatus`. Stop using `waiting_for_key` in the upload flow. `stored` may exist for the moment between saving bytes and starting parse; the status the library shows after a successful upload is `parsed`.

`MAX_UPLOAD_BYTES` (20 MB) and `MAX_PDF_PAGES` (50) stay. Over-cap uploads are rejected and **not** stored.

Add Word to the accepted types: `.docx` (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`), plus the existing PDF, plain text, and Markdown types.

## Accounts

- `GET /auth/google` starts OAuth. Store `state` server-side for the round trip.
- `GET /auth/google/callback` checks the ID token (`iss`, `aud`, `exp`), upserts the user (Google subject, email, name), creates a session row, and sets a cookie.
- Cookie: random session id, `httpOnly`, `SameSite=Lax`. Set `Secure` only when `JEWEL_ENV` is not `local`, so localhost over HTTP still works.
- `POST /auth/logout` deletes the session.
- `GET /me` returns email, name. No API-key fields. Do not implement `/me/api-key`.
- No passwords, no second provider, no guest, no fake logged-in user.
- Settings already exist: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `SESSION_SECRET`, `DATABASE_URL`. Read them from `jewel.config.Settings`. Do not add a project LLM key.

Every document route requires a session. The user id comes from the session, never from a client-supplied owner field alone.

## Documents

Postgres tables, via `psycopg` (already a dependency). A SQL file next to `jewel.db` is enough. No ORM required.

- `users`: id, google_sub unique, email, name, created_at.
- `sessions`: id, user_id, expires_at.
- `documents`: id, user_id, filename, media_type, stored_path (opaque, not a client path), uploaded_at, document_date nullable, extracted_text, status, error nullable.

`document_date` stays null in this pass unless you already have an obvious single date from the file with no extra guessing. Do not invent dates.

Flow for `POST /documents` (multipart, one file):

1. Reject a missing session, a disallowed type, or an over-cap file before writing bytes.
2. Write bytes under `JEWEL_UPLOAD_DIR` at an opaque path. Insert the row.
3. Set `parsing`. Parse to text.
   - PDF: the existing `DocumentParser` / pypdf path.
   - `.txt` and `.md`: read as UTF-8 text.
   - `.docx`: convert to text with a small library you add for that purpose.
4. If the text is empty or whitespace, set `failed` and an error like "No text could be extracted".
5. Otherwise save `extracted_text` and set `parsed`.

Also:

- `GET /documents` returns the caller's rows: id, filename, uploaded_at, status, error. No extracted text in the list.
- `GET /documents/{id}` returns the row including extracted text when the caller owns it. 404 when they do not.
- `DELETE /documents/{id}` deletes the row and the file when the caller owns it. 404 when they do not. Do not touch Neo4j.

Do not implement `POST /documents/{id}/build`. That route is the graph pass.

## HTTP

Mount on the FastAPI app:

- The auth routes above and `GET /me`.
- The document routes above.

Leave mounted: `GET /health`.

Do not mount `/ask`, `/graph`, or any key route.

## Frontend

The Vite app already has the advice sentence, an inert Sign in button, and empty Documents, Graph, and Ask regions.

- Sign in with Google goes to `GET /auth/google` on the API (`VITE_API_BASE_URL`). After callback, the page shows the Google name and email and a sign-out control that calls `POST /auth/logout`.
- Documents: pick a file, upload, list filename, time, and status. Show `error` when status is `failed`. Empty copy invites a PDF, text, Markdown, or Word file.
- Graph and Ask stay empty and disabled. Do not add Cytoscape. You may delete the sentence that says asking needs an xAI key, since that decision is gone. Do not build an API-key form.

## Tests

No live calls to Google, Neo4j, Ollama, Kimi, or xAI.

- Parsers: a tiny PDF, a `.txt`, a `.md`, a `.docx`, and a PDF or docx that yields no text.
- Over 20 MB is rejected and leaves no row and no file. A PDF over 50 pages is rejected the same way.
- With two users in the database, user A cannot `GET` or `DELETE` user B's document.
- `GET /health` still returns its current body.
- `pytest` and `ruff check` pass.

## Your files

You may create and edit:

- `backend/src/jewel/auth/`
- `backend/src/jewel/db/`
- `backend/src/jewel/documents/`
- `backend/src/jewel/parsing/`
- `backend/src/jewel/api/routes/auth.py`
- `backend/src/jewel/api/routes/documents.py`
- `backend/src/jewel/api/app.py` (mount only the routes named above)
- `backend/src/jewel/config.py` only if a Google or Postgres setting is missing. Do not remove settings you do not understand.
- `backend/tests/` for the tests above
- `backend/pyproject.toml` and `uv.lock` if the docx parser needs a library
- `frontend/src/` for sign-in and the library
- `.env.example` with empty Google values only if a name is missing. Never commit `.env`.

## Do not touch

- `backend/src/jewel/kg/`
- `backend/src/jewel/retrieval/`
- `backend/src/jewel/agents/`
- `backend/src/jewel/llm/`
- `backend/src/jewel/ingestion/`
- `backend/src/jewel/api/routes/ask.py`
- `backend/src/jewel/api/routes/graph.py`
- `backend/src/jewel/api/routes/keys.py`
- `docs/problem-statement.md`, `docs/architecture.md`, and the ADRs, except a one-line note is unnecessary. The status `parsed` lives in code.

Do not add Redis, LangGraph, Neo4j writes, Ollama, embeddings, or a sample corpus.

## Done

A reviewer can sign in with Google on localhost, upload one PDF and one `.docx`, see both as `parsed`, open the extracted text, and sign out. A second account cannot see those rows. `GET /health` still works. Graph and Ask are still empty. Open a PR against `main`.
