# Architecture Decision Records

Lightweight ADRs (Michael Nygard format). Status is **Proposed**, **Accepted**, or
**Superseded**. Superseded records are kept for history and are not part of the active set.

## Active

| ADR | Title | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0005](0005-frontend-framework.md) | Frontend: Vite + React + TypeScript, Cytoscape.js | Accepted |
| [0006](0006-deployment.md) | Deployment (hosting open) | Proposed |
| [0008](0008-google-oauth-sessions.md) | Google OAuth sign-in with server-side sessions | Accepted |
| [0009](0009-postgres-app-data.md) | Postgres for application data | Accepted |
| [0010](0010-redis-dropped-this-version.md) | Redis dropped for this version | Accepted |
| [0011](0011-neo4j-per-user-graph.md) | Graph store: Neo4j 5.x Community, per-user Document/Entity graph | Accepted |
| [0012](0012-retrieval-graph-ppr.md) | Retrieval: HippoRAG-2-inspired time-aware PPR in networkx | Accepted |
| [0013](0013-single-langgraph-agent.md) | One LangGraph tool-using agent | Accepted |
| [0014](0014-user-xai-key.md) | User-supplied xAI key through one OpenAI-compatible client | Accepted |

## Superseded (history only)

| ADR | Superseded by |
|---|---|
| [0002](0002-graph-store-neo4j.md) | [0011](0011-neo4j-per-user-graph.md) |
| [0003](0003-cache-redis.md) | [0010](0010-redis-dropped-this-version.md) |
| [0004](0004-retrieval-approach.md) | [0012](0012-retrieval-graph-ppr.md) |
| [0007](0007-langgraph-orchestration.md) | [0013](0013-single-langgraph-agent.md) |
