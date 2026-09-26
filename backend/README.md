# jewel backend

Python 3.11+ / FastAPI / (planned) LangGraph. Step 1 contains only a `/health` route and
documented stubs; see [`../docs/architecture.md`](../docs/architecture.md).

```bash
uv sync                      # create .venv with runtime + dev deps
uv run pytest                # tests
uv run ruff check . && uv run ruff format --check .
uv run uvicorn jewel.api.app:app --reload   # http://localhost:8000/health
```

## Package layout

| Package | Responsibility (planned) |
|---|---|
| `jewel.api` | FastAPI app and routers (only `/health` exists today) |
| `jewel.config` | Settings from environment (`.env`) |
| `jewel.ingestion` | Turn a paste or an upload into an `Episode` (author, authored_at, raw text) |
| `jewel.parsing` | `DocumentParser` interface and PDF/text implementations |
| `jewel.kg` | Temporal KG: `schema` (node/edge kinds), `neo4j_store` (Neo4j), `temporal` (valid-at filters), `permissions` (per-agent write guard), `extraction` (LLM triple extraction) |
| `jewel.agents` | LangGraph nodes (`parse`, `ehr_order`, `lab_monitor`, `pharmacologist`, `answer`), shared `state`, `progress` steps, and the wiring in `graph.py` |
| `jewel.rules` | Frozen protocol rules (deterministic code, never LLM-decided) |
| `jewel.retrieval` | `hippo` (HippoRAG-2-inspired temporal PPR retrieval) and `baseline_rag` (naive RAG for the side-by-side proof) |
| `jewel.llm` | Provider-agnostic chat + embedding interfaces |
| `jewel.cache` | Cache interface (Redis) |
