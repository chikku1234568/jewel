# Diagrams

Mermaid sources (`*.mmd`) are extracted from [`../architecture.md`](../architecture.md),
which is the source of truth; PNGs are rendered with
[mermaid-cli](https://github.com/mermaid-js/mermaid-cli) (`make diagrams`).

| Diagram | Source | PNG |
|---|---|---|
| System overview | [01-system-overview.mmd](01-system-overview.mmd) | [PNG](01-system-overview.png) |
| Ingestion-to-answer sequence (5 progress steps) | [02-ingestion-to-answer-sequence.mmd](02-ingestion-to-answer-sequence.mmd) | [PNG](02-ingestion-to-answer-sequence.png) |
| LangGraph graph | [03-langgraph-graph.mmd](03-langgraph-graph.mmd) | [PNG](03-langgraph-graph.png) |
| Temporal KG schema (Neo4j) | [04-temporal-kg-schema.mmd](04-temporal-kg-schema.mmd) | [PNG](04-temporal-kg-schema.png) |
| Retrieval pipeline | [05-retrieval-pipeline.mmd](05-retrieval-pipeline.mmd) | [PNG](05-retrieval-pipeline.png) |

`puppeteer.json` passes `--no-sandbox` for rendering inside containers.
