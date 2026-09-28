/**
 * Typed API client for the jewel backend (placeholder).
 *
 * Only GET /health exists on the server today. Planned calls (all session-cookie based):
 *   - GET  /auth/google, POST /auth/logout, GET /me
 *   - PUT / DELETE /me/api-key, POST /me/api-key/check
 *   - POST /documents, GET /documents, GET /documents/{id},
 *     POST /documents/{id}/build, DELETE /documents/{id}
 *   - GET /graph?document_id=..., DELETE /graph/entities/{id},
 *     DELETE /graph/relationships/{id}
 *   - POST /ask, GET /ask/{run_id}/events (Server-Sent Events), POST /ask/{run_id}/compare
 */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
