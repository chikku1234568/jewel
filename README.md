# jewel

A personal knowledge graph for your own documents.

You sign in with Google, upload a file, and build it into a graph that belongs only to your account. You can pan that graph, or ask a question. One agent searches the graph and quotes the passages it used. The page shows each step.

Answers quote your documents. They are not medical, legal, or financial advice. There is no billing, no teams, and no shared library. A second account cannot see the first account's files or graph.

[tryjewel.dev](https://tryjewel.dev) is a short retired notice. These instructions are how you run jewel yourself.

## Run it locally

You need Docker, [uv](https://docs.astral.sh/uv/), Node.js 20.19 or newer, a Google account, and an API key for an OpenAI-compatible chat and embeddings API. The key is typed into the page. The server uses it for that request and does not store it.

Windows notes for one particular laptop are in [docs/run-local.md](docs/run-local.md). The commands below are the usual path.

### 1. Google sign-in

In the Google Cloud console, create an OAuth client of type **Web application**. Add this authorized redirect URI:

```text
http://localhost:8000/auth/google/callback
```

The scopes the app requests are `openid`, `email`, and `profile`. No JavaScript origin is required.

### 2. Environment

```bash
cp .env.example .env
```

Fill in `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, and a long random `SESSION_SECRET` (`openssl rand -hex 32`). The database values in `.env.example` match the local Compose file. Use `localhost`, not `127.0.0.1`, for the API and the page, so the sign-in cookie is sent.

Do not commit `.env`. A production file, `infra/prod.env`, stays on the host as well. `infra/prod.env.example` shows the names and nothing else.

### 3. Databases

```bash
docker compose -f infra/docker-compose.yml --env-file .env up -d postgres neo4j
```

Postgres listens on port 5432. Neo4j Browser is on 7474 and Bolt is on 7687. The API creates its tables on startup.

### 4. API

```bash
cd backend
uv sync
uv run --env-file ../.env uvicorn jewel.api.app:app --reload
```

Health is [http://localhost:8000/health](http://localhost:8000/health).

### 5. Page

```bash
cd frontend
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Sign in, upload a file, paste your model key, and press Build.

## What a session does

1. **Sign in.** Google's code flow. The API stores a session in Postgres and sets an `httpOnly` cookie. Outside local development, `JEWEL_ALLOWED_EMAILS` is the list of addresses that may sign in. An empty list on a non-local server admits nobody.
2. **Upload.** The API checks the type, a 20 MB cap, and a 20-page cap for PDFs. Text is taken from the file in that request. Scanned PDFs are not read, because there is no OCR. Accepted types are PDF, Word, PowerPoint, Excel, HTML, `.txt`, and `.md`.
3. **Build.** The click records the file as waiting and returns. At most two files extract at once, and only one of those belongs to one account. Each extracting file sends eight passages at a time. The model returns entities and `subject - predicate - object` triples with a quote from the passage. Embeddings and the graph are written under your user id. A passage that was already extracted with the same model and prompt is skipped. Stop works on a waiting file and on an extracting file. A restart marks an unfinished build failed, because the key was only in memory. Press Build again.
4. **Ask.** One agent calls `search_graph` or `read_document`, one tool at a time, at most 12 calls. Search ranks your facts with embedding similarity and Personalized PageRank. `read_document` opens at most three passages of a file that this search already returned. Each account may upload 30 files, start 20 builds, and ask 60 questions per hour. A restart clears those counts.

## Stack

| Layer | Technology |
|---|---|
| Page | Vite, React 19, TypeScript, Cytoscape.js |
| API | Python 3.11+, FastAPI, Pydantic, uvicorn, uv |
| Accounts and files | Postgres 17, psycopg, no ORM |
| Graph | Neo4j 5 Community (`neo4j:5.26-community`) |
| Agent | LangGraph, two tools |
| Parsing | MarkItDown. PDF text layer only |
| Models | Any OpenAI-compatible chat and embeddings API. You bring the key |
| Production shape | Caddy, Docker Compose, GitHub Actions. See [docs/system-architecture.md](docs/system-architecture.md) |
| Tests | ruff and pytest. Frontend lint, typecheck, and build |

## Repository

```text
backend/src/jewel/
  api/            routes: health, auth, documents, graph, ask, hourly limits
  auth/           Google sign-in, sessions, the allowlist
  db/             Postgres connection and schema.sql
  documents/      upload rules, storage, the build queue
  parsing/        files to Markdown
  ingestion/      passages, the extraction cache, the build
  kg/             triples, Neo4j, and an in-memory store for tests
  retrieval/      linking and Personalized PageRank
  agents/         the tool-using agent
  llm/            OpenAI-compatible chat and embeddings
backend/tests/    pytest
frontend/src/     sign-in, library, graph, ask
infra/            Compose for local databases, and the production Compose file
docs/             spec, decisions, diagrams
```

## Tests

The database tests truncate their tables. Give them a database named `jewel_test`, not the database you use for real documents.

```bash
docker compose -f infra/docker-compose.yml --env-file .env up -d postgres
docker compose -f infra/docker-compose.yml exec postgres createdb -U jewel jewel_test

cd backend
JEWEL_TEST_DATABASE_URL=postgresql://jewel:jewel@localhost:5432/jewel_test uv run pytest
uv run ruff check . && uv run ruff format --check .

cd ../frontend
npm run lint && npm run typecheck && npm run build
```

No test calls Google or a model API.

## Configuration

Names are in `.env.example` and `backend/src/jewel/config.py`.

| Variable | Purpose |
|---|---|
| `JEWEL_ENV` | `local` leaves the session cookie unsecured. Any other value marks it `Secure`. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | The OAuth client. The redirect URI must match the client exactly. |
| `JEWEL_FRONTEND_URL` | Where the browser goes after sign-in, and the one origin CORS allows. |
| `JEWEL_ALLOWED_EMAILS` | Comma-separated. Empty allows any Google account when `JEWEL_ENV=local`, and nobody otherwise. |
| `SESSION_SECRET` | HMAC key for the session id. Sign-in fails without it. |
| `DATABASE_URL` | Postgres. |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | Neo4j. Build, the graph, and Ask return 503 without a password. |
| `JEWEL_UPLOAD_DIR` | Where uploaded bytes go. Default `./data/uploads`. |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | The local Postgres container. |
| `VITE_API_BASE_URL` | API address compiled into the page. Default `http://localhost:8000`. |
| `JEWEL_TEST_DATABASE_URL` | Throwaway Postgres for pytest. |

`KEY_ENCRYPTION_SECRET`, `JEWEL_LLM_MODEL`, and `JEWEL_EMBEDDING_MODEL` remain in `.env.example` from an earlier design that stored a key. No request reads them.

The Deploy workflow logs into a host named by the Actions secret `JEWEL_SSH_HOST` (`user@host`). It also needs `JEWEL_SSH_PRIVATE_KEY` and `JEWEL_SSH_KNOWN_HOSTS`. A green test run on `main` rebuilds that host only when the repository variable `JEWEL_AUTO_DEPLOY` is `true`.

## Further reading

- [Product spec](docs/problem-statement.md), written before this implementation. Where it disagrees with the code, trust the code and this file.
- [System architecture](docs/system-architecture.md) and the [diagrams](docs/diagrams/).
- [Decision records](docs/decisions/).

## License

[MIT](LICENSE).
