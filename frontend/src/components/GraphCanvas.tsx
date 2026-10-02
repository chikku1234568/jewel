import { useEffect, useRef } from 'react'
import type { Core, ElementDefinition } from 'cytoscape'
import { documentNodeId, type FileDrawing } from '../lib/graphElements'

/** What the person clicked in the drawing. */
export type GraphPick =
  | { kind: 'document' }
  | { kind: 'entity'; id: string }
  | { kind: 'triple'; id: string }
  | null


/** The furthest the automatic fit zooms in; the person can still zoom further. */
const FIT_MAX_ZOOM = 1.5

function cssVar(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

function elementsFor(drawing: FileDrawing): ElementDefinition[] {
  const documentNode = documentNodeId(drawing.documentId)
  return [
    { data: { id: documentNode, label: drawing.filename }, classes: 'document' },
    ...drawing.entities.map((entity) => ({
      data: { id: entity.id, label: entity.name },
      classes: `entity type-${entity.type}`,
    })),
    // A light link from the file to each entity it names, so the file sits in the picture.
    ...drawing.entities.map((entity) => ({
      data: { id: `${documentNode}->${entity.id}`, source: documentNode, target: entity.id },
      classes: 'mention',
      selectable: false,
    })),
    ...drawing.triples.map((triple) => ({
      data: {
        id: triple.id,
        source: triple.source_id,
        target: triple.target_id,
        label: triple.predicate,
      },
      classes: 'triple',
    })),
  ]
}

/**
 * Cytoscape.js drawing of one file. Cytoscape is loaded on first use, so the Documents
 * and Ask areas do not pay for it. The instance is rebuilt when the drawing changes (a
 * new file or a new focus); one file is small enough that this stays instant.
 */
export function GraphCanvas({
  drawing,
  selectedId,
  onPick,
}: {
  drawing: FileDrawing
  selectedId: string | null
  onPick: (pick: GraphPick) => void
}) {
  // The library polls while a build runs and the graph is refetched each time. Rebuild
  // the drawing only when what is drawn changes, so the layout does not jump every poll.
  const signature = [
    drawing.documentId,
    ...drawing.entities.map((entity) => entity.id),
    ...drawing.triples.map((triple) => triple.id),
  ].join('|')
  const drawingRef = useRef(drawing)
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const onPickRef = useRef(onPick)
  const selectedRef = useRef(selectedId)
  // Runs before the effect below in the same commit, so it always sees fresh values.
  useEffect(() => {
    drawingRef.current = drawing
    onPickRef.current = onPick
    selectedRef.current = selectedId
  }, [drawing, onPick, selectedId])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    let cancelled = false
    let observer: ResizeObserver | null = null

    void import('cytoscape').then(({ default: cytoscape }) => {
      if (cancelled) return
      const accent = cssVar('--accent', '#1f5c55')
      const ink = cssVar('--ink', '#1d1c1a')
      const muted = cssVar('--muted', '#6c685f')
      const rule = cssVar('--rule-strong', '#d2cdc2')
      const accentStrong = cssVar('--accent-strong', '#164540')
      const cy = cytoscape({
        container,
        elements: elementsFor(drawingRef.current),
        layout: {
          name: 'cose',
          animate: false,
          padding: 24,
          nodeRepulsion: () => 9000,
        },
        minZoom: 0.2,
        maxZoom: 3,
        style: [
          {
            selector: 'node',
            style: {
              label: 'data(label)',
              'font-size': 11,
              color: ink,
              'text-valign': 'bottom',
              'text-margin-y': 4,
              'text-wrap': 'ellipsis',
              'text-max-width': '120px',
              width: 18,
              height: 18,
              'background-color': accent,
            },
          },
          {
            selector: 'node.document',
            style: {
              shape: 'round-rectangle',
              width: 28,
              height: 22,
              'background-color': ink,
              'font-weight': 'bold',
            },
          },
          { selector: 'node.type-person', style: { shape: 'ellipse' } },
          { selector: 'node.type-organization', style: { shape: 'diamond' } },
          { selector: 'node.type-place', style: { shape: 'triangle' } },
          { selector: 'node.type-other', style: { 'background-color': muted } },
          {
            selector: 'edge',
            style: { width: 1.5, 'line-color': rule, 'curve-style': 'bezier' },
          },
          {
            selector: 'edge.triple',
            style: {
              label: 'data(label)',
              'font-size': 9,
              color: muted,
              'text-rotation': 'autorotate',
              'text-background-color': '#ffffff',
              'text-background-opacity': 0.85,
              'text-background-padding': '2px',
              // Edge labels disappear when zoomed far out instead of turning into noise.
              'min-zoomed-font-size': 7,
              'line-color': accent,
              'target-arrow-color': accent,
              'target-arrow-shape': 'triangle',
              'arrow-scale': 0.8,
            },
          },
          { selector: 'edge.mention', style: { 'line-style': 'dashed', width: 1 } },
          {
            selector: 'node:selected',
            style: { 'border-width': 3, 'border-color': accentStrong },
          },
          {
            selector: 'edge:selected',
            style: { width: 3, 'line-color': accentStrong, 'target-arrow-color': accentStrong },
          },
        ],
      })
      cy.on('tap', 'node.document', () => onPickRef.current({ kind: 'document' }))
      cy.on('tap', 'node.entity', (event) =>
        onPickRef.current({ kind: 'entity', id: event.target.id() }),
      )
      cy.on('tap', 'edge.triple', (event) =>
        onPickRef.current({ kind: 'triple', id: event.target.id() }),
      )
      cy.on('tap', (event) => {
        if (event.target === cy) onPickRef.current(null)
      })
      cyRef.current = cy
      if (selectedRef.current) cy.getElementById(selectedRef.current).select()

      // The Graph area is mounted while hidden and the page can be resized; Cytoscape
      // has to be told when its box changes, or it draws into a 0×0 canvas.
      observer = new ResizeObserver(() => {
        cy.resize()
        cy.fit(undefined, 24)
        // A file with few names would otherwise fill the box with giant labels.
        if (cy.zoom() > FIT_MAX_ZOOM) {
          cy.zoom(FIT_MAX_ZOOM)
          cy.center()
        }
      })
      observer.observe(container)
    })

    return () => {
      cancelled = true
      observer?.disconnect()
      cyRef.current?.destroy()
      cyRef.current = null
    }
  }, [signature])

  // Mirror the selection from the side panel (or a statement click) into the drawing.
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.elements().unselect()
    if (selectedId) cy.getElementById(selectedId).select()
  }, [selectedId, signature])

  return (
    <div
      ref={containerRef}
      className="graph-canvas"
      role="img"
      aria-label={`Graph of ${drawing.filename}: ${drawing.entities.length} names, ${drawing.triples.length} statements. The same statements are listed as text beside it.`}
    />
  )
}
