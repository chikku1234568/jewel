import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import {
  ACCEPTED_FILE_TYPES,
  buildDocument,
  deleteDocument,
  stopBuild,
  getDocument,
  listDocuments,
  uploadDocument,
  type DocumentDetail,
  type DocumentSummary,
  type EmbeddingChoice,
  type ExtractionChoice,
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
export function DocumentLibrary({
  embedding,
  extraction,
  onBuilt,
}: {
  embedding: EmbeddingChoice
  extraction: ExtractionChoice
  onBuilt?: () => void
}) {
  const [documents, setDocuments] = useState<DocumentSummary[] | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [buildingId, setBuildingId] = useState<string | null>(null)
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

  const onBuiltRef = useRef(onBuilt)
  onBuiltRef.current = onBuilt
  const building = documents?.some((doc) => doc.status === 'extracting') ?? false
  useEffect(() => {
    if (!building) return
    const timer = window.setInterval(() => {
      void refresh().then(() => onBuiltRef.current?.())
    }, 4000)
    return () => window.clearInterval(timer)
  }, [building, refresh])

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

  async function onBuild(doc: DocumentSummary) {
    setBuildingId(doc.id)
    setError(null)
    try {
      await buildDocument(doc.id, embedding, extraction)
      await refresh()
    } catch (err) {
      setError(message(err))
    } finally {
      setBuildingId(null)
    }
  }

  async function onStop(doc: DocumentSummary) {
    setError(null)
    try {
      await stopBuild(doc.id)
      await refresh()
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
      <p className="hint">
        Keep PDFs to about 20 pages. A longer file still uploads, but the graph build is slow
        and less reliable.
      </p>
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
      <p className="hint">PDF, text, Markdown or Word (.docx), up to 20 MB. PDFs over 50 pages are rejected.</p>

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
                  {doc.status === 'extracting' ? (
                    <div className="progress">
                      {(doc.build_total ?? 0) > 0 ? (
                        <progress value={doc.build_done ?? 0} max={doc.build_total} />
                      ) : (
                        <progress />
                      )}
                      <span className="hint">
                        {(doc.build_total ?? 0) > 0
                          ? `${doc.build_done ?? 0} / ${doc.build_total} passages`
                          : 'Building…'}
                      </span>
                    </div>
                  ) : null}
                  {doc.status === 'failed' && doc.error ? (
                    <div className="error">{doc.error}</div>
                  ) : null}
                </td>
                <td className="actions">
                  <button type="button" onClick={() => void onOpen(doc.id)}>
                    Open
                  </button>
                  {doc.status === 'extracting' ? (
                    <button type="button" onClick={() => void onStop(doc)}>
                      Stop
                    </button>
                  ) : (
                    <button
                      type="button"
                      disabled={
                        buildingId !== null ||
                        !['parsed', 'ready', 'failed'].includes(doc.status)
                      }
                      onClick={() => void onBuild(doc)}
                    >
                      {buildingId === doc.id ? 'Building…' : 'Build graph'}
                    </button>
                  )}
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
