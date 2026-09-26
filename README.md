# jewel

**Pharmacotherapy regimen lab alert**: a showcase in which pasted notes and uploaded
documents become episodes in a **temporal knowledge graph**, three **role-restricted
agents** update it, and a question about drug administration is answered from
relationships that are **valid now**, not from a text search.

> [!WARNING]
> **Not for clinical use.** This is a technical showcase on a private URL. It is not a
> medical device and not clinical advice. The patient is synthetic. Never add real
> patient data to this repository.

## Status

**Step 1: repository structure + architecture proposal.** Nothing is implemented beyond a
FastAPI `/health` route, a placeholder frontend page with the not-for-clinical-use banner,
and documented module stubs. The architecture is up for review.

| Decision | Status |
|---|---|
| Graph store: Neo4j 5.x Community | Accepted |
| Cache: Redis | Accepted |
| Retrieval: HippoRAG-2-inspired temporal PPR | Proposed (pending user input) |
| LangGraph orchestration | Proposed, for review |
| Frontend (Vite + React + TS), deployment | Proposed |

## The scenario in brief

An enoxaparin 100 mg twice-daily order is signed. A later lab shows creatinine clearance
below 30 mL/min but never names the drug. A frozen protocol rule closes the
`PRESCRIBED_DOSE` relationship by setting `invalid_at` to the specimen time. Asked *"Is the
current order for enoxaparin 100 mg twice daily valid for immediate administration?"*, the
graph answers **no**; a naive RAG over the same notes says the order is fine.

## Docs

- [Problem statement](docs/problem-statement.md) (verbatim spec)
- [Architecture proposal](docs/architecture.md) (diagrams, LangGraph design, schema, retrieval)
- [Decision records](docs/decisions/)
- [Open questions](docs/open-questions.md)
- [Rendered diagrams](docs/diagrams/)

## Repository layout

```text
backend/    Python 3.11+ / FastAPI / (planned) LangGraph, managed with uv
frontend/   Vite + React + TypeScript
infra/      docker-compose for local dev (neo4j, redis, backend, frontend)
data/demo/  the three synthetic demo episodes (not locked yet)
docs/       problem statement, architecture, ADRs, diagrams, open questions
```

## Quickstart (placeholder)

Requirements: [uv](https://docs.astral.sh/uv/), Node.js >= 20.19, Docker (optional).

```bash
cp .env.example .env

# backend
cd backend && uv sync && uv run pytest
uv run uvicorn jewel.api.app:app --reload        # http://localhost:8000/health

# frontend
cd frontend && npm ci && npm run dev             # http://localhost:5173

# or the whole stack (placeholder services)
docker compose -f infra/docker-compose.yml --env-file .env up --build
```

`make help` lists shortcuts (`make test`, `make lint`, `make build`, `make diagrams`).
