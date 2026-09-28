import { useEffect, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  askQuestion,
  getGraph,
  type AgentChoice,
  type AskResult,
  type EmbeddingChoice,
  type GraphView,
} from '../lib/api'

function message(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong.'
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`
}

/** The signed-in user's entities and the sentences that connect them. */
export function GraphPanel({ refreshKey }: { refreshKey: number }) {
  const [graph, setGraph] = useState<GraphView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    let cancelled = false
    getGraph()
      .then((value) => {
        if (cancelled) return
        setGraph(value)
        setError(null)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(message(err))
      })
    return () => {
      cancelled = true
    }
  }, [refreshKey])

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
  if (graph.entities.length === 0) {
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

  const names = new Map(graph.entities.map((entity) => [entity.id, entity.name]))
  const files = new Map(graph.documents.map((doc) => [doc.id, doc.filename]))
  const entity = graph.entities.find((item) => item.id === selected) ?? null
  const source =
    graph.triples.find(
      (triple) => triple.source_id === selected || triple.target_id === selected,
    ) ?? null
  const quote = source?.quote ?? null
  const needle = filter.trim().toLowerCase()
  const shown = needle
    ? graph.entities.filter((item) => item.name.toLowerCase().includes(needle))
    : graph.entities
  const triples = entity
    ? graph.triples.filter(
        (triple) => triple.source_id === entity.id || triple.target_id === entity.id,
      )
    : graph.triples

  return (
    <div className="graph">
      <p className="graph-meta hint">
        {plural(graph.entities.length, 'name', 'names')} ·{' '}
        {plural(graph.triples.length, 'statement', 'statements')} ·{' '}
        {plural(graph.documents.length, 'file', 'files')}
      </p>
      <div className="graph-grid">
        <div className="graph-names">
          <label className="field">
            <span className="visually-hidden">Filter names</span>
            <input
              type="search"
              placeholder="Filter names"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            />
          </label>
          {shown.length === 0 ? (
            <p className="hint">No name matches “{filter}”.</p>
          ) : (
            <ul className="nodes">
              {shown.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className={selected === item.id ? 'node selected' : 'node'}
                    aria-pressed={selected === item.id}
                    onClick={() => setSelected(item.id)}
                  >
                    {item.name}
                    <span className="node-type"> {item.type}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="graph-detail" aria-live="polite">
          {entity ? (
            <div className="entity">
              <p className="eyebrow">{entity.type}</p>
              <h2 className="entity-name">{entity.name}</h2>
              {quote ? (
                <blockquote className="quote">
                  <p>{quote}</p>
                  {source && files.get(source.document_id) ? (
                    <footer>{files.get(source.document_id)}</footer>
                  ) : null}
                </blockquote>
              ) : null}
            </div>
          ) : (
            <p className="hint entity-placeholder">
              Choose a name to see the sentence it comes from.
            </p>
          )}

          <div className="block-head">
            <h3 className="block-title">
              {entity ? `Statements about ${entity.name}` : 'All statements'}
            </h3>
            {entity ? (
              <button
                type="button"
                className="button button-small button-quiet"
                onClick={() => setSelected(null)}
              >
                Show all
              </button>
            ) : null}
          </div>
          <ul className="triples">
            {triples.map((triple) => (
              <li key={triple.id}>
                <span className="triple-end">
                  {names.get(triple.source_id) ?? triple.source_id}
                </span>{' '}
                <span className="triple-predicate">{triple.predicate}</span>{' '}
                <span className="triple-end">
                  {names.get(triple.target_id) ?? triple.target_id}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
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
