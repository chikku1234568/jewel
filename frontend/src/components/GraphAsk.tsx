import {
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from 'react'
import { Link } from 'react-router-dom'
import {
  askQuestion,
  deleteRelations,
  getGraph,
  type AgentChoice,
  type AskResult,
  type EmbeddingChoice,
  type GraphView,
} from '../lib/api'
import {
  documentNodeId,
  drawingFor,
  tripleCounts,
  type FileDrawing,
} from '../lib/graphElements'
import { GraphCanvas, type GraphPick } from './GraphCanvas'

function message(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong.'
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`
}

/** The file the selector opens on: the first one with something to draw. */
function defaultDocument(graph: GraphView): string | null {
  const counts = tripleCounts(graph)
  const withTriples = graph.documents.find((doc) => (counts.get(doc.id) ?? 0) > 0)
  return (withTriples ?? graph.documents[0])?.id ?? null
}

/**
 * The signed-in user's graph, one file at a time, drawn with Cytoscape.js. A click shows
 * the quote, predicate and filename. This is a picture of `GET /graph`; it is not the
 * PageRank walk and never calls Ask.
 */
export function GraphPanel({ refreshKey }: { refreshKey: number }) {
  const [graph, setGraph] = useState<GraphView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [focusId, setFocusId] = useState<string | null>(null)
  const [pick, setPick] = useState<GraphPick>(null)
  const [deleting, setDeleting] = useState(false)
  const [chosen, setChosen] = useState<Set<string>>(() => new Set())
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getGraph()
      .then((value) => {
        if (cancelled) return
        setGraph(value)
        setError(null)
        // Keep the chosen file across refreshes unless it is gone (deleted or rebuilt away).
        setDocumentId((current) =>
          current && value.documents.some((doc) => doc.id === current)
            ? current
            : defaultDocument(value),
        )
        setFocusId((current) =>
          current && value.entities.some((entity) => entity.id === current) ? current : null,
        )
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(message(err))
      })
    return () => {
      cancelled = true
    }
  }, [refreshKey])

  useEffect(() => {
    if (!deleting) return
    function onKey(event: globalThis.KeyboardEvent) {
      if (event.key !== 'Escape') return
      setDeleting(false)
      setChosen(new Set())
      setDeleteError(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [deleting])

  const drawing = useMemo(
    () => (graph && documentId ? drawingFor(graph, documentId, focusId) : null),
    [graph, documentId, focusId],
  )
  const selectedIds = useMemo(() => {
    if (!drawing) return []
    const live = new Set(drawing.triples.map((triple) => triple.id))
    return [...chosen].filter((id) => live.has(id))
  }, [drawing, chosen])
  const counts = useMemo(() => (graph ? tripleCounts(graph) : new Map<string, number>()), [graph])

  if (error) {
    return (
      <p className="error" role="alert">
        {error}
      </p>
    )
  }
  if (!graph) {
    return <p className="hint">Loading your graph…</p>
  }
  if (graph.documents.length === 0 || !drawing) {
    return (
      <div className="empty-block">
        <p className="empty">
          Build a document and the people, places, and ideas in it show up here.
        </p>
        <Link className="button" to="/app">
          Go to Documents
        </Link>
      </div>
    )
  }

  const names = new Map(graph.entities.map((entity) => [entity.id, entity]))
  const nameOf = (id: string) => names.get(id)?.name ?? id
  const focus = focusId ? (names.get(focusId) ?? null) : null
  const pickedTriple = pick?.kind === 'triple' ? pick.id : null
  const selectedId =
    pick?.kind === 'document' ? documentNodeId(drawing.documentId) : (pick?.id ?? null)

  function keepChoicesFor(nextFocus: string | null) {
    if (!graph || !documentId) return
    const live = new Set(
      drawingFor(graph, documentId, nextFocus).triples.map((triple) => triple.id),
    )
    setChosen((current) => {
      const next = new Set([...current].filter((id) => live.has(id)))
      return next.size === current.size ? current : next
    })
  }

  function onPick(next: GraphPick) {
    setPick(next)
    // Clicking an entity limits the drawing to that entity's edges.
    if (next?.kind === 'entity') {
      setFocusId(next.id)
      keepChoicesFor(next.id)
    }
  }

  function chooseFile(id: string) {
    setDocumentId(id)
    setFocusId(null)
    setPick(null)
    setDeleting(false)
    setChosen(new Set())
    setDeleteError(null)
  }

  function leaveDeleteMode() {
    setDeleting(false)
    setChosen(new Set())
    setDeleteError(null)
  }

  function toggleChosen(id: string) {
    setChosen((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function confirmDelete() {
    if (selectedIds.length === 0 || deleteBusy) return
    const ids = selectedIds
    setDeleteBusy(true)
    setDeleteError(null)
    try {
      await deleteRelations(ids)
      const value = await getGraph()
      const removed = new Set(ids)
      setGraph(value)
      setPick((current) =>
        current?.kind === 'triple' && removed.has(current.id) ? null : current,
      )
      setFocusId((current) => {
        if (!current || !documentId) return current
        const still = value.triples.some(
          (triple) =>
            triple.document_id === documentId &&
            (triple.source_id === current || triple.target_id === current),
        )
        return still ? current : null
      })
      setChosen(new Set())
      setDeleting(false)
    } catch (err) {
      setDeleteError(message(err))
    } finally {
      setDeleteBusy(false)
    }
  }

  return (
    <div className="graph">
      <div className="graph-toolbar">
        <label className="field graph-file">
          <span className="field-label">File</span>
          <select value={drawing.documentId} onChange={(event) => chooseFile(event.target.value)}>
            {graph.documents.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.filename} ({plural(counts.get(doc.id) ?? 0, 'statement', 'statements')})
              </option>
            ))}
          </select>
        </label>
        {focus ? (
          <div className="graph-focus">
            <span className="hint small">
              Showing the edges of <strong>{focus.name}</strong>
            </span>
            <button
              type="button"
              className="button button-small button-quiet"
              onClick={() => {
                setFocusId(null)
                setPick(null)
                keepChoicesFor(null)
              }}
            >
              Show whole file
            </button>
          </div>
        ) : null}
      </div>
      <p className="graph-meta hint">
        {plural(drawing.entities.length, 'name', 'names')} ·{' '}
        {plural(drawing.triples.length, 'statement', 'statements')} in this view. Drag a name to
        move it. Scroll to zoom. The names stay where you leave them.
      </p>

      {drawing.triples.length === 0 ? (
        <p className="empty">No statements were kept from this file.</p>
      ) : (
        <div className="graph-grid">
          <GraphCanvas drawing={drawing} selectedId={selectedId} onPick={onPick} />
          <div className="graph-detail">
            <div aria-live="polite">
              <PickDetail
                pick={pick}
                drawing={drawing}
                nameOf={nameOf}
                entityType={(id) => names.get(id)?.type ?? ''}
              />
            </div>
            <div className="statements-head">
              <h3 className="block-title">Statements in this view</h3>
              {deleting ? (
                <div className="delete-actions">
                  <button
                    type="button"
                    className="button button-small button-quiet"
                    onClick={leaveDeleteMode}
                    disabled={deleteBusy}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="button button-small button-danger"
                    onClick={() => void confirmDelete()}
                    disabled={deleteBusy || selectedIds.length === 0}
                  >
                    {deleteBusy
                      ? 'Deleting…'
                      : selectedIds.length === 0
                        ? 'Delete selected'
                        : `Delete ${selectedIds.length} selected`}
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  className="button button-small"
                  onClick={() => setDeleting(true)}
                >
                  Delete a relation(s)
                </button>
              )}
            </div>
            {deleting ? (
              <p className="hint small delete-note">
                Tick the statements to remove. Building this file again puts the extracted
                statements back.
              </p>
            ) : null}
            {deleteError ? (
              <p className="error" role="alert">
                {deleteError}
              </p>
            ) : null}
            <ul className="triples">
              {drawing.triples.map((triple) => {
                const label = `${nameOf(triple.source_id)} ${triple.predicate} ${nameOf(triple.target_id)}`
                return (
                  <li key={triple.id}>
                    {deleting ? (
                      <label className="triple-check">
                        <input
                          type="checkbox"
                          checked={chosen.has(triple.id)}
                          disabled={deleteBusy}
                          aria-label={`Select ${label}`}
                          onChange={() => toggleChosen(triple.id)}
                        />
                      </label>
                    ) : null}
                    <button
                      type="button"
                      className={
                        pickedTriple === triple.id ? 'triple-button selected' : 'triple-button'
                      }
                      aria-pressed={pickedTriple === triple.id}
                      onClick={() => setPick({ kind: 'triple', id: triple.id })}
                    >
                      <span className="triple-end">{nameOf(triple.source_id)}</span>{' '}
                      <span className="triple-predicate">{triple.predicate}</span>{' '}
                      <span className="triple-end">{nameOf(triple.target_id)}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}

/** The quote, predicate and filename behind whatever was clicked. */
function PickDetail({
  pick,
  drawing,
  nameOf,
  entityType,
}: {
  pick: GraphPick
  drawing: FileDrawing
  nameOf: (id: string) => string
  entityType: (id: string) => string
}) {
  if (pick?.kind === 'triple') {
    const triple = drawing.triples.find((item) => item.id === pick.id)
    if (triple) {
      return (
        <div className="entity">
          <p className="eyebrow">Statement</p>
          <h2 className="entity-name">
            {nameOf(triple.source_id)}{' '}
            <span className="triple-predicate">{triple.predicate}</span>{' '}
            {nameOf(triple.target_id)}
          </h2>
          <Quote text={triple.quote} filename={drawing.filename} />
        </div>
      )
    }
  }
  if (pick?.kind === 'entity') {
    const own = drawing.triples.filter(
      (triple) => triple.source_id === pick.id || triple.target_id === pick.id,
    )
    return (
      <div className="entity">
        <p className="eyebrow">{entityType(pick.id)}</p>
        <h2 className="entity-name">{nameOf(pick.id)}</h2>
        {own.map((triple) => (
          <div key={triple.id} className="pick-statement">
            <p className="hint small">
              {nameOf(triple.source_id)}{' '}
              <span className="triple-predicate">{triple.predicate}</span>{' '}
              {nameOf(triple.target_id)}
            </p>
            <Quote text={triple.quote} filename={drawing.filename} />
          </div>
        ))}
      </div>
    )
  }
  if (pick?.kind === 'document') {
    return (
      <div className="entity">
        <p className="eyebrow">File</p>
        <h2 className="entity-name">{drawing.filename}</h2>
        <p className="hint">
          {plural(drawing.triples.length, 'statement', 'statements')} about{' '}
          {plural(drawing.entities.length, 'name', 'names')} in this view.
        </p>
      </div>
    )
  }
  return (
    <p className="hint entity-placeholder">
      Click a name or a line to read the sentence it comes from.
    </p>
  )
}

function Quote({ text, filename }: { text: string; filename: string }) {
  return (
    <blockquote className="quote">
      <p>{text}</p>
      <footer>{filename}</footer>
    </blockquote>
  )
}

/** Ask the graph. Shows the tool trace and the answer. */
export function AskPanel({
  embedding,
  agent,
  onAsked,
}: {
  embedding: EmbeddingChoice
  agent: AgentChoice
  onAsked?: (highlights: string[]) => void
}) {
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<AskResult | null>(null)

  async function onSubmit(event?: FormEvent) {
    event?.preventDefault()
    if (!question.trim() || asking) return
    setAsking(true)
    setError(null)
    try {
      const answer = await askQuestion(question.trim(), embedding, agent)
      setResult(answer)
      onAsked?.(answer.highlight_entity_ids)
    } catch (err) {
      setError(message(err))
    } finally {
      setAsking(false)
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault()
      void onSubmit()
    }
  }

  return (
    <div className="ask">
      <form className="ask-form" onSubmit={(event) => void onSubmit(event)}>
        <label className="field-label" htmlFor="ask-question">
          Question
        </label>
        <textarea
          id="ask-question"
          placeholder="Ask a question about your documents"
          rows={4}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={onKeyDown}
        />
        <div className="ask-actions">
          <span className="hint small">Ctrl or ⌘ + Enter also asks.</span>
          <button
            type="submit"
            className="button button-primary"
            disabled={asking || !question.trim()}
          >
            {asking ? 'Searching…' : 'Ask'}
          </button>
        </div>
      </form>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      {result ? (
        <div className="ask-result" aria-live="polite">
          <section aria-labelledby="ask-steps-title">
            <h2 id="ask-steps-title" className="block-title">
              Steps
            </h2>
            {result.trace.length === 0 ? (
              <p className="hint">The agent answered without a search step.</p>
            ) : (
              <ol className="trace">
                {result.trace.map((entry, index) => (
                  <li key={`${entry.name}-${index}`}>
                    <strong>
                      {entry.name === 'search_graph' ? 'Search graph' : 'Read document'}
                    </strong>
                    <div className="hint">{entry.summary}</div>
                  </li>
                ))}
              </ol>
            )}
          </section>
          <section aria-labelledby="ask-answer-title">
            <h2 id="ask-answer-title" className="block-title">
              Answer
            </h2>
            <div className="answer">{result.answer}</div>
          </section>
        </div>
      ) : asking ? (
        <p className="hint" role="status">
          Searching your graph…
        </p>
      ) : (
        <p className="hint">The search steps and the answer show up here.</p>
      )}
    </div>
  )
}
