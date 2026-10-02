/**
 * Which part of `GET /graph` to draw. Pure functions, no Cytoscape here.
 *
 * Only one file is drawn at a time: its document node, the entities its triples touch,
 * and the triples whose `document_id` is that file. A large library therefore never puts
 * every node on screen at once. Focusing an entity narrows that to the entity's own edges.
 */
import type { GraphEntity, GraphTriple, GraphView } from './api'

export interface FileDrawing {
  documentId: string
  filename: string
  /** Entities to draw: endpoints of the drawn triples. */
  entities: GraphEntity[]
  /** Triples to draw, all from this file. */
  triples: GraphTriple[]
}

/** Id of the drawn document node; prefixed so it can never collide with an entity id. */
export function documentNodeId(documentId: string): string {
  return `document:${documentId}`
}

/** One file, optionally narrowed to the edges that touch `focusEntityId`. */
export function drawingFor(
  graph: GraphView,
  documentId: string,
  focusEntityId: string | null,
): FileDrawing {
  const filename = graph.documents.find((doc) => doc.id === documentId)?.filename ?? documentId
  let triples = graph.triples.filter((triple) => triple.document_id === documentId)
  if (focusEntityId) {
    triples = triples.filter(
      (triple) => triple.source_id === focusEntityId || triple.target_id === focusEntityId,
    )
  }
  const used = new Set(triples.flatMap((triple) => [triple.source_id, triple.target_id]))
  const entities = graph.entities.filter((entity) => used.has(entity.id))
  return { documentId, filename, entities, triples }
}

/** Triples per file, so the selector can open on a file that has something to draw. */
export function tripleCounts(graph: GraphView): Map<string, number> {
  const counts = new Map<string, number>()
  for (const triple of graph.triples) {
    counts.set(triple.document_id, (counts.get(triple.document_id) ?? 0) + 1)
  }
  return counts
}
