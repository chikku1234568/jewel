/**
 * Typed API client for the jewel backend.
 *
 * Every call sends the session cookie (`credentials: 'include'`), because the Vite dev
 * server (localhost:5173) and the API (localhost:8000) are different origins. The API
 * allows exactly the frontend origin with credentials.
 *
 * Mounted today: GET /auth/google (a browser navigation, not a fetch), POST /auth/logout,
 * GET /me, POST / GET /documents, GET / DELETE /documents/{id}, the build and stop
 * routes under /documents/{id}, GET /graph, DELETE /graph/relations, and POST /ask.
 */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

/** Where the "Sign in with Google" link points. The API redirects back here afterwards. */
export const SIGN_IN_URL = `${API_BASE_URL}/auth/google`

export interface Me {
  email: string
  name: string | null
}

export type DocumentStatus =
  | 'stored'
  | 'parsing'
  | 'parsed'
  | 'failed'
  | 'waiting'
  | 'extracting'
  | 'ready'

export interface DocumentSummary {
  id: string
  filename: string
  uploaded_at: string
  status: DocumentStatus
  error: string | null
  /** Passages of the running build that are done, and how many there are. */
  build_done?: number
  build_total?: number
  /** Triples written to the graph by this file's last finished build. */
  triples_kept?: number
}

export interface DocumentDetail extends DocumentSummary {
  media_type: string
  document_date: string | null
  extracted_text: string | null
}

/** File types the API accepts, for the file picker. */
export const ACCEPTED_FILE_TYPES = '.pdf,.docx,.pptx,.xlsx,.html,.htm,.txt,.md'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: 'include',
  })
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  return response
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail
      if (typeof detail === 'string') return detail
    }
  } catch {
    // Not JSON; fall through to the status text.
  }
  return response.statusText || `Request failed (${response.status})`
}

/** The signed-in user, or null when there is no valid session. */
export async function getMe(): Promise<Me | null> {
  try {
    const response = await request('/me')
    return (await response.json()) as Me
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}

export async function logout(): Promise<void> {
  await request('/auth/logout', { method: 'POST' })
}

export async function listDocuments(): Promise<DocumentSummary[]> {
  const response = await request('/documents')
  return (await response.json()) as DocumentSummary[]
}

export async function uploadDocument(file: File): Promise<DocumentSummary> {
  const form = new FormData()
  form.append('file', file)
  const response = await request('/documents', { method: 'POST', body: form })
  return (await response.json()) as DocumentSummary
}

export async function getDocument(id: string): Promise<DocumentDetail> {
  const response = await request(`/documents/${encodeURIComponent(id)}`)
  return (await response.json()) as DocumentDetail
}

export async function stopBuild(id: string): Promise<DocumentSummary> {
  const response = await request(`/documents/${encodeURIComponent(id)}/stop`, {
    method: 'POST',
  })
  return (await response.json()) as DocumentSummary
}

export async function deleteDocument(id: string): Promise<void> {
  await request(`/documents/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

/** Delete every file and the knowledge graph for the signed-in account. */
export async function deleteLibrary(): Promise<void> {
  await request('/documents', { method: 'DELETE' })
}

export interface EmbeddingChoice {
  provider: 'api'
  model: string
  base_url: string
  api_key: string
}

export interface ExtractionChoice {
  provider: 'api'
  model: string
  base_url: string
  api_key: string
}

export interface AgentChoice {
  model: string
  base_url: string
  api_key: string
}

export const AGENT_MODELS = [
  { id: 'kimi-k2.6', label: 'Kimi kimi-k2.6', base_url: 'https://api.moonshot.ai/v1' },
  { id: 'kimi-k3', label: 'Kimi kimi-k3', base_url: 'https://api.moonshot.ai/v1' },
  { id: 'gpt-4o-mini', label: 'OpenAI gpt-4o-mini', base_url: 'https://api.openai.com/v1' },
]

export const API_EMBEDDINGS = [
  { id: 'text-embedding-3-small', label: 'OpenAI text-embedding-3-small' },
  { id: 'text-embedding-3-large', label: 'OpenAI text-embedding-3-large' },
]

export const API_EXTRACTION = [
  { id: 'gpt-4o-mini', label: 'OpenAI gpt-4o-mini', base_url: 'https://api.openai.com/v1' },
  { id: 'kimi-k2.6', label: 'Kimi kimi-k2.6', base_url: 'https://api.moonshot.ai/v1' },
]

export async function buildDocument(
  id: string,
  embedding: EmbeddingChoice,
  extraction: ExtractionChoice,
): Promise<DocumentSummary> {
  const response = await request(`/documents/${encodeURIComponent(id)}/build`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...embedding, extraction }),
  })
  return (await response.json()) as DocumentSummary
}

export interface GraphEntity {
  id: string
  name: string
  type: string
}

export interface GraphTriple {
  id: string
  source_id: string
  target_id: string
  predicate: string
  quote: string
  document_id: string
}

export interface GraphView {
  documents: { id: string; filename: string }[]
  entities: GraphEntity[]
  triples: GraphTriple[]
}

export async function getGraph(): Promise<GraphView> {
  const response = await request('/graph')
  return (await response.json()) as GraphView
}

/** Remove existing entity-to-entity relations. Unknown ids are skipped. */
export async function deleteRelations(ids: string[]): Promise<{ deleted: number }> {
  const response = await request('/graph/relations', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids }),
  })
  return (await response.json()) as { deleted: number }
}

export interface AskResult {
  answer: string
  tool_calls_used: number
  trace: { name: string; summary: string }[]
  highlight_entity_ids: string[]
  highlight_relationship_ids: string[]
}

export async function askQuestion(
  question: string,
  embedding: EmbeddingChoice,
  agent: AgentChoice,
): Promise<AskResult> {
  const response = await request('/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, ...embedding, agent }),
  })
  return (await response.json()) as AskResult
}
