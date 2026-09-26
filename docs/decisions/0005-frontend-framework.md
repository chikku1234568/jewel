# 0005. Frontend: Vite + React + TypeScript

- **Status:** Proposed

## Context

TypeScript is required. The UI is a single page: ingest panel, five-step progress list
(SSE), chat with side-by-side answers, a graph view showing the closed edge, and a
permanent not-for-clinical-use banner. No accounts, no SEO, no server rendering needed.

## Proposed decision

**Vite + React + TypeScript** single-page app (scaffolded in `frontend/`). Graph view with
**Cytoscape.js** (mature, good for small labelled graphs, can style closed edges e.g. dashed
with an `invalid_at` label).

## Alternatives

- **Next.js:** routing, server components, easy Vercel deploy; unnecessary weight for one
  page, and the backend is already FastAPI.
- **react-force-graph** instead of Cytoscape.js: attractive force layout, less control over
  labelled, styled edges.

## Consequences

- Static build (`vite build`) deploys to any static host; API URL via `VITE_API_BASE_URL`.

## Open questions for review

1. Vite SPA acceptable, or prefer Next.js?
2. Cytoscape.js or react-force-graph for the graph view?
3. Any UI kit preference (none, Tailwind, shadcn/ui, MUI)?
