import { useEffect, useState, type FormEvent } from 'react'
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

/** The signed-in user's entities and the sentences that connect them. */
export function GraphPanel({ refreshKey }: { refreshKey: number }) {
  const [graph, setGraph] = useState<GraphView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getGraph()
      .then((value) => {
        if (!cancelled) setGraph(value)
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
  if (!graph || graph.entities.length === 0) {
    return (
      <p className="empty">
        Build a document and the people, places, and ideas in it show up here.
      </p>
    )
  }
  const names = new Map(graph.entities.map((entity) => [entity.id, entity.name]))
  const quote =
    graph.triples.find((triple) => triple.source_id === selected || triple.target_id === selected)
      ?.quote ?? null
  return (
    <div>
      <ul className="nodes">
        {graph.entities.map((entity) => (
          <li key={entity.id}>
            <button
              type="button"
              className={selected === entity.id ? 'node selected' : 'node'}
              onClick={() => setSelected(entity.id)}
            >
              {entity.name}
              <span className="hint"> {entity.type}</span>
            </button>
          </li>
        ))}
      </ul>
      {quote ? <p className="quote">{quote}</p> : null}
      <ul className="triples">
        {graph.triples.map((triple) => (
          <li key={triple.id}>
            {names.get(triple.source_id) ?? triple.source_id} {triple.predicate}{' '}
            {names.get(triple.target_id) ?? triple.target_id}
          </li>
        ))}
      </ul>
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

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!question.trim()) return
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

  return (
    <div>
      <form className="upload" onSubmit={(event) => void onSubmit(event)}>
        <textarea
          aria-label="Question"
          placeholder="Ask a question about your documents"
          rows={3}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
        />
        <button type="submit" disabled={asking || !question.trim()}>
          {asking ? 'Searching…' : 'Ask'}
        </button>
      </form>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      {result ? (
        <div>
          <ol className="trace">
            {result.trace.map((entry, index) => (
              <li key={`${entry.name}-${index}`}>
                <strong>{entry.name === 'search_graph' ? 'Search graph' : 'Read document'}</strong>
                <div className="hint">{entry.summary}</div>
              </li>
            ))}
          </ol>
          <p>{result.answer}</p>
        </div>
      ) : (
        <p className="hint">The search steps and the answer show up here.</p>
      )}
    </div>
  )
}
