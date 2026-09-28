# jewel backend

Python 3.11+ / FastAPI / Pydantic, managed with uv. This is a scaffold: only `GET /health`
is mounted; every other module is a documented stub. See
[`../docs/architecture.md`](../docs/architecture.md) and the spec in
[`../docs/problem-statement.md`](../docs/problem-statement.md).

```bash
uv sync                      # create .venv with runtime + dev deps
uv run pytest                # tests (no network, no databases)
uv run ruff check . && uv run ruff format --check .
uv run uvicorn jewel.api.app:app --reload   # http://localhost:8000/health
```

## Package layout

| Package | Responsibility (planned) |
|---|---|
| `jewel.api` | FastAPI app; routers `health` (mounted), `auth`, `keys`, `documents`, `graph`, `ask` (stubs, not mounted) |
| `jewel.auth` | Google OAuth (authorization-code flow), server sessions, encrypted per-user xAI key |
| `jewel.db` | Postgres: users, sessions, document rows, ciphertext keys, chunk rows, ask runs |
| `jewel.documents` | Document status values, upload limits, local-volume file storage |
| `jewel.ingestion` | Fixed pipeline: parse, chunk, extract, embed, write |
| `jewel.parsing` | `DocumentParser` interface; PDF (pypdf first), `.txt`, `.md` |
| `jewel.kg` | Neo4j graph: `schema` (Document, Entity, MENTIONS, RELATED_TO), `neo4j_store` (user-scoped reads/writes), `temporal` (validity predicate), `extraction` (entities and triples) |
| `jewel.retrieval` | `hippo/` graph retriever behind `search_graph`; `baseline_rag` text-search comparison |
| `jewel.agents` | One LangGraph tool-using agent: `graph`, `state`, `tools` (`search_graph`, `read_document`) |
| `jewel.llm` | Model interfaces for one OpenAI-compatible client at `https://api.x.ai/v1` |
| `jewel.config` | Settings from the environment |
