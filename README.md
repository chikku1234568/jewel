# jewel

jewel is a personal live knowledge graph over your own documents. You sign in with
Google, upload PDF, Word, PowerPoint, Excel, HTML, `.txt` or `.md` files, and build each file into a
knowledge graph that belongs only to your account. You can browse the entities and the
sentences that connect them, and ask questions. One agent answers by searching your graph
and quoting the passages of your files that it used.

Answers quote your documents. They are not medical, legal, or financial advice.

There is no billing, no teams and no sharing. Each account sees only its own files and
graph.

## How it works

1. **Sign in.** Google OAuth (authorization-code flow, scopes `openid email profile`).
   The API keeps a server-side session and gives the browser an `httpOnly` cookie.
2. **Upload.** The API checks the file (type, 20 MB cap, 20-page cap for PDFs), stores
   the bytes, extracts the text in the same request, and saves the text in Postgres. A PDF over 20 pages is rejected and not stored.
3. **Build.** On request, one file at a time: the text is split into passages, a chat
   model extracts entities and `subject - predicate - object` triples with a verbatim
   quote, an embedding model embeds the document, entities and facts, and the result is
   written to Neo4j under your user id. The extraction model is an OpenAI-compatible chat
   API, and the build request must include your API key. The embedding model is an
   OpenAI-compatible embeddings API, and that request must include your API key too. Model output for each
   passage is cached in Postgres, so rebuilding the same text with the same model does not
   call the model again. The build runs in the background; the page shows progress and can
   stop it.
4. **Ask.** One agent decides, step by step, whether to call `search_graph` or
   `read_document`, at most four times, then answers. `search_graph` is a
   HippoRAG-2-style retriever: it links the question to your facts by embedding
   similarity, keeps only facts valid at the question time, and ranks your documents with
   Personalized PageRank over your graph (graph built with networkx). `read_document`
   only opens documents that a search in the same run returned. The answer model defaults
   to Kimi (`kimi-k2.6`) through its OpenAI-compatible API; any OpenAI-compatible chat
   model can be chosen instead.

Model choices and any API key you type are sent with each build or ask request. The
server uses the key for that request only and does not store it. The browser keeps your
choices, including typed keys, in `sessionStorage` for the current tab.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Vite, React 19, TypeScript, React Router |
| API | Python 3.11+, FastAPI, Pydantic, uvicorn, managed with uv |
| App data | Postgres 17 (users, sessions, OAuth state, documents and extracted text, extraction cache), psycopg, no ORM |
| Graph | Neo4j 5 Community (`neo4j:5.26-community`), official Python driver |
| Retrieval | Embedding similarity plus Personalized PageRank over a networkx graph, in the API process |
| Parsing | MarkItDown to Markdown (PDF text layer only, no OCR; .docx, .pptx, .xlsx, .html), pypdf page count, UTF-8 text |
| Models | OpenAI-compatible APIs for extraction, embeddings, and answers. The user supplies the key. |
| CI | GitHub Actions: ruff and pytest against Postgres; oxlint, typecheck and build for the frontend |

## Repository map

```text
backend/src/jewel/
  api/            FastAPI app and routes: health, auth, documents (upload, build, stop), graph, ask
  auth/           Google OAuth, server-side sessions, current-user dependency
  db/             Postgres connection and schema.sql (applied at startup)
  documents/      Upload rules, file storage under JEWEL_UPLOAD_DIR, document rows
  parsing/        Uploads to Markdown (MarkItDown), PDF page check, plain text
  ingestion/      Passage extraction, extraction cache, build pipeline
  kg/             Extraction parsing, graph records, Neo4j and in-memory stores
  retrieval/hippo Linking, time filter and Personalized PageRank
  agents/         The LangGraph tool-calling agent (create_agent) and its chat adapter
  llm/            OpenAI-compatible chat, embedders, per-request model choices
backend/tests/    pytest suite (database tests need a throwaway Postgres)
frontend/src/     Landing page, signed-in workspace (Documents, Graph, Ask), API client
infra/            docker-compose for local Postgres and Neo4j (plus dev-only app containers)
docs/             System design, deployment strategy, spec, ADRs, diagrams
data/fixtures/    Description of the two-document test fixture
```

## Local development

Requirements: [uv](https://docs.astral.sh/uv/), Node.js 20.19 or later, Docker, and a
Google account. Building a file needs an API key for the extraction model, typed in the app.

### 1. Google OAuth client

In the Google Cloud Console, configure the OAuth consent screen (External, publishing
status Testing, and add your own Google account as a test user). Then create an OAuth
client of type **Web application** and add this authorized redirect URI:

```text
http://localhost:8000/auth/google/callback
```

The flow is server-side, so no authorized JavaScript origin is needed.

### 2. Environment

```bash
cp .env.example .env
```

Fill in `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
`GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback` and a long random
`SESSION_SECRET` (for example `openssl rand -hex 32`). The database values in
`.env.example` match the local docker-compose defaults. To let the answer model work
without typing a key in the page, also add `KIMI_API_KEY=<your Moonshot key>` to `.env`.

Use `localhost`, not `127.0.0.1`, for both the API and the frontend. The session cookie
is set by `localhost:8000` and must be sent by pages served from `localhost:5173`, and
`JEWEL_FRONTEND_URL` is the one origin the API allows through CORS.

### 3. Databases

```bash
docker compose -f infra/docker-compose.yml --env-file .env up -d postgres neo4j
```

Postgres listens on 5432 and Neo4j on 7687 (Neo4j Browser on 7474). The API creates its
Postgres tables at startup.

### 4. API

```bash
cd backend
uv sync
uv run --env-file ../.env uvicorn jewel.api.app:app --reload   # http://localhost:8000/health
```

`--env-file ../.env` matters: the settings class only looks for `.env` in the current
directory, and `KIMI_API_KEY` is read from the process environment. It is the fallback
for the answer model only, when that request carries no key. Extraction always uses the
key typed in the app.

### 5. Frontend

```bash
cd frontend
npm ci
npm run dev                                                     # http://localhost:5173
```

The frontend calls `http://localhost:8000` unless `VITE_API_BASE_URL` is set at build
time (Vite reads it from the shell or from `frontend/.env*`, not from the repository-root
`.env`).

`make help` lists shortcuts (`make test`, `make lint`, `make typecheck`, `make build`).
`make up` starts every compose service, but the backend and frontend containers are
development placeholders: the backend container is not given `KIMI_API_KEY`, and the
frontend container runs the Vite dev server.
Running the API and frontend on the host, as above, is the supported path.

## Configuration

Values live in `.env` (never commit it). Names come from `.env.example`,
`backend/src/jewel/config.py` and the modules that read the environment directly.

| Variable | Used by | Purpose |
|---|---|---|
| `JEWEL_ENV` | API | `local` turns off the `Secure` flag on the session cookie. Any other value (for example `production`) sets it. |
| `GOOGLE_CLIENT_ID` | API | Google OAuth client id. |
| `GOOGLE_CLIENT_SECRET` | API | Google OAuth client secret, used in the code exchange. |
| `GOOGLE_REDIRECT_URI` | API | Callback URL sent to Google. Must exactly match an authorized redirect URI on the client. |
| `JEWEL_FRONTEND_URL` | API | Where the browser is sent after sign-in, and the single origin allowed by CORS with credentials. |
| `SESSION_SECRET` | API | Key for the HMAC that turns the cookie token into the stored session id. Sign-in fails without it. |
| `DATABASE_URL` | API | Postgres connection string. |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | API | Neo4j connection. Without a password, build, graph and ask return 503. |
| `JEWEL_UPLOAD_DIR` | API | Directory for uploaded file bytes (default `./data/uploads`). |
| `KIMI_API_KEY` | API | Server-side key for the answer model, used when that request carries no key. Extraction does not use it. |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | docker-compose | Credentials for the local Postgres container. |
| `VITE_API_BASE_URL` | frontend build | API base URL compiled into the frontend (default `http://localhost:8000`). |
| `JEWEL_TEST_DATABASE_URL` | tests | Throwaway Postgres for the database tests. |

`KEY_ENCRYPTION_SECRET`, `JEWEL_LLM_MODEL` and `JEWEL_EMBEDDING_MODEL` appear in
`.env.example` and `config.py` but are not used by any request path today. They are left
over from an earlier design in which users saved an xAI key.

## Testing

```bash
docker compose -f infra/docker-compose.yml --env-file .env up -d postgres
docker compose -f infra/docker-compose.yml exec postgres createdb -U jewel jewel_test

cd backend
JEWEL_TEST_DATABASE_URL=postgresql://jewel:jewel@localhost:5432/jewel_test uv run pytest
uv run ruff check . && uv run ruff format --check .

cd ../frontend
npm run lint && npm run typecheck && npm run build
```

The database tests apply the schema and then **truncate** the `users`, `sessions`,
`oauth_states` and `documents` tables. Point `JEWEL_TEST_DATABASE_URL` only at a database
you can wipe. Without it the database tests are skipped locally; in CI (when `CI` is set)
they fail instead of skipping. No test calls Google, Neo4j, Kimi or any other
model API.

## Documentation

Read in this order if you want to run jewel in production:

1. [System design](docs/system-design.md): components, the state each one holds, the main
   flows as sequence diagrams, and what in the current code must change before
   production.
2. [Deployment strategy](docs/deployment-strategy.md): hosting options, the recommended
   setup, environments and delivery pipeline, configuration and secrets, security,
   operations, and a phased rollout checklist.
3. [Backend structure](docs/backend-structure.md): code map of `backend/`, every API route,
   core flows traced through files and functions, data stores, config and known gaps.

Background:

- [Product spec](docs/problem-statement.md) and [architecture sketch](docs/architecture.md).
  Both were written for the scaffold and predate the implementation. Where they differ
  from the code (for example the saved per-user xAI key, Server-Sent Events, LangGraph and
  Cytoscape), the code and the system design doc describe what actually runs.
- [Decision records](docs/decisions/) and [rendered diagrams](docs/diagrams/) from the
  scaffold.
