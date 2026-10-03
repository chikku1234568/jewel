import { useEffect, useRef } from 'react'
import type { Core, ElementDefinition, LayoutOptions } from 'cytoscape'
import type { FileDrawing } from '../lib/graphElements'

/** What the person clicked in the drawing. */
export type GraphPick =
  | { kind: 'document' }
  | { kind: 'entity'; id: string }
  | { kind: 'triple'; id: string }
  | null

/** The furthest the automatic fit zooms in. Buttons and the scroll wheel can go further. */
const FIT_MAX_ZOOM = 1.8

type Point = { x: number; y: number }
type View = { zoom: number; pan: Point }

function cssVar(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

/** Statements only. A spoke from the file to every name turns the picture into a star. */
function elementsFor(drawing: FileDrawing, placed: Map<string, Point>): ElementDefinition[] {
  return [
    ...drawing.entities.map((entity) => {
      const at = placed.get(entity.id)
      return {
        data: { id: entity.id, label: entity.name },
        classes: `entity type-${entity.type}`,
        ...(at ? { position: at } : {}),
      }
    }),
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

function fitGently(cy: Core) {
  cy.resize()
  cy.fit(undefined, 48)
  if (cy.zoom() > FIT_MAX_ZOOM) {
    cy.zoom(FIT_MAX_ZOOM)
    cy.center()
  }
}

function remember(cy: Core, placed: Map<string, Point>, view: { current: View | null }) {
  cy.nodes().forEach((node) => {
    placed.set(node.id(), { ...node.position() })
  })
  view.current = { zoom: cy.zoom(), pan: { ...cy.pan() } }
}

/**
 * One file, drawn with Cytoscape. The first view lays the names out once and then
 * leaves them there: panning, zooming, and dragging do not run the layout again, and
 * removing a statement keeps the other names where you left them.
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
  const placedRef = useRef<{ file: string; pos: Map<string, Point> }>({
    file: '',
    pos: new Map(),
  })
  const viewRef = useRef<View | null>(null)
  const nodeKeyRef = useRef('')
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
      const current = drawingRef.current
      if (placedRef.current.file !== current.documentId) {
        placedRef.current = { file: current.documentId, pos: new Map() }
        viewRef.current = null
        nodeKeyRef.current = ''
      }
      const placed = placedRef.current.pos
      const nodeKey = current.entities
        .map((entity) => entity.id)
        .sort()
        .join('|')
      const namesChanged = nodeKey !== nodeKeyRef.current
      nodeKeyRef.current = nodeKey
      const known = current.entities.filter((entity) => placed.has(entity.id)).length
      const reuse = known > 0 && known >= current.entities.length * 0.6
      const accent = cssVar('--accent', '#1f5c55')
      const ink = cssVar('--ink', '#1d1c1a')
      const ink2 = cssVar('--ink-2', '#45433e')
      const muted = cssVar('--muted', '#6c685f')
      const accentStrong = cssVar('--accent-strong', '#164540')
      const surface = cssVar('--surface', '#ffffff')
      const cy = cytoscape({
        container,
        elements: elementsFor(current, reuse ? placed : new Map()),
        minZoom: 0.15,
        maxZoom: 4,
        wheelSensitivity: 0.75,
        pixelRatio: 'auto',
        boxSelectionEnabled: false,
        layout: { name: 'preset' },
        style: [
          {
            selector: 'node',
            style: {
              label: 'data(label)',
              'font-size': 13,
              color: ink,
              'text-valign': 'bottom',
              'text-margin-y': 6,
              'text-wrap': 'wrap',
              'text-max-width': '140px',
              width: 28,
              height: 28,
              'background-color': accent,
              'border-width': 2,
              'border-color': surface,
            },
          },
          { selector: 'node.type-person', style: { shape: 'ellipse', 'background-color': accent } },
          {
            selector: 'node.type-organization',
            style: { shape: 'diamond', 'background-color': ink, width: 30, height: 30 },
          },
          {
            selector: 'node.type-place',
            style: { shape: 'triangle', 'background-color': accentStrong, width: 30, height: 28 },
          },
          {
            selector: 'node.type-concept',
            style: { shape: 'hexagon', 'background-color': ink2, width: 28, height: 28 },
          },
          {
            selector: 'node.type-other',
            style: { shape: 'round-rectangle', 'background-color': muted, width: 24, height: 24 },
          },
          {
            selector: 'edge',
            style: {
              width: 1.6,
              'line-color': accent,
              'curve-style': 'bezier',
              'target-arrow-color': accent,
              'target-arrow-shape': 'triangle',
              'arrow-scale': 1,
              label: 'data(label)',
              'font-size': 11,
              color: ink2,
              'text-rotation': 'autorotate',
              'text-background-color': surface,
              'text-background-opacity': 0.92,
              'text-background-padding': '3px',
              'text-background-shape': 'roundrectangle',
              'min-zoomed-font-size': 10,
            },
          },
          {
            selector: 'node:selected',
            style: { 'border-width': 4, 'border-color': accentStrong },
          },
          {
            selector: 'node.hot',
            style: { 'border-width': 3, 'border-color': accentStrong },
          },
          {
            selector: 'edge:selected, edge.hot',
            style: { width: 3, 'line-color': accentStrong, 'target-arrow-color': accentStrong },
          },
        ],
      })
      const setCursor = (value: string) => {
        container.style.cursor = value
      }
      cy.on('tap', 'node', (event) => onPickRef.current({ kind: 'entity', id: event.target.id() }))
      cy.on('tap', 'edge', (event) => onPickRef.current({ kind: 'triple', id: event.target.id() }))
      cy.on('tap', (event) => {
        if (event.target === cy) onPickRef.current(null)
      })
      cy.on('mouseover', 'node', (event) => {
        event.target.addClass('hot')
        setCursor('grab')
      })
      cy.on('mouseout', 'node', (event) => {
        event.target.removeClass('hot')
        setCursor('')
      })
      cy.on('grab', 'node', () => setCursor('grabbing'))
      cy.on('free', 'node', (event) => {
        placed.set(event.target.id(), { ...event.target.position() })
        setCursor('grab')
      })
      cy.on('mouseover', 'edge', (event) => event.target.addClass('hot'))
      cy.on('mouseout', 'edge', (event) => event.target.removeClass('hot'))
      cyRef.current = cy
      if (selectedRef.current) cy.getElementById(selectedRef.current).select()

      let programmatic = false
      let userMoved = false
      cy.on('viewport', () => {
        if (!programmatic) userMoved = true
      })
      const applyView = (shouldFit: boolean) => {
        if (cancelled || cy.destroyed()) return
        const saved = viewRef.current
        if (!shouldFit && saved && container.clientWidth > 0) {
          programmatic = true
          cy.viewport({ zoom: saved.zoom, pan: saved.pan })
          programmatic = false
          remember(cy, placed, viewRef)
          return
        }
        cy.nodes().forEach((node) => {
          placed.set(node.id(), { ...node.position() })
        })
        if (container.clientWidth === 0) return
        programmatic = true
        fitGently(cy)
        programmatic = false
        remember(cy, placed, viewRef)
      }

      if (reuse) {
        applyView(namesChanged || viewRef.current === null)
      } else {
        const layout = cy.layout({
          name: 'cose',
          animate: false,
          randomize: true,
          padding: 40,
          nodeRepulsion: () => 12000,
          idealEdgeLength: () => 90,
          gravity: 0.4,
          numIter: 250,
          nodeOverlap: 12,
        } as LayoutOptions)
        layout.on('layoutstop', () => applyView(true))
        layout.run()
      }

      let lastWidth = container.clientWidth
      observer = new ResizeObserver(() => {
        if (cancelled || cy.destroyed()) return
        const width = container.clientWidth
        cy.resize()
        // The graph area is mounted while hidden. Fit once when it first gets a box,
        // and leave the view alone after the person has panned or zoomed.
        if (lastWidth === 0 && width > 0 && !userMoved) applyView(viewRef.current === null)
        lastWidth = width
      })
      observer.observe(container)
    })

    return () => {
      cancelled = true
      observer?.disconnect()
      if (cyRef.current && !cyRef.current.destroyed()) {
        remember(cyRef.current, placedRef.current.pos, viewRef)
        cyRef.current.destroy()
      }
      cyRef.current = null
    }
  }, [signature])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.elements().unselect()
    if (selectedId) cy.getElementById(selectedId).select()
  }, [selectedId, signature])

  function zoomBy(factor: number) {
    const cy = cyRef.current
    if (!cy) return
    const next = Math.min(cy.maxZoom(), Math.max(cy.minZoom(), cy.zoom() * factor))
    cy.zoom({
      level: next,
      renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
    })
  }

  function fitView() {
    const cy = cyRef.current
    if (!cy) return
    fitGently(cy)
    remember(cy, placedRef.current.pos, viewRef)
  }

  return (
    <div className="graph-stage">
      <div
        ref={containerRef}
        className="graph-canvas"
        role="img"
        aria-label={`Graph of ${drawing.filename}: ${drawing.entities.length} names, ${drawing.triples.length} statements. Drag a name to move it. Scroll to zoom.`}
      />
      <div className="graph-zoom" role="group" aria-label="Zoom">
        <button type="button" className="button button-small" onClick={() => zoomBy(1.2)}>
          +
        </button>
        <button type="button" className="button button-small" onClick={() => zoomBy(0.84)}>
          −
        </button>
        <button type="button" className="button button-small" onClick={fitView}>
          Fit
        </button>
      </div>
    </div>
  )
}
