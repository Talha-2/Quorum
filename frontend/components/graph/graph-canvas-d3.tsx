'use client'

/**
 * Force-directed graph canvas — d3-force based.
 *
 * Key behaviors:
 *   - d3.forceSimulation with charge(-400), collide(50), centripetal x/y
 *   - SVG-based; nodes are <circle>, edges are <path> (curved bezier for
 *     parallel edges, circular arcs for self-loops)
 *   - d3.zoom applied to a wrapper <g>, scaleExtent [0.1, 4]
 *   - d3.drag on nodes (fixes position on drag end so they stay put)
 *   - "Show Edge Labels" toggle for the relationship type strings
 *   - Click node → onNodeClick prop
 *   - Hover node → highlight its neighbors and connected edges
 *   - Initial nodes can spawn one-by-one for the "watch the graph build" feel
 */

import React, { useEffect, useMemo, useRef, useState } from 'react'
import * as d3 from 'd3'
import { Maximize2, RefreshCw, Eye, EyeOff } from 'lucide-react'

// ============================================
// Types
// ============================================

export interface D3GraphNode {
  id: string
  name: string
  type: string                  // ontology type, used for color
  description?: string
  is_individual?: boolean
  // d3-force will mutate these in place during simulation
  x?: number
  y?: number
  vx?: number
  vy?: number
  fx?: number | null
  fy?: number | null
}

export interface D3GraphEdge {
  id: string
  source: string | D3GraphNode  // string before d3 resolves; node after
  target: string | D3GraphNode
  type: string                  // relation type (e.g. REPORTS_ON)
  description?: string
  // computed by us before render so multi-edges curve apart
  pairTotal?: number
  pairIndex?: number
  curvature?: number
  isSelfLoop?: boolean
}

interface GraphCanvasD3Props {
  nodes: D3GraphNode[]
  edges: D3GraphEdge[]
  selectedNodeId?: string | null
  height?: string
  showEdgeLabels?: boolean
  onShowEdgeLabelsChange?: (v: boolean) => void
  onNodeClick?: (node: D3GraphNode) => void
  onNodeHover?: (id: string | null) => void
  onRefresh?: () => void
  showLegend?: boolean
}

// ============================================
// Color palette — stable per ontology type name
// ============================================

const PALETTE = [
  '#FF4500', // brand orange
  '#00B0FF', // sky blue
  '#00C851', // green
  '#9b51e0', // purple
  '#f59e0b', // amber
  '#0ea5e9', // cyan
  '#ec4899', // pink
  '#10b981', // emerald
  '#6366f1', // indigo
  '#ef4444', // red
  '#84cc16', // lime
  '#a855f7', // violet
]

function colorForType(type: string, allTypes: string[]): string {
  const idx = allTypes.indexOf(type)
  if (idx === -1) return '#9b9895'
  return PALETTE[idx % PALETTE.length]
}

// ============================================
// Edge math — group parallel edges so they fan out as curves
// ============================================

function computeEdgeCurvature(edges: D3GraphEdge[]): D3GraphEdge[] {
  // Group edges by unordered (source, target) pair
  const groups = new Map<string, D3GraphEdge[]>()
  for (const e of edges) {
    const s = typeof e.source === 'string' ? e.source : e.source.id
    const t = typeof e.target === 'string' ? e.target : e.target.id
    const isSelfLoop = s === t
    e.isSelfLoop = isSelfLoop
    const key = isSelfLoop ? `self:${s}` : [s, t].sort().join('|')
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(e)
  }

  const allGroups: D3GraphEdge[][] = []
  groups.forEach((g) => allGroups.push(g))
  for (const group of allGroups) {
    const total = group.length
    group.forEach((e, i) => {
      e.pairTotal = total
      e.pairIndex = i
      // First edge straight, then alternate sides with growing offset
      if (e.isSelfLoop) {
        e.curvature = 1
      } else if (total === 1) {
        e.curvature = 0
      } else {
        // Distribute around 0: ..., -2, -1, 0, 1, 2, ...
        const offset = i - (total - 1) / 2
        e.curvature = offset * 0.6
      }
    })
  }

  return edges
}

// ============================================
// Component
// ============================================

export default function GraphCanvasD3({
  nodes,
  edges,
  selectedNodeId = null,
  height = 'h-full',
  showEdgeLabels: showEdgeLabelsProp,
  onShowEdgeLabelsChange,
  onNodeClick,
  onNodeHover,
  onRefresh,
  showLegend = true,
}: GraphCanvasD3Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const svgRef = useRef<SVGSVGElement | null>(null)
  const simulationRef = useRef<d3.Simulation<D3GraphNode, D3GraphEdge> | null>(null)
  const transformRef = useRef<d3.ZoomTransform>(d3.zoomIdentity)

  // Internal show-edge-labels state if not controlled
  const [internalShowEdgeLabels, setInternalShowEdgeLabels] = useState(false)
  const showEdgeLabels = showEdgeLabelsProp ?? internalShowEdgeLabels
  const setShowEdgeLabels = onShowEdgeLabelsChange ?? setInternalShowEdgeLabels

  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [zoomPercent, setZoomPercent] = useState(100)

  // Stable list of unique types for color mapping + legend
  const allTypes = useMemo(() => {
    const seen = new Set<string>()
    const list: string[] = []
    nodes.forEach((n) => {
      if (!seen.has(n.type)) {
        seen.add(n.type)
        list.push(n.type)
      }
    })
    return list.sort()
  }, [nodes])

  // ============================================
  // Build neighbour index for hover highlighting
  // ============================================
  const neighbours = useMemo(() => {
    const m = new Map<string, Set<string>>()
    edges.forEach((e) => {
      const s = typeof e.source === 'string' ? e.source : e.source.id
      const t = typeof e.target === 'string' ? e.target : e.target.id
      if (!m.has(s)) m.set(s, new Set())
      if (!m.has(t)) m.set(t, new Set())
      m.get(s)!.add(t)
      m.get(t)!.add(s)
    })
    return m
  }, [edges])

  // ============================================
  // The simulation — runs whenever nodes/edges change
  // ============================================
  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return
    if (nodes.length === 0) {
      // Clear any prior render
      d3.select(svgRef.current).selectAll('*').remove()
      simulationRef.current?.stop()
      return
    }

    const width = containerRef.current.clientWidth
    const heightPx = containerRef.current.clientHeight

    // Clone data so d3 mutations don't leak into props
    const nodeMap = new Map<string, D3GraphNode>()
    const simNodes: D3GraphNode[] = nodes.map((n) => {
      const copy: D3GraphNode = { ...n }
      nodeMap.set(copy.id, copy)
      return copy
    })

    // Resolve edge endpoints to node references and compute curvature
    const simEdges: D3GraphEdge[] = edges
      .map((e) => {
        const sid = typeof e.source === 'string' ? e.source : e.source.id
        const tid = typeof e.target === 'string' ? e.target : e.target.id
        const sNode = nodeMap.get(sid)
        const tNode = nodeMap.get(tid)
        if (!sNode || !tNode) return null
        return {
          ...e,
          source: sNode,
          target: tNode,
        } as D3GraphEdge
      })
      .filter((e): e is D3GraphEdge => e !== null)

    computeEdgeCurvature(simEdges)

    // ============================================
    // d3-force simulation
    // ============================================
    const simulation = d3
      .forceSimulation<D3GraphNode>(simNodes)
      .force(
        'link',
        d3
          .forceLink<D3GraphNode, D3GraphEdge>(simEdges)
          .id((d) => d.id)
          .distance((d: any) => {
            // 150 base + 50 per extra parallel edge so duplicates fan out
            const base = 150
            const extra = ((d.pairTotal || 1) - 1) * 50
            return base + extra
          })
      )
      .force('charge', d3.forceManyBody().strength(-400))
      .force('center', d3.forceCenter(width / 2, heightPx / 2))
      .force('collide', d3.forceCollide(50))
      .force('x', d3.forceX(width / 2).strength(0.04))
      .force('y', d3.forceY(heightPx / 2).strength(0.04))

    simulationRef.current = simulation

    // ============================================
    // SVG setup
    // ============================================
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()
    svg
      .attr('viewBox', `0 0 ${width} ${heightPx}`)
      .attr('preserveAspectRatio', 'xMidYMid meet')

    // Arrow marker
    svg
      .append('defs')
      .append('marker')
      .attr('id', 'arrow-default')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 26)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#9b9895')

    svg
      .select('defs')
      .append('marker')
      .attr('id', 'arrow-active')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 26)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', 'var(--brand)')

    const g = svg.append('g').attr('class', 'zoom-target')
    // Restore prior zoom if we had one
    g.attr('transform', transformRef.current.toString())

    // ============================================
    // Zoom + pan
    // ============================================
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform.toString())
        transformRef.current = event.transform
        setZoomPercent(Math.round(event.transform.k * 100))
      })
    svg.call(zoom)

    // ============================================
    // Edges (curved paths)
    // ============================================
    const linkLayer = g.append('g').attr('class', 'links')
    const labelLayer = g.append('g').attr('class', 'edge-labels')

    const link = linkLayer
      .selectAll<SVGPathElement, D3GraphEdge>('path')
      .data(simEdges, (d: any) => d.id)
      .enter()
      .append('path')
      .attr('stroke', '#c6c6c6')
      .attr('stroke-width', 1.4)
      .attr('fill', 'none')
      .attr('marker-end', 'url(#arrow-default)')
      .attr('class', 'edge-path')
      .attr('data-edge-id', (d) => d.id)
      .style('cursor', 'pointer')

    const edgeLabel = labelLayer
      .selectAll<SVGTextElement, D3GraphEdge>('text')
      .data(simEdges, (d: any) => d.id)
      .enter()
      .append('text')
      .attr('text-anchor', 'middle')
      .attr('font-size', 9)
      .attr('font-family', 'ui-monospace, monospace')
      .attr('fill', '#9b9895')
      .attr('pointer-events', 'none')
      .style('display', showEdgeLabels ? 'block' : 'none')
      .text((d) => d.type)

    // ============================================
    // Nodes
    // ============================================
    const nodeLayer = g.append('g').attr('class', 'nodes')

    const node = nodeLayer
      .selectAll<SVGGElement, D3GraphNode>('g')
      .data(simNodes, (d: any) => d.id)
      .enter()
      .append('g')
      .attr('class', 'node')
      .style('cursor', 'grab')

    // Circle
    node
      .append('circle')
      .attr('r', 10)
      .attr('fill', (d) => colorForType(d.type, allTypes))
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 2)

    // Label below the node
    node
      .append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', 22)
      .attr('font-size', 10)
      .attr('font-family', 'system-ui, sans-serif')
      .attr('fill', 'var(--ink)')
      .attr('pointer-events', 'none')
      .text((d) => (d.name.length > 16 ? d.name.slice(0, 16) + '…' : d.name))

    // Click + hover
    node
      .on('click', (event, d) => {
        event.stopPropagation()
        onNodeClick?.(d)
      })
      .on('mouseenter', (_event, d) => {
        setHoveredId(d.id)
        onNodeHover?.(d.id)
      })
      .on('mouseleave', () => {
        setHoveredId(null)
        onNodeHover?.(null)
      })

    // Drag
    const drag = d3
      .drag<SVGGElement, D3GraphNode>()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
      })
      .on('drag', (event, d) => {
        d.fx = event.x
        d.fy = event.y
      })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0)
        // Leave fx/fy set so the node stays where dragged
      })
    node.call(drag)

    // ============================================
    // Tick handler — recompute positions
    // ============================================
    const linkPath = (d: D3GraphEdge): string => {
      const s: any = d.source
      const t: any = d.target
      if (typeof s !== 'object' || typeof t !== 'object') return ''
      const sx = s.x ?? 0
      const sy = s.y ?? 0
      const tx = t.x ?? 0
      const ty = t.y ?? 0

      if (d.isSelfLoop) {
        const r = 30
        const x1 = sx + 8
        const y1 = sy - 4
        const x2 = sx + 8
        const y2 = sy + 4
        return `M${x1},${y1} A${r},${r} 0 1,1 ${x2},${y2}`
      }

      const curv = d.curvature ?? 0
      if (curv === 0) {
        return `M${sx},${sy} L${tx},${ty}`
      }

      const dx = tx - sx
      const dy = ty - sy
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      const offset = Math.max(35, dist * (0.25 + (d.pairTotal || 1) * 0.05))
      const ox = (-dy / dist) * curv * offset
      const oy = (dx / dist) * curv * offset
      const cx = (sx + tx) / 2 + ox
      const cy = (sy + ty) / 2 + oy
      return `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`
    }

    const linkMidpoint = (d: D3GraphEdge): { x: number; y: number } => {
      const s: any = d.source
      const t: any = d.target
      const sx = s.x ?? 0
      const sy = s.y ?? 0
      const tx = t.x ?? 0
      const ty = t.y ?? 0
      if (d.isSelfLoop) return { x: sx + 70, y: sy }
      const curv = d.curvature ?? 0
      if (curv === 0) return { x: (sx + tx) / 2, y: (sy + ty) / 2 - 4 }
      const dx = tx - sx
      const dy = ty - sy
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      const offset = Math.max(35, dist * (0.25 + (d.pairTotal || 1) * 0.05))
      const ox = (-dy / dist) * curv * offset
      const oy = (dx / dist) * curv * offset
      const cx = (sx + tx) / 2 + ox
      const cy = (sy + ty) / 2 + oy
      // Quadratic bezier midpoint t=0.5
      return {
        x: 0.25 * sx + 0.5 * cx + 0.25 * tx,
        y: 0.25 * sy + 0.5 * cy + 0.25 * ty,
      }
    }

    simulation.on('tick', () => {
      link.attr('d', linkPath)
      edgeLabel
        .attr('x', (d) => linkMidpoint(d).x)
        .attr('y', (d) => linkMidpoint(d).y)
      node.attr('transform', (d) => `translate(${d.x ?? 0},${d.y ?? 0})`)
    })

    // Cleanup
    return () => {
      simulation.stop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, allTypes])

  // ============================================
  // React to showEdgeLabels toggle without rebuilding sim
  // ============================================
  useEffect(() => {
    if (!svgRef.current) return
    d3.select(svgRef.current)
      .selectAll<SVGTextElement, unknown>('g.edge-labels text')
      .style('display', showEdgeLabels ? 'block' : 'none')
  }, [showEdgeLabels])

  // ============================================
  // React to selection / hover — highlight edges + dim others
  // ============================================
  useEffect(() => {
    if (!svgRef.current) return
    const focusId = hoveredId ?? selectedNodeId
    const svg = d3.select(svgRef.current)

    if (!focusId) {
      svg.selectAll<SVGPathElement, D3GraphEdge>('path.edge-path')
        .attr('stroke', '#c6c6c6')
        .attr('stroke-width', 1.4)
        .attr('marker-end', 'url(#arrow-default)')
        .attr('opacity', 1)
      svg.selectAll<SVGGElement, D3GraphNode>('g.node').attr('opacity', 1)
      return
    }

    const focusNeighbours = neighbours.get(focusId) ?? new Set<string>()

    svg.selectAll<SVGPathElement, D3GraphEdge>('path.edge-path').each(function (d) {
      const s = typeof d.source === 'string' ? d.source : (d.source as any).id
      const t = typeof d.target === 'string' ? d.target : (d.target as any).id
      const isAdjacent = s === focusId || t === focusId
      d3.select(this)
        .attr('stroke', isAdjacent ? 'var(--brand)' : '#e5e4e2')
        .attr('stroke-width', isAdjacent ? 2 : 1)
        .attr('marker-end', isAdjacent ? 'url(#arrow-active)' : 'url(#arrow-default)')
        .attr('opacity', isAdjacent ? 1 : 0.4)
    })

    svg.selectAll<SVGGElement, D3GraphNode>('g.node').each(function (d) {
      const isFocus = d.id === focusId
      const isNeighbour = focusNeighbours.has(d.id)
      d3.select(this)
        .attr('opacity', isFocus || isNeighbour ? 1 : 0.35)
        .select('circle')
        .attr('r', isFocus ? 14 : 10)
        .attr('stroke', isFocus ? 'var(--brand)' : '#ffffff')
        .attr('stroke-width', isFocus ? 3 : 2)
    })
  }, [hoveredId, selectedNodeId, neighbours])

  // ============================================
  // Reset view
  // ============================================
  const resetView = () => {
    if (!svgRef.current) return
    const svg = d3.select(svgRef.current)
    svg.transition().duration(500).call(
      d3.zoom<SVGSVGElement, unknown>().on('zoom', (event) => {
        const g = svg.select<SVGGElement>('g.zoom-target')
        g.attr('transform', event.transform.toString())
        transformRef.current = event.transform
        setZoomPercent(Math.round(event.transform.k * 100))
      }).transform as any,
      d3.zoomIdentity
    )
  }

  return (
    <div
      ref={containerRef}
      className={`${height} w-full relative bg-[var(--bg-soft)] rounded-md overflow-hidden border border-[var(--line)]`}
      style={{
        backgroundImage: 'radial-gradient(circle, var(--line) 1px, transparent 1px)',
        backgroundSize: '20px 20px',
      }}
    >
      <svg ref={svgRef} className="absolute inset-0 w-full h-full" />

      {/* Empty state */}
      {nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center">
            <p className="font-display text-lg font-medium text-[var(--ink)]">No graph yet</p>
            <p className="text-sm text-[var(--muted)] mt-1">
              Launch a simulation to see the knowledge graph build
            </p>
          </div>
        </div>
      )}

      {/* Top-right tool bar — Show Edge Labels + Refresh + Reset */}
      {nodes.length > 0 && (
        <div className="absolute top-3 right-3 flex items-center gap-1">
          <button
            onClick={() => setShowEdgeLabels(!showEdgeLabels)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-[var(--card)] border border-[var(--line)] rounded-md text-[10px] font-mono text-[var(--ink)] hover:border-[var(--brand)] transition-colors"
            title="Toggle edge labels"
          >
            {showEdgeLabels ? (
              <Eye className="h-3 w-3 text-[var(--brand)]" />
            ) : (
              <EyeOff className="h-3 w-3 text-[var(--muted)]" />
            )}
            edges
          </button>
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="p-1.5 bg-[var(--card)] border border-[var(--line)] rounded-md hover:border-[var(--brand)] transition-colors"
              title="Refresh"
            >
              <RefreshCw className="h-3 w-3 text-[var(--muted)]" />
            </button>
          )}
          <button
            onClick={resetView}
            className="p-1.5 bg-[var(--card)] border border-[var(--line)] rounded-md hover:border-[var(--brand)] transition-colors"
            title="Reset view"
          >
            <Maximize2 className="h-3 w-3 text-[var(--muted)]" />
          </button>
        </div>
      )}

      {/* Stats pill */}
      {nodes.length > 0 && (
        <div className="absolute top-3 left-3 bg-[var(--card)] border border-[var(--line)] rounded-md px-2.5 py-1.5">
          <span className="text-[10px] font-mono text-[var(--muted)]">
            {zoomPercent}% · {nodes.length} · {edges.length}
          </span>
        </div>
      )}

      {/* Legend (entity types) */}
      {showLegend && allTypes.length > 0 && (
        <div className="absolute bottom-3 left-3 bg-[var(--card)] border border-[var(--line)] rounded-md p-3 max-w-[260px]">
          <p className="label-mono mb-2">Entity types</p>
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {allTypes.map((type) => (
              <div key={type} className="flex items-center gap-1.5">
                <span
                  className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ background: colorForType(type, allTypes) }}
                />
                <span className="text-[10px] text-[var(--ink)]">{type}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Hint */}
      {nodes.length > 0 && (
        <div className="absolute bottom-3 right-3 bg-[var(--card)] border border-[var(--line)] rounded-md px-2.5 py-1.5">
          <span className="text-[10px] font-mono text-[var(--muted)]">drag · scroll · click</span>
        </div>
      )}
    </div>
  )
}
