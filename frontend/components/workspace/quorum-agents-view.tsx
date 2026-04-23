'use client'

import React, { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Bot,
  Search,
  X,
  Users,
  ThumbsUp,
  ThumbsDown,
  Minus,
  Sparkles,
  ArrowRight,
  Filter,
} from 'lucide-react'

import type { Project, AgentProfile } from '@/types/pipeline'

interface QuorumAgentsViewProps {
  project: Project
  onChatWithAgent: (agent: AgentProfile) => void
}

const STANCE_META = {
  support: { Icon: ThumbsUp, color: '#00C851', label: 'Support' },
  oppose: { Icon: ThumbsDown, color: '#ff4444', label: 'Oppose' },
  neutral: { Icon: Minus, color: '#9b9895', label: 'Neutral' },
} as const

// Stable hash → color so each agent always gets the same avatar tone
function colorForAgent(name: string): string {
  const palette = [
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
  ]
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = (hash << 5) - hash + name.charCodeAt(i)
    hash |= 0
  }
  return palette[Math.abs(hash) % palette.length]
}

export default function QuorumAgentsView({ project, onChatWithAgent }: QuorumAgentsViewProps) {
  const agents = project.agents ?? []

  const [search, setSearch] = useState('')
  const [stanceFilter, setStanceFilter] = useState<'all' | 'support' | 'oppose' | 'neutral'>(
    'all'
  )

  // Stance distribution for the header
  const stanceCounts = useMemo(() => {
    const counts = { support: 0, oppose: 0, neutral: 0 }
    agents.forEach((a) => {
      counts[a.stance] = (counts[a.stance] || 0) + 1
    })
    return counts
  }, [agents])

  // Apply filters
  const filtered = useMemo(() => {
    const lc = search.trim().toLowerCase()
    return agents.filter((a) => {
      if (stanceFilter !== 'all' && a.stance !== stanceFilter) return false
      if (!lc) return true
      return (
        a.name.toLowerCase().includes(lc) ||
        a.user_name.toLowerCase().includes(lc) ||
        a.role.toLowerCase().includes(lc) ||
        (a.expertise || []).some((e) => e.toLowerCase().includes(lc))
      )
    })
  }, [agents, search, stanceFilter])

  if (!agents.length) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 bg-[var(--bg-soft)]">
        <div className="max-w-md text-center">
          <div className="inline-flex h-14 w-14 items-center justify-center rounded-md bg-[var(--card)] border border-[var(--line)] mb-4">
            <Users className="h-6 w-6 text-[var(--muted)]" />
          </div>
          <h3 className="font-display text-lg font-medium text-[var(--ink)]">
            No agents yet
          </h3>
          <p className="mt-2 text-sm text-[var(--muted)] leading-relaxed">
            Run <span className="font-mono text-[var(--brand)]">Stage 03 — Environment Setup</span>{' '}
            on the workbench to instantiate one agent per real-world entity in the graph.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-[var(--bg-soft)]">
      {/* ============ Toolbar ============ */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-[var(--line)] bg-[var(--bg)] flex-shrink-0">
        <div className="flex items-center gap-2">
          <Sparkles className="h-3.5 w-3.5 text-[var(--brand)]" />
          <span className="label-mono">{agents.length} agents</span>
        </div>

        <div className="w-px h-5 bg-[var(--line)]" />

        {/* Stance distribution */}
        <div className="flex items-center gap-3 text-[11px] font-mono">
          <span className="inline-flex items-center gap-1 text-[#00C851]">
            <ThumbsUp className="h-3 w-3" />
            {stanceCounts.support}
          </span>
          <span className="inline-flex items-center gap-1 text-[#ff4444]">
            <ThumbsDown className="h-3 w-3" />
            {stanceCounts.oppose}
          </span>
          <span className="inline-flex items-center gap-1 text-[var(--muted)]">
            <Minus className="h-3 w-3" />
            {stanceCounts.neutral}
          </span>
        </div>

        <div className="flex-1" />

        {/* Search */}
        <div className="relative w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--muted)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, role, expertise…"
            className="w-full pl-9 pr-8 py-1.5 text-xs bg-[var(--bg-soft)] border border-[var(--line)] rounded-md focus:outline-none focus:border-[var(--brand)]"
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
      </div>

      {/* Stance filter chips */}
      <div className="flex items-center gap-1.5 px-6 py-2 border-b border-[var(--line)] bg-[var(--bg)] flex-shrink-0">
        <Filter className="h-3 w-3 text-[var(--muted)]" />
        {(['all', 'support', 'oppose', 'neutral'] as const).map((s) => {
          const active = stanceFilter === s
          const meta = s === 'all' ? null : STANCE_META[s]
          return (
            <button
              key={s}
              onClick={() => setStanceFilter(s)}
              className={`px-2.5 py-1 rounded text-[10px] font-mono uppercase tracking-wider inline-flex items-center gap-1.5 transition-colors ${
                active
                  ? 'bg-[var(--brand)] text-white'
                  : 'bg-[var(--bg-soft)] text-[var(--muted)] hover:text-[var(--ink)] border border-[var(--line)]'
              }`}
            >
              {meta && <meta.Icon className="h-2.5 w-2.5" />}
              {s === 'all' ? `All (${agents.length})` : `${s} (${stanceCounts[s]})`}
            </button>
          )
        })}
        <div className="flex-1" />
        <span className="text-[10px] font-mono text-[var(--muted)]">
          showing <span className="text-[var(--ink)]">{filtered.length}</span>
        </span>
      </div>

      {/* ============ Grid ============ */}
      <div className="flex-1 overflow-y-auto p-6">
        {filtered.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-sm text-[var(--muted)]">No agents match the current filters.</p>
          </div>
        ) : (
          <div className="grid gap-3 grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {filtered.map((agent, idx) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                index={idx}
                onChat={() => onChatWithAgent(agent)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ============================================
// Agent card
// ============================================
function AgentCard({
  agent,
  index,
  onChat,
}: {
  agent: AgentProfile
  index: number
  onChat: () => void
}) {
  const color = colorForAgent(agent.name)
  const stance = STANCE_META[agent.stance] || STANCE_META.neutral

  return (
    <motion.button
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: Math.min(index * 0.02, 0.4) }}
      onClick={onChat}
      className="group relative bg-[var(--card)] border border-[var(--line)] rounded-md p-4 text-left hover:border-[var(--brand)] hover:shadow-md transition-all"
    >
      {/* Top: avatar + name + stance */}
      <div className="flex items-start gap-3">
        <div
          className="h-10 w-10 rounded-md flex items-center justify-center flex-shrink-0"
          style={{ background: color }}
        >
          <Bot className="h-5 w-5 text-white" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-display text-sm font-medium text-[var(--ink)] truncate">
            {agent.name}
          </p>
          <p className="text-[10px] font-mono text-[var(--muted)] truncate">
            @{agent.user_name}
          </p>
        </div>
        <div
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider"
          style={{ background: `${stance.color}22`, color: stance.color }}
        >
          <stance.Icon className="h-2.5 w-2.5" />
          {stance.label}
        </div>
      </div>

      {/* Role */}
      <p className="mt-3 text-[11px] font-medium text-[var(--ink)]">{agent.role}</p>

      {/* Bio */}
      {agent.bio && (
        <p className="mt-1 text-[11px] text-[var(--muted)] leading-relaxed line-clamp-2">
          {agent.bio}
        </p>
      )}

      {/* Personality bars */}
      <div className="mt-3 grid grid-cols-3 gap-2">
        <PersonalityBar label="opt" value={agent.optimism} color={color} />
        <PersonalityBar label="risk" value={agent.risk_tolerance} color={color} />
        <PersonalityBar label="caut" value={agent.caution} color={color} />
      </div>

      {/* Bias */}
      {agent.bias && (
        <p className="mt-3 text-[10px] font-mono text-[var(--muted)] line-clamp-1">
          bias: <span className="text-[var(--ink)]">{agent.bias}</span>
        </p>
      )}

      {/* Expertise tags */}
      {agent.expertise && agent.expertise.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {agent.expertise.slice(0, 3).map((e) => (
            <span
              key={e}
              className="px-1.5 py-0.5 rounded bg-[var(--bg-soft)] border border-[var(--line)] text-[9px] font-mono text-[var(--muted)]"
            >
              {e}
            </span>
          ))}
          {agent.expertise.length > 3 && (
            <span className="px-1.5 py-0.5 text-[9px] font-mono text-[var(--muted)]">
              +{agent.expertise.length - 3}
            </span>
          )}
        </div>
      )}

      {/* Hover hint */}
      <div className="mt-3 pt-3 border-t border-[var(--line-soft)] flex items-center justify-between">
        <span className="text-[10px] font-mono text-[var(--muted)]">
          Click to chat
        </span>
        <ArrowRight className="h-3 w-3 text-[var(--muted)] group-hover:text-[var(--brand)] group-hover:translate-x-0.5 transition-all" />
      </div>
    </motion.button>
  )
}

function PersonalityBar({
  label,
  value,
  color,
}: {
  label: string
  value: number
  color: string
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-[9px] font-mono uppercase text-[var(--muted)]">{label}</span>
        <span className="text-[9px] font-mono text-[var(--muted)] tabular-nums">
          {(value * 100).toFixed(0)}
        </span>
      </div>
      <div className="h-1 bg-[var(--bg-strong)] rounded-full overflow-hidden">
        <div
          className="h-full"
          style={{ width: `${value * 100}%`, background: color }}
        />
      </div>
    </div>
  )
}
