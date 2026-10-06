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

Diagrams 01–05 are the older scaffold. The running system is the hand-written set below. Each of those files starts with `%% keep: hand`, so `make diagrams` does not delete them.

| Diagram | Source |
|---|---|
| One Ask on the VM | [06-ask-on-the-vm.mmd](06-ask-on-the-vm.mmd) |
| Laptop, CI, and deploy | [07-dev-and-production.mmd](07-dev-and-production.mmd) |
| Why a Vercel-only deploy fails | [08-vercel-only-fails.mmd](08-vercel-only-fails.mmd) |
| Production runtime | [09-production-runtime.mmd](09-production-runtime.mmd) |
| Sign-in, upload, build, and Ask | [10-request-paths.mmd](10-request-paths.mmd) |
| Concurrency and limits | [11-concurrency.mmd](11-concurrency.mmd) |

`puppeteer.json` passes `--no-sandbox` for rendering inside containers.
