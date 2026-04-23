'use client'

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { GraphData, GraphNode } from '@/types/graph'
import GraphNodeComponent from './graph-node'

interface GraphCanvasProps {
  data?: GraphData
  selectedNodeId?: string | null
  hoveredNodeId?: string | null
  animatingNodeIds?: Set<string>
  zoomLevel?: number
  panPosition?: { x: number; y: number }
  onNodeClick?: (node: GraphNode) => void
  onNodeHover?: (nodeId: string | null) => void
  onNodeDrag?: (nodeId: string, position: { x: number; y: number }) => void
  onZoomChange?: (zoom: number) => void
  onPanChange?: (pan: { x: number; y: number }) => void
  height?: string
  showLegend?: boolean
}

const NODE_HALF = 40 // node is 80px wide, half = 40

export default function GraphCanvas({
  data,
  selectedNodeId = null,
  hoveredNodeId = null,
  animatingNodeIds,
  zoomLevel = 1,
  panPosition = { x: 0, y: 0 },
  onNodeClick,
  onNodeHover,
  onNodeDrag,
  onZoomChange,
  onPanChange,
  height = 'h-full',
  showLegend = true,
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [isPanning, setIsPanning] = useState(false)
  const [panStart, setPanStart] = useState({ x: 0, y: 0 })
  const [draggingNode, setDraggingNode] = useState<string | null>(null)
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 })

  const nodes = data?.nodes ?? []
  const edges = data?.edges ?? []
  const animSet = animatingNodeIds ?? new Set<string>()

  const getNodeColor = (type: string) => {
    const colors: Record<string, string> = {
      agent: '#FF4500',
      entity: '#00B0FF',
      theme: '#9b51e0',
      context: '#000000',
      blocker: '#b3473d',
    }
    return colors[type] || '#686562'
  }

  // ============ Wheel zoom ============
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      const delta = e.deltaY > 0 ? 0.92 : 1.08
      const next = Math.max(0.4, Math.min(zoomLevel * delta, 2.5))
      onZoomChange?.(next)
    },
    [zoomLevel, onZoomChange]
  )

  // ============ Pan ============
  const startPan = useCallback(
    (e: React.MouseEvent) => {
      // Pan with middle mouse, ctrl+drag, or shift+drag
      if (e.button === 1 || e.metaKey || e.ctrlKey || e.shiftKey) {
        e.preventDefault()
        setIsPanning(true)
        setPanStart({ x: e.clientX - panPosition.x, y: e.clientY - panPosition.y })
      }
    },
    [panPosition]
  )

  const handleContainerMove = useCallback(
    (e: React.MouseEvent) => {
      if (isPanning) {
        onPanChange?.({ x: e.clientX - panStart.x, y: e.clientY - panStart.y })
      } else if (draggingNode) {
        const rect = containerRef.current?.getBoundingClientRect()
        if (!rect) return
        // Convert screen coords to graph coords (account for pan + zoom)
        const localX = (e.clientX - rect.left - panPosition.x) / zoomLevel
        const localY = (e.clientY - rect.top - panPosition.y) / zoomLevel
        onNodeDrag?.(draggingNode, {
          x: localX - dragOffset.x,
          y: localY - dragOffset.y,
        })
      }
    },
    [isPanning, draggingNode, panStart, panPosition, zoomLevel, dragOffset, onPanChange, onNodeDrag]
  )

  const stopAll = useCallback(() => {
    setIsPanning(false)
    setDraggingNode(null)
  }, [])

  // ============ Node drag ============
  const handleNodeMouseDown = useCallback(
    (e: React.MouseEvent, node: GraphNode) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey) return // let pan handle this
      e.stopPropagation()
      const rect = containerRef.current?.getBoundingClientRect()
      if (!rect) return
      const localX = (e.clientX - rect.left - panPosition.x) / zoomLevel
      const localY = (e.clientY - rect.top - panPosition.y) / zoomLevel
      const nodeX = node.position?.x ?? 0
      const nodeY = node.position?.y ?? 0
      setDraggingNode(node.id)
      setDragOffset({ x: localX - nodeX, y: localY - nodeY })
    },
    [panPosition, zoomLevel]
  )

  // Cleanup if user releases outside
  useEffect(() => {
    const onUp = () => stopAll()
    window.addEventListener('mouseup', onUp)
    return () => window.removeEventListener('mouseup', onUp)
  }, [stopAll])

  // ============ Edge highlight on hover ============
  const isEdgeHighlighted = (edge: { source: string; target: string }) =>
    hoveredNodeId !== null &&
    (edge.source === hoveredNodeId || edge.target === hoveredNodeId)

  return (
    <div
      ref={containerRef}
      className={`${height} w-full relative bg-[var(--bg-soft)] rounded-md overflow-hidden border border-[var(--line)] select-none ${
        isPanning ? 'cursor-grabbing' : 'cursor-grab'
      }`}
      onWheel={handleWheel}
      onMouseDown={startPan}
      onMouseMove={handleContainerMove}
      onMouseUp={stopAll}
      onMouseLeave={stopAll}
      style={{
        backgroundImage:
          'radial-gradient(circle, var(--line) 1px, transparent 1px)',
        backgroundSize: '20px 20px',
      }}
    >
      {/* SVG layer for edges */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none"
        style={{
          transform: `translate(${panPosition.x}px, ${panPosition.y}px) scale(${zoomLevel})`,
          transformOrigin: '0 0',
        }}
      >
        <defs>
          <marker
            id="arrowhead"
            markerWidth="8"
            markerHeight="8"
            refX="7"
            refY="3"
            orient="auto"
          >
            <polygon points="0 0, 8 3, 0 6" fill="var(--muted-soft)" />
          </marker>
          <marker
            id="arrowhead-active"
            markerWidth="8"
            markerHeight="8"
            refX="7"
            refY="3"
            orient="auto"
          >
            <polygon points="0 0, 8 3, 0 6" fill="var(--brand)" />
          </marker>
        </defs>

        {edges.map(edge => {
          const sourceNode = nodes.find(n => n.id === edge.source)
          const targetNode = nodes.find(n => n.id === edge.target)
          if (!sourceNode || !targetNode) return null

          const sx = (sourceNode.position?.x || 0) + NODE_HALF
          const sy = (sourceNode.position?.y || 0) + NODE_HALF
          const tx = (targetNode.position?.x || 0) + NODE_HALF
          const ty = (targetNode.position?.y || 0) + NODE_HALF

          const highlighted = isEdgeHighlighted(edge)

          return (
            <g key={edge.id}>
              <line
                x1={sx}
                y1={sy}
                x2={tx}
                y2={ty}
                stroke={highlighted ? 'var(--brand)' : 'var(--line-strong)'}
                strokeWidth={highlighted ? 2 : 1.5}
                markerEnd={highlighted ? 'url(#arrowhead-active)' : 'url(#arrowhead)'}
                strokeDasharray={edge.animated ? '5,5' : 'none'}
                className={edge.animated ? 'animate-dash' : ''}
                style={{ transition: 'stroke 200ms ease, stroke-width 200ms ease' }}
              />
              {highlighted && (
                <text
                  x={(sx + tx) / 2}
                  y={(sy + ty) / 2 - 6}
                  textAnchor="middle"
                  className="text-[9px] font-mono uppercase tracking-wider fill-[var(--brand)]"
                  pointerEvents="none"
                >
                  {edge.type}
                </text>
              )}
            </g>
          )
        })}
      </svg>

      {/* Nodes layer */}
      <div
        className="absolute inset-0 w-full h-full"
        style={{
          transform: `translate(${panPosition.x}px, ${panPosition.y}px) scale(${zoomLevel})`,
          transformOrigin: '0 0',
        }}
      >
        {nodes.map(node => (
          <GraphNodeComponent
            key={node.id}
            node={node}
            isSelected={selectedNodeId === node.id}
            isHovered={hoveredNodeId === node.id}
            isAnimating={animSet.has(node.id)}
            color={getNodeColor(node.type)}
            onClick={() => onNodeClick?.(node)}
            onHover={() => onNodeHover?.(node.id)}
            onHoverEnd={() => onNodeHover?.(null)}
            onMouseDown={(e) => handleNodeMouseDown(e, node)}
            isDragging={draggingNode === node.id}
            style={{
              transform: `translate(${node.position?.x || 0}px, ${node.position?.y || 0}px)`,
            }}
          />
        ))}
      </div>

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

      {/* Legend */}
      {showLegend && (
        <div className="absolute bottom-4 left-4 bg-[var(--card)] border border-[var(--line)] rounded-md p-3">
          <p className="label-mono mb-2">Node types</p>
          <div className="space-y-1.5">
            {['agent', 'entity', 'theme', 'context', 'blocker'].map(type => (
              <div key={type} className="flex items-center gap-2">
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: getNodeColor(type) }}
                />
                <span className="text-[11px] capitalize text-[var(--ink)]">{type}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top-right info pill */}
      <div className="absolute top-4 right-4 bg-[var(--card)] border border-[var(--line)] rounded-md px-2.5 py-1.5 flex items-center gap-2">
        <span className="text-[10px] font-mono text-[var(--muted)]">
          {(zoomLevel * 100).toFixed(0)}%
        </span>
        <span className="text-[10px] font-mono text-[var(--muted-soft)]">
          {nodes.length} · {edges.length}
        </span>
      </div>

      {/* Hint */}
      <div className="absolute bottom-4 right-4 bg-[var(--card)] border border-[var(--line)] rounded-md px-2.5 py-1.5">
        <span className="text-[10px] font-mono text-[var(--muted)]">
          drag · scroll · ⇧+drag pan
        </span>
      </div>
    </div>
  )
}
