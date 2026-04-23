'use client'

import React, { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Search,
  Filter,
  X,
  Bot,
  Box,
  Target,
  BookOpen,
  Ban,
  Network,
  ArrowRight,
} from 'lucide-react'

import GraphCanvasD3 from '@/components/graph/graph-canvas-d3'
import type { D3GraphNode, D3GraphEdge } from '@/components/graph/graph-canvas-d3'
import type { Project, AgentProfile } from '@/types/pipeline'

interface QuorumGraphViewProps {
  project: Project
  onChatWithAgent?: (agent: AgentProfile) => void
}

const NODE_TYPE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  agent: Bot,
  entity: Box,
  theme: Target,
  context: BookOpen,
  blocker: Ban,
}

export default function QuorumGraphView({
  project,
  onChatWithAgent,
}: QuorumGraphViewProps) {
  const [search, setSearch] = useState('')
  const [activeTypeFilter, setActiveTypeFilter] = useState<string | 'all'>('all')
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  // Backend node lookup table for the detail panel
  const backendNodeById = useMemo(() => {
    const map: Record<string, NonNullable<Project['graph']>['nodes'][number]> = {}
    project.graph?.nodes.forEach((n) => {
      map[n.id] = n
    })
    return map
  }, [project.graph])

  // Type histogram for the legend + filter chips
  const typeHistogram = useMemo(() => {
    const counts: Record<string, number> = {}
    project.graph?.nodes.forEach((n) => {
      counts[n.type] = (counts[n.type] || 0) + 1
    })
    return Object.entries(counts).sort((a, b) => b[1] - a[1])
  }, [project.graph])

  // Degree map for the right-panel "connections" stat
  const degree = useMemo(() => {
    const d: Record<string, number> = {}
    project.graph?.edges.forEach((e) => {
      d[e.source_id] = (d[e.source_id] || 0) + 1
      d[e.target_id] = (d[e.target_id] || 0) + 1
    })
    return d
  }, [project.graph])

  // Apply search + type filters to produce the visible d3 graph data
  const visibleGraph = useMemo<{ nodes: D3GraphNode[]; edges: D3GraphEdge[] }>(() => {
    if (!project.graph) return { nodes: [], edges: [] }
    const lcSearch = search.trim().toLowerCase()
    const filteredBackendNodes = project.graph.nodes.filter((n) => {
      if (activeTypeFilter !== 'all' && n.type !== activeTypeFilter) return false
      if (!lcSearch) return true
      return n.name.toLowerCase().includes(lcSearch)
    })
    const visibleIds = new Set(filteredBackendNodes.map((n) => n.id))
    const filteredEdges = project.graph.edges.filter(
      (e) => visibleIds.has(e.source_id) && visibleIds.has(e.target_id)
    )
    return {
      nodes: filteredBackendNodes.map((n) => ({
        id: n.id,
        name: n.name,
        type: n.type,
        description: n.description,
        is_individual: n.is_individual,
      })),
      edges: filteredEdges.map((e) => ({
        id: e.id,
        source: e.source_id,
        target: e.target_id,
        type: e.type,
        description: e.description,
      })),
    }
  }, [project.graph, search, activeTypeFilter])

  const selectedBackend = selectedNodeId ? backendNodeById[selectedNodeId] : null
  const selectedAgent = useMemo(() => {
    if (!selectedBackend || !project.agents) return null
    return project.agents.find((a) => a.source_entity_id === selectedBackend.id) || null
  }, [selectedBackend, project.agents])

  const totalNodes = project.graph?.nodes.length ?? 0
  const totalEdges = project.graph?.edges.length ?? 0

  return (
    <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_320px] min-h-0">
      {/* ============ Main canvas ============ */}
      <div className="relative flex flex-col min-w-0 min-h-0 border-r border-[var(--line)]">
        {/* Top toolbar — search */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--line)] bg-[var(--bg-soft)] flex-shrink-0">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--muted)]" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search nodes…"
              className="w-full pl-9 pr-8 py-1.5 text-xs bg-[var(--card)] border border-[var(--line)] rounded-md focus:outline-none focus:border-[var(--brand)]"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--muted)] hover:text-[var(--ink)]"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </div>
          <div className="flex-1" />
          <span className="text-[10px] font-mono text-[var(--muted)] flex-shrink-0">
            <span className="text-[var(--ink)]">{visibleGraph.nodes.length}</span> /{' '}
            {totalNodes} nodes
          </span>
        </div>

        {/* Type filter chips */}
        <div className="px-4 py-2 border-b border-[var(--line)] bg-[var(--bg-soft)] overflow-x-auto flex-shrink-0">
          <div className="flex items-center gap-1.5 min-w-max">
            <Filter className="h-3 w-3 text-[var(--muted)] flex-shrink-0" />
            <button
              onClick={() => setActiveTypeFilter('all')}
              className={`px-2 py-1 rounded text-[10px] font-mono uppercase tracking-wider transition-colors ${
                activeTypeFilter === 'all'
                  ? 'bg-[var(--brand)] text-white'
                  : 'bg-[var(--card)] text-[var(--muted)] hover:text-[var(--ink)] border border-[var(--line)]'
              }`}
            >
              All ({totalNodes})
            </button>
            {typeHistogram.map(([type, count]) => (
              <button
                key={type}
                onClick={() => setActiveTypeFilter(type)}
                className={`px-2 py-1 rounded text-[10px] font-mono transition-colors ${
                  activeTypeFilter === type
                    ? 'bg-[var(--brand)] text-white'
                    : 'bg-[var(--card)] text-[var(--muted)] hover:text-[var(--ink)] border border-[var(--line)]'
                }`}
              >
                {type} ({count})
              </button>
            ))}
          </div>
        </div>

        {/* The d3 canvas */}
        <div className="flex-1 min-h-0">
          <GraphCanvasD3
            nodes={visibleGraph.nodes}
            edges={visibleGraph.edges}
            selectedNodeId={selectedNodeId}
            onNodeClick={(node) => setSelectedNodeId(node.id)}
            onNodeHover={() => {}}
            height="h-full"
            showLegend
          />
        </div>
      </div>

      {/* ============ Right sidebar ============ */}
      <aside className="overflow-y-auto bg-[var(--bg-soft)] flex flex-col min-h-0">
        {selectedBackend ? (
          <NodeDetailPanel
            backend={selectedBackend}
            agent={selectedAgent}
            degreeCount={degree[selectedBackend.id] || 0}
            onChatWithAgent={onChatWithAgent}
            onClose={() => setSelectedNodeId(null)}
          />
        ) : (
          <GraphOverviewPanel
            project={project}
            typeHistogram={typeHistogram}
            totalNodes={totalNodes}
            totalEdges={totalEdges}
          />
        )}
      </aside>
    </div>
  )
}

// ============================================
// Sidebar: graph overview (no node selected)
// ============================================
function GraphOverviewPanel({
  project,
  typeHistogram,
  totalNodes,
  totalEdges,
}: {
  project: Project
  typeHistogram: [string, number][]
  totalNodes: number
  totalEdges: number
}) {
  return (
    <div className="p-5 space-y-5">
      <div>
        <div className="flex items-center gap-2 mb-2">
          <Network className="h-3.5 w-3.5 text-[var(--brand)]" />
          <span className="label-mono">Graph overview</span>
        </div>
        <h3 className="font-display text-lg font-medium text-[var(--ink)] tracking-tight">
          {project.title}
        </h3>
        <p className="mt-2 text-xs text-[var(--muted)] leading-relaxed line-clamp-3">
          {project.brief}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="bg-[var(--card)] border border-[var(--line)] rounded-md p-3">
          <p className="label-mono">Nodes</p>
          <p className="font-display text-2xl font-medium text-[var(--ink)] mt-1">
            {totalNodes}
          </p>
        </div>
        <div className="bg-[var(--card)] border border-[var(--line)] rounded-md p-3">
          <p className="label-mono">Edges</p>
          <p className="font-display text-2xl font-medium text-[var(--ink)] mt-1">
            {totalEdges}
          </p>
        </div>
      </div>

      <div>
        <p className="label-mono mb-2">Schema distribution</p>
        <div className="space-y-1.5">
          {typeHistogram.map(([type, count]) => {
            const pct = totalNodes > 0 ? (count / totalNodes) * 100 : 0
            return (
              <div key={type} className="space-y-1">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-mono text-[var(--ink)] truncate">{type}</span>
                  <span className="font-mono text-[var(--muted)] tabular-nums">
                    {count}
                  </span>
                </div>
                <div className="h-1 bg-[var(--bg-strong)] rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-[var(--brand)]"
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.5 }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="bg-[var(--card)] border border-[var(--line)] rounded-md p-3 text-[11px] text-[var(--muted)] leading-relaxed">
        Click any node to see its details. Drag nodes to rearrange. Scroll to zoom,
        Shift+drag to pan.
      </div>
    </div>
  )
}

// ============================================
// Sidebar: node detail
// ============================================
function NodeDetailPanel({
  backend,
  agent,
  degreeCount,
  onChatWithAgent,
  onClose,
}: {
  backend: NonNullable<Project['graph']>['nodes'][number]
  agent: AgentProfile | null
  degreeCount: number
  onChatWithAgent?: (agent: AgentProfile) => void
  onClose: () => void
}) {
  const Icon = backend.is_individual ? Bot : Box

  return (
    <motion.div
      key={backend.id}
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2 }}
      className="p-5 space-y-5"
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <Icon className="h-3.5 w-3.5 text-[var(--brand)]" />
            <span className="label-mono">Selected node</span>
          </div>
          <h3 className="font-display text-xl font-medium text-[var(--ink)] tracking-tight break-words">
            {backend.name}
          </h3>
          <p className="mt-1 text-[10px] font-mono uppercase tracking-wider text-[var(--brand)]">
            {backend.type}
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-[var(--muted)] hover:text-[var(--ink)] text-sm font-mono"
          aria-label="Close"
        >
          ×
        </button>
      </div>

      {backend.description && (
        <div>
          <p className="label-mono mb-2">Description</p>
          <p className="text-xs text-[var(--ink)] leading-relaxed">{backend.description}</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        <div className="bg-[var(--card)] border border-[var(--line)] rounded-md p-3">
          <p className="label-mono">Connections</p>
          <p className="font-display text-2xl font-medium text-[var(--ink)] mt-1">
            {degreeCount}
          </p>
        </div>
        <div className="bg-[var(--card)] border border-[var(--line)] rounded-md p-3">
          <p className="label-mono">Type</p>
          <p className="text-xs font-medium text-[var(--ink)] mt-1.5">
            {backend.is_individual ? 'Individual' : 'Group/Concept'}
          </p>
        </div>
      </div>

      {agent ? (
        <div className="bg-[var(--brand-tint)] border border-[var(--brand)] rounded-md p-4">
          <div className="flex items-center gap-2 mb-2">
            <Bot className="h-3.5 w-3.5 text-[var(--brand)]" />
            <span className="label-mono text-[var(--brand)]">Linked agent</span>
          </div>
          <p className="font-display text-sm font-medium text-[var(--ink)]">
            {agent.name}
          </p>
          <p className="text-[10px] font-mono text-[var(--muted)] mt-0.5">
            @{agent.user_name} · {agent.role}
          </p>
          <p className="text-[11px] text-[var(--muted)] mt-2 leading-relaxed line-clamp-3">
            {agent.bio}
          </p>
          {onChatWithAgent && (
            <button
              onClick={() => onChatWithAgent(agent)}
              className="mt-3 w-full inline-flex items-center justify-center gap-2 px-3 py-2 bg-[var(--brand)] text-white text-xs font-medium rounded-md hover:bg-[var(--ink)] transition-colors"
            >
              Chat with this agent
              <ArrowRight className="h-3 w-3" />
            </button>
          )}
        </div>
      ) : (
        <div className="bg-[var(--card)] border border-[var(--line)] rounded-md p-3 text-[11px] text-[var(--muted)] leading-relaxed">
          This entity is in the graph but doesn't have an associated agent yet (it
          may be a concept, event, or document, or env setup hasn't run).
        </div>
      )}
    </motion.div>
  )
}
