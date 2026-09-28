import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import {
  ACCEPTED_FILE_TYPES,
  deleteDocument,
  getDocument,
  listDocuments,
  uploadDocument,
  type DocumentDetail,
  type DocumentSummary,
} from '../lib/api'

const STATUS_LABELS: Record<DocumentSummary['status'], string> = {
  stored: 'Stored',
  parsing: 'Reading',
  parsed: 'Parsed',
  failed: 'Failed',
  extracting: 'Building graph',
  ready: 'Ready',
}

function formatTime(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString()
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong.'
}

/** The signed-in user's library: upload, list with status, open extracted text, delete. */
export function DocumentLibrary() {
  const [documents, setDocuments] = useState<DocumentSummary[] | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [opened, setOpened] = useState<DocumentDetail | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const refresh = useCallback(async () => {
    try {
      setDocuments(await listDocuments())
    } catch (err) {
      setError(message(err))
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    listDocuments()
      .then((rows) => {
        if (!cancelled) setDocuments(rows)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(message(err))
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function onUpload(event: FormEvent) {
    event.preventDefault()
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      await uploadDocument(file)
      setFile(null)
      if (inputRef.current) inputRef.current.value = ''
    } catch (err) {
      setError(message(err))
    } finally {
      setUploading(false)
      await refresh()
    }
  }

  async function onOpen(id: string) {
    setError(null)
    try {
      setOpened(await getDocument(id))
    } catch (err) {
      setError(message(err))
    }
  }

  async function onDelete(doc: DocumentSummary) {
    if (!window.confirm(`Delete ${doc.filename}?`)) return
    setError(null)
    try {
      await deleteDocument(doc.id)
      if (opened?.id === doc.id) setOpened(null)
    } catch (err) {
      setError(message(err))
    } finally {
      await refresh()
    }
  }

  return (
    <div>
      <form className="upload" onSubmit={onUpload}>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_FILE_TYPES}
          aria-label="Choose a file"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <button type="submit" disabled={!file || uploading}>
          {uploading ? 'Uploading…' : 'Upload'}
        </button>
      </form>
      <p className="hint">PDF (up to 50 pages), text, Markdown or Word (.docx), up to 20 MB.</p>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}

      {documents === null ? (
        <p className="hint">Loading your library…</p>
      ) : documents.length === 0 ? (
        <p className="empty">
          Your library is empty. Upload a PDF, text, Markdown or Word file to get started.
        </p>
      ) : (
        <table className="library">
          <thead>
            <tr>
              <th scope="col">File</th>
              <th scope="col">Uploaded</th>
              <th scope="col">Status</th>
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr key={doc.id}>
                <td>{doc.filename}</td>
                <td>{formatTime(doc.uploaded_at)}</td>
                <td>
                  <span className={`status status-${doc.status}`}>
                    {STATUS_LABELS[doc.status] ?? doc.status}
                  </span>
                  {doc.status === 'failed' && doc.error ? (
                    <div className="error">{doc.error}</div>
                  ) : null}
                </td>
                <td className="actions">
                  <button type="button" onClick={() => void onOpen(doc.id)}>
                    Open
                  </button>
                  <button type="button" onClick={() => void onDelete(doc)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {opened ? (
        <article className="viewer" aria-labelledby="viewer-title">
          <div className="viewer-header">
            <h3 id="viewer-title">{opened.filename}</h3>
            <button type="button" onClick={() => setOpened(null)}>
              Close
            </button>
          </div>
          {opened.extracted_text ? (
            <pre className="extracted">{opened.extracted_text}</pre>
          ) : (
            <p className="empty">{opened.error ?? 'No text was extracted from this file.'}</p>
          )}
        </article>
      ) : null}
    </div>
  )
}
