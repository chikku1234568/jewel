# Diagrams

Mermaid sources (`*.mmd`) are extracted from [`../architecture.md`](../architecture.md),
which is the source of truth: each block starts with `%% name: <file-stem>`.
`make diagrams` runs [`extract.py`](extract.py) (which also deletes stale files) and renders
PNGs with [mermaid-cli](https://github.com/mermaid-js/mermaid-cli).

| Diagram | Source | PNG |
|---|---|---|
| System overview | [01-system-overview.mmd](01-system-overview.mmd) | [PNG](01-system-overview.png) |
| Ingestion pipeline | [02-ingestion-pipeline.mmd](02-ingestion-pipeline.mmd) | [PNG](02-ingestion-pipeline.png) |
| Document / Entity schema | [03-document-entity-schema.mmd](03-document-entity-schema.mmd) | [PNG](03-document-entity-schema.png) |
| Retriever pipeline | [04-retriever-pipeline.mmd](04-retriever-pipeline.mmd) | [PNG](04-retriever-pipeline.png) |
| Agent loop (4-call cap, SSE trace) | [05-agent-loop.mmd](05-agent-loop.mmd) | [PNG](05-agent-loop.png) |

`puppeteer.json` passes `--no-sandbox` for rendering inside containers.
