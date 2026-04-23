'use client'

import React, { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Bot, ChevronDown, Settings2 } from 'lucide-react'
import StageCard, { StageActionButton } from '@/components/pipeline/stage-card'
import type {
  AgentActivityConfig,
  PlatformConfig,
  SimulationParameters,
  TimeSimulationConfig,
} from '@/types/pipeline'
import type { StageStatus } from '@/components/pipeline/stage-card'

interface StageConfigCardProps {
  number: string
  status: StageStatus
  params: SimulationParameters | null
  onGenerate?: () => void
  loading?: boolean
}

export default function StageConfigCard({
  number,
  status,
  params,
  onGenerate,
  loading = false,
}: StageConfigCardProps) {
  return (
    <StageCard
      number={number}
      title="Generate Config"
      endpoint="/api/projects/{id}/simulation/prepare"
      description="LLM generates dual-platform simulation config parameters based on simulation requirements and agent profiles."
      status={status}
      action={
        !params && onGenerate ? (
          <StageActionButton onClick={onGenerate} disabled={loading}>
            {loading ? 'Generating config…' : 'Generate simulation config'}
          </StageActionButton>
        ) : undefined
      }
    >
      {params && (
        <div className="space-y-5">
          <TimeConfigGrid time={params.time_config} />
          <HourMultiplierRows time={params.time_config} />
          <PlatformConfigGrid feed={params.feed_config} community={params.community_config} />
          <AgentConfigGrid agents={params.agent_configs} />
          {params.generation_reasoning && (
            <ReasoningCallout reasoning={params.generation_reasoning} />
          )}
        </div>
      )}
    </StageCard>
  )
}

// ============================================
// Time config — 4 stat boxes in a row
// ============================================
function TimeConfigGrid({ time }: { time: TimeSimulationConfig }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      <StatBox label="Duration" value={`${time.total_simulation_hours}`} unit="hours" />
      <StatBox label="Round duration" value={`${time.minutes_per_round}`} unit="min" />
      <StatBox
        label="Total rounds"
        value={`${Math.round((time.total_simulation_hours * 60) / time.minutes_per_round)}`}
        unit="rounds"
      />
      <StatBox
        label="Active / hour"
        value={`${time.agents_per_hour_min}-${time.agents_per_hour_max}`}
        unit=""
      />
    </div>
  )
}

function StatBox({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="bg-[var(--bg-soft)] border border-[var(--line)] rounded-md p-3">
      <p className="label-mono">{label}</p>
      <p className="font-display text-xl font-medium text-[var(--ink)] mt-1 leading-none tabular-nums">
        {value}
        {unit && (
          <span className="text-[10px] font-mono text-[var(--muted)] ml-1.5 font-normal">
            {unit}
          </span>
        )}
      </p>
    </div>
  )
}

// ============================================
// Hour multipliers — 4 rows with hour ranges + multiplier pills
// ============================================
function HourMultiplierRows({ time }: { time: TimeSimulationConfig }) {
  const rows = [
    {
      label: 'Peak hours',
      hours: time.peak_hours,
      multiplier: time.peak_activity_multiplier,
      tone: 'brand',
    },
    {
      label: 'Work hours',
      hours: time.work_hours,
      multiplier: time.work_activity_multiplier,
      tone: 'neutral',
    },
    {
      label: 'Morning hours',
      hours: time.morning_hours,
      multiplier: time.morning_activity_multiplier,
      tone: 'neutral',
    },
    {
      label: 'Off-peak hours',
      hours: time.off_peak_hours,
      multiplier: time.off_peak_activity_multiplier,
      tone: 'muted',
    },
  ] as const
  return (
    <div className="space-y-1">
      {rows.map((row) => (
        <div
          key={row.label}
          className="flex items-center justify-between bg-[var(--bg-soft)] border border-[var(--line)] rounded-md px-3 py-2"
        >
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-[11px] font-medium text-[var(--ink)] flex-shrink-0">
              {row.label}
            </span>
            <span className="text-[10px] font-mono text-[var(--muted)] truncate">
              {formatHours(row.hours)}
            </span>
          </div>
          <span
            className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
              row.tone === 'brand'
                ? 'bg-[var(--brand-soft)] text-[var(--brand)]'
                : row.tone === 'muted'
                  ? 'bg-[var(--bg-strong)] text-[var(--muted)]'
                  : 'bg-[var(--card)] border border-[var(--line)] text-[var(--ink)]'
            }`}
          >
            ×{row.multiplier}
          </span>
        </div>
      ))}
    </div>
  )
}

function formatHours(hours: number[]): string {
  if (!hours || hours.length === 0) return ''
  // Try to compress consecutive ranges into "9:00-18:00" form
  if (hours.length === 1) return `${hours[0]}:00`
  const sorted = [...hours].sort((a, b) => a - b)
  const isContig = sorted.every((h, i) => i === 0 || h === sorted[i - 1] + 1)
  if (isContig) {
    return `${sorted[0]}:00-${sorted[sorted.length - 1]}:00`
  }
  return sorted.map((h) => `${h}:00`).join(', ')
}

// ============================================
// Platform configs — 2 columns
// ============================================
function PlatformConfigGrid({
  feed,
  community,
}: {
  feed: PlatformConfig | null
  community: PlatformConfig | null
}) {
  if (!feed && !community) return null
  return (
    <div>
      <p className="label-mono mb-2">Recommendation algorithm config</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {feed && <PlatformPanel title="Platform 1: Feed" cfg={feed} />}
        {community && <PlatformPanel title="Platform 2: Community" cfg={community} />}
      </div>
    </div>
  )
}

function PlatformPanel({ title, cfg }: { title: string; cfg: PlatformConfig }) {
  const rows = [
    { label: 'Recency weight', value: cfg.recency_weight.toFixed(1) },
    { label: 'Popularity weight', value: cfg.popularity_weight.toFixed(1) },
    { label: 'Relevance weight', value: cfg.relevance_weight.toFixed(1) },
    { label: 'Viral threshold', value: `${cfg.viral_threshold}` },
    { label: 'Echo chamber strength', value: cfg.echo_chamber_strength.toFixed(1) },
  ]
  return (
    <div className="bg-[var(--bg-soft)] border border-[var(--line)] rounded-md p-3">
      <p className="text-[11px] font-medium text-[var(--ink)] mb-2">{title}</p>
      <div className="space-y-1">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-[var(--brand)]">{r.label}</span>
            <span className="text-[10px] font-mono text-[var(--ink)] tabular-nums">
              {r.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ============================================
// Agent config grid — collapsible (showing first 6)
// ============================================
function AgentConfigGrid({ agents }: { agents: AgentActivityConfig[] }) {
  const [showAll, setShowAll] = useState(false)
  const visible = showAll ? agents : agents.slice(0, 6)

  if (agents.length === 0) return null

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="label-mono">Agent config</p>
        <span className="text-[10px] font-mono text-[var(--muted)]">
          {agents.length} agents
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-[440px] overflow-y-auto pr-1">
        {visible.map((a) => (
          <AgentConfigPanel key={a.agent_id} agent={a} />
        ))}
      </div>
      {agents.length > 6 && (
        <button
          onClick={() => setShowAll(!showAll)}
          className="mt-2 w-full inline-flex items-center justify-center gap-1.5 py-1.5 text-[10px] font-mono uppercase tracking-wider text-[var(--muted)] hover:text-[var(--brand)] transition-colors"
        >
          {showAll ? 'Show first 6' : `Show all ${agents.length}`}
          <ChevronDown className={`h-3 w-3 transition-transform ${showAll ? 'rotate-180' : ''}`} />
        </button>
      )}
    </div>
  )
}

function AgentConfigPanel({ agent }: { agent: AgentActivityConfig }) {
  const stanceColor =
    agent.stance === 'supportive'
      ? '#00C851'
      : agent.stance === 'opposing'
        ? '#ff4444'
        : '#9b9895'
  return (
    <div className="bg-[var(--bg-soft)] border border-[var(--line)] rounded-md p-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-mono uppercase tracking-wider text-[var(--muted)]">
            Agent {agent.agent_id}
          </p>
          <p className="text-[11px] font-medium text-[var(--ink)] truncate mt-0.5">
            {agent.entity_name}
          </p>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <span className="text-[9px] font-mono uppercase px-1 py-0.5 rounded bg-[var(--card)] border border-[var(--line)] text-[var(--muted)]">
            {agent.entity_type}
          </span>
          <span
            className="text-[9px] font-mono uppercase px-1 py-0.5 rounded"
            style={{ background: `${stanceColor}22`, color: stanceColor }}
          >
            {agent.stance}
          </span>
        </div>
      </div>

      {/* Active hours bar */}
      <div className="mb-2">
        <p className="text-[9px] font-mono uppercase text-[var(--muted)] mb-1">Active hours</p>
        <ActiveHoursBar hours={agent.active_hours} />
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-3 gap-1.5 text-[10px]">
        <Stat label="Posts/hr" value={agent.posts_per_hour.toFixed(1)} />
        <Stat label="Comments/hr" value={agent.comments_per_hour.toFixed(1)} />
        <Stat
          label="Delay"
          value={`${agent.response_delay_min}-${agent.response_delay_max}m`}
        />
        <Stat
          label="Activity"
          value={`${(agent.activity_level * 100).toFixed(0)}%`}
          bar={agent.activity_level}
        />
        <Stat
          label="Sentiment"
          value={
            agent.sentiment_bias > 0
              ? `+${agent.sentiment_bias.toFixed(1)}`
              : agent.sentiment_bias.toFixed(1)
          }
        />
        <Stat label="Influence" value={agent.influence_weight.toFixed(1)} />
      </div>
    </div>
  )
}

function ActiveHoursBar({ hours }: { hours: number[] }) {
  const set = new Set(hours)
  return (
    <div className="flex items-center gap-[1px]">
      {Array.from({ length: 24 }, (_, h) => (
        <span
          key={h}
          className={`h-2 flex-1 rounded-sm ${
            set.has(h) ? 'bg-[var(--brand)]' : 'bg-[var(--bg-strong)]'
          }`}
          title={`${h}:00`}
        />
      ))}
    </div>
  )
}

function Stat({
  label,
  value,
  bar,
}: {
  label: string
  value: string
  bar?: number
}) {
  return (
    <div>
      <p className="text-[9px] font-mono text-[var(--muted)]">{label}</p>
      <p className="text-[10px] font-medium text-[var(--ink)] tabular-nums">{value}</p>
      {bar !== undefined && (
        <div className="mt-0.5 h-0.5 bg-[var(--bg-strong)] rounded overflow-hidden">
          <div
            className="h-full bg-[var(--brand)]"
            style={{ width: `${Math.min(bar * 100, 100)}%` }}
          />
        </div>
      )}
    </div>
  )
}

// ============================================
// LLM reasoning callout
// ============================================
function ReasoningCallout({ reasoning }: { reasoning: string }) {
  return (
    <div className="bg-[var(--bg-soft)] border border-[var(--line)] rounded-md p-3">
      <p className="label-mono mb-2">LLM config reasoning</p>
      <p className="text-[11px] text-[var(--muted)] leading-relaxed whitespace-pre-line">
        {reasoning}
      </p>
    </div>
  )
}
