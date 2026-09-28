/**
 * Typed API client for the jewel backend.
 *
 * Every call sends the session cookie (`credentials: 'include'`), because the Vite dev
 * server (localhost:5173) and the API (localhost:8000) are different origins. The API
 * allows exactly the frontend origin with credentials.
 *
 * Mounted today: GET /auth/google (a browser navigation, not a fetch), POST /auth/logout,
 * GET /me, and POST / GET /documents, GET / DELETE /documents/{id}. Graph and Ask
 * belong to a later pass.
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
  | 'extracting'
  | 'ready'

export interface DocumentSummary {
  id: string
  filename: string
  uploaded_at: string
  status: DocumentStatus
  error: string | null
}

export interface DocumentDetail extends DocumentSummary {
  media_type: string
  document_date: string | null
  extracted_text: string | null
}

/** File types the API accepts, for the file picker. */
export const ACCEPTED_FILE_TYPES = '.pdf,.txt,.md,.docx'

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

export async function deleteDocument(id: string): Promise<void> {
  await request(`/documents/${encodeURIComponent(id)}`, { method: 'DELETE' })
}
