# 0005. Frontend: Vite + React + TypeScript, Cytoscape.js for the graph

- **Status:** Accepted (settled by `docs/problem-statement.md`, 2026-09-28; previously Proposed)

## Context

TypeScript is required. After sign-in the interface is one page with three regions
(Documents, Graph, Ask) plus Key and Account, a Server-Sent Events trace, and a clickable
graph that the agent can highlight. No server rendering or SEO is needed.

## Decision

Keep the existing **Vite + React + TypeScript** single-page app in `frontend/`. The graph
view uses **Cytoscape.js** (pan/zoom, labelled nodes, predicate-labelled edges, click
details, highlight, delete). Cytoscape.js is added in the pass that implements the graph;
the scaffold page shows an empty Graph region.

## Consequences

- Static build (`vite build`) deploys to any static host; API URL via `VITE_API_BASE_URL`.
- Session cookies are `httpOnly`, so the frontend never handles tokens or keys.

## Open questions for review

None; hosting is tracked in [0006](0006-deployment.md).
