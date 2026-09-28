# jewel

**A personal live knowledge graph.** Sign in with Google, upload your own PDF, `.txt` and
`.md` files, and get a knowledge graph of them that you can click through. Save your own
xAI API key and ask one agent questions: it searches your graph, the screen shows each
step of the search and highlights what came back, and the answer quotes the passages it
used. A text-search comparison shows what the same question gets from text chunks alone.

Answers quote your documents and are not medical, legal, or financial advice.

The product is free: no billing, teams or sharing. Model calls use each user's own key.

## Status

**Scaffold.** Structure, module docstrings, route names, docs and a placeholder page.
Only `GET /health` is live. Google sign-in, uploads, extraction, the graph, the retriever
and the agent are documented stubs, not implemented yet.

## Docs

- [Product spec](docs/problem-statement.md) (authoritative)
- [Architecture](docs/architecture.md) (diagrams, settled decisions)
- [Decision records](docs/decisions/)
- [Open questions](docs/open-questions.md) (three items)
- [Rendered diagrams](docs/diagrams/)

## Repository layout

```text
backend/        Python 3.11+ / FastAPI / Pydantic, managed with uv
frontend/       Vite + React + TypeScript placeholder page
infra/          docker-compose for local dev (neo4j, postgres, backend, frontend)
data/fixtures/  test-only fixture description (never loaded into an account)
docs/           spec, architecture, ADRs, diagrams, open questions
```

## Run what exists

Requirements: [uv](https://docs.astral.sh/uv/), Node.js >= 20.19, Docker (optional).

```bash
cp .env.example .env

# backend: health route + tests
cd backend && uv sync && uv run pytest
uv run uvicorn jewel.api.app:app --reload        # http://localhost:8000/health

# frontend: placeholder page
cd frontend && npm ci && npm run dev             # http://localhost:5173

# or the placeholder stack
docker compose -f infra/docker-compose.yml --env-file .env up --build
```

`make help` lists shortcuts (`make test`, `make lint`, `make build`, `make diagrams`).
