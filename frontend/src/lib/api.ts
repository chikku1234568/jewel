/**
 * Typed API client for the jewel backend (placeholder).
 *
 * TODO(step-N): add typed calls for:
 *   - POST /episodes        (paste text or upload a document)
 *   - POST /runs            (run the three agents in order, stream 5 progress steps)
 *   - POST /ask             (graph answer + naive-RAG baseline side by side)
 *   - GET  /graph?as_of=... (time-filtered subgraph for the graph view)
 */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
