'use client'

import React, { useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Bot, MessageSquare } from 'lucide-react'
import type { AgentProfile } from '@/types/pipeline'

interface AgentDetailModalProps {
  agent: AgentProfile | null
  onClose: () => void
  onChat?: (agent: AgentProfile) => void
}

// ============================================
// Persona section parser
// ============================================
//
// The backend persona prompt asks the LLM to write the long persona text with
// `\n\n` between four labeled sections: Background, Behavior Profile, Unique
// Memory, Social Network. We parse those out for the detailed-persona quad.
//
// If the LLM didn't follow the structure, we fall back to showing the entire
// persona as the "Long persona" block.

const SECTION_LABELS = [
  'Background',
  'Behavior Profile',
  'Unique Memory',
  'Social Network',
] as const

type SectionLabel = (typeof SECTION_LABELS)[number]

interface ParsedPersona {
  sections: Partial<Record<SectionLabel, string>>
  remainder: string
}

function parsePersona(text: string): ParsedPersona {
  if (!text) return { sections: {}, remainder: '' }
  const sections: Partial<Record<SectionLabel, string>> = {}
  let remainder = text

  // Match "Section Name: ..." up to the next section label or end of string
  const labelPattern = SECTION_LABELS.map((l) => l.replace(/ /g, '\\s*')).join('|')
  const sectionRegex = new RegExp(
    `(?:^|\\n)\\s*(${labelPattern})\\s*:\\s*([\\s\\S]*?)(?=\\n\\s*(?:${labelPattern})\\s*:|$)`,
    'gi'
  )

  const matches: { label: SectionLabel; body: string; idx: number }[] = []
  let m: RegExpExecArray | null
  while ((m = sectionRegex.exec(text)) !== null) {
    const rawLabel = m[1].replace(/\s+/g, ' ').trim()
    const matched = SECTION_LABELS.find(
      (l) => l.toLowerCase() === rawLabel.toLowerCase()
    )
    if (!matched) continue
    matches.push({ label: matched, body: m[2].trim(), idx: m.index })
  }

  matches.forEach((m) => {
    sections[m.label] = m.body
  })

  // Remainder = anything before the first matched section
  if (matches.length > 0) {
    const firstIdx = Math.min(...matches.map((m) => m.idx))
    remainder = text.slice(0, firstIdx).trim()
  }

  return { sections, remainder }
}

// ============================================
// Stable color hash from agent name
// ============================================
function colorForAgent(name: string): string {
  const palette = [
    '#FF4500', '#00B0FF', '#00C851', '#9b51e0', '#f59e0b',
    '#0ea5e9', '#ec4899', '#10b981', '#6366f1', '#ef4444',
  ]
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = (hash << 5) - hash + name.charCodeAt(i)
    hash |= 0
  }
  return palette[Math.abs(hash) % palette.length]
}

// ============================================
// Component
// ============================================
export default function AgentDetailModal({
  agent,
  onClose,
  onChat,
}: AgentDetailModalProps) {
  const parsed = useMemo(() => parsePersona(agent?.persona ?? ''), [agent?.persona])
  const color = useMemo(() => (agent ? colorForAgent(agent.name) : '#9b9895'), [agent])

  if (!agent) return null

  const stanceColor =
    agent.stance === 'support'
      ? '#00C851'
      : agent.stance === 'oppose'
        ? '#ff4444'
        : '#9b9895'

  return (
    <AnimatePresence>
      {agent && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
            onClick={onClose}
          />
          {/* Modal */}
          <motion.div
            key="modal"
            initial={{ opacity: 0, scale: 0.95, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 12 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none"
          >
            <div className="bg-[var(--card)] border border-[var(--line-strong)] rounded-lg shadow-xl w-full max-w-2xl max-h-[88vh] overflow-hidden flex flex-col pointer-events-auto">
              {/* Header */}
              <header className="px-6 py-5 border-b border-[var(--line)] bg-[var(--bg-soft)] flex items-start justify-between gap-3 flex-shrink-0">
                <div className="flex items-start gap-3 min-w-0 flex-1">
                  <div
                    className="h-12 w-12 rounded-md flex items-center justify-center flex-shrink-0"
                    style={{ background: color }}
                  >
                    <Bot className="h-6 w-6 text-white" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-[11px] font-mono text-[var(--muted)] truncate">
                      {agent.user_name} · @{agent.name}
                    </p>
                    <h2 className="font-display text-xl font-medium text-[var(--ink)] tracking-tight truncate">
                      {agent.name}
                    </h2>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-[var(--bg)] border border-[var(--line)] text-[var(--muted)]">
                        {agent.role}
                      </span>
                      <span
                        className="text-[10px] font-mono uppercase px-2 py-0.5 rounded"
                        style={{ background: `${stanceColor}22`, color: stanceColor }}
                      >
                        {agent.stance}
                      </span>
                    </div>
                  </div>
                </div>
                <button
                  onClick={onClose}
                  className="text-[var(--muted)] hover:text-[var(--ink)] p-1 flex-shrink-0"
                  aria-label="Close"
                >
                  <X className="h-5 w-5" />
                </button>
              </header>

              {/* Body — scrolls */}
              <div className="flex-1 overflow-y-auto p-6 space-y-5">
                {/* Apparent demographics quad */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <DemoBox
                    label="Apparent age"
                    value={agent.age != null ? `${agent.age} yrs` : '—'}
                  />
                  <DemoBox
                    label="Apparent gender"
                    value={agent.gender ? capitalize(agent.gender) : '—'}
                  />
                  <DemoBox
                    label="Country / region"
                    value={agent.country ?? '—'}
                  />
                  <DemoBox
                    label="Apparent MBTI"
                    value={agent.mbti ?? '—'}
                    accent
                  />
                </div>

                {/* Bio */}
                {agent.bio && (
                  <div>
                    <p className="label-mono mb-2">Bio</p>
                    <div className="bg-[var(--bg-soft)] border border-[var(--line)] rounded-md p-4">
                      <p className="text-sm text-[var(--ink)] leading-relaxed">{agent.bio}</p>
                    </div>
                  </div>
                )}

                {/* Related topics */}
                {agent.interested_topics.length > 0 && (
                  <div>
                    <p className="label-mono mb-2">Related topics</p>
                    <div className="flex flex-wrap gap-1.5">
                      {agent.interested_topics.map((t) => (
                        <span
                          key={t}
                          className="px-2 py-1 rounded-full bg-[var(--accent-blue)]/14 border border-[var(--accent-blue)]/30 text-[11px] text-[var(--accent-blue)]"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Detailed persona quad */}
                {(parsed.sections.Background ||
                  parsed.sections['Behavior Profile'] ||
                  parsed.sections['Unique Memory'] ||
                  parsed.sections['Social Network']) && (
                  <div>
                    <p className="label-mono mb-2">Detailed persona</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <PersonaSectionCard
                        title="Background"
                        body={parsed.sections.Background}
                        fallback="Personal background and experience related to the topic."
                      />
                      <PersonaSectionCard
                        title="Behavior Profile"
                        body={parsed.sections['Behavior Profile']}
                        fallback="Argumentation style and language patterns."
                      />
                      <PersonaSectionCard
                        title="Unique Memory"
                        body={parsed.sections['Unique Memory']}
                        fallback="Specific experience or precedent they would reference."
                      />
                      <PersonaSectionCard
                        title="Social Network"
                        body={parsed.sections['Social Network']}
                        fallback="Allies, opponents, audience, institutional ties."
                      />
                    </div>
                  </div>
                )}

                {/* Personality bars */}
                <div>
                  <p className="label-mono mb-2">Personality</p>
                  <div className="grid grid-cols-3 gap-2">
                    <PersonalityBar label="Optimism" value={agent.optimism} color={color} />
                    <PersonalityBar
                      label="Risk tolerance"
                      value={agent.risk_tolerance}
                      color={color}
                    />
                    <PersonalityBar label="Caution" value={agent.caution} color={color} />
                  </div>
                  {agent.bias && (
                    <p className="text-[10px] font-mono text-[var(--muted)] mt-3">
                      bias: <span className="text-[var(--ink)]">{agent.bias}</span>
                    </p>
                  )}
                </div>

                {/* Long persona body — only if there was content not parsed into sections */}
                {parsed.remainder && (
                  <div>
                    <p className="label-mono mb-2">Persona summary</p>
                    <div className="bg-[var(--bg-soft)] border border-[var(--line)] rounded-md p-4">
                      <p className="text-[12px] text-[var(--ink)] leading-relaxed whitespace-pre-line">
                        {parsed.remainder}
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Footer */}
              {onChat && (
                <footer className="px-6 py-4 border-t border-[var(--line)] bg-[var(--bg-soft)] flex items-center justify-between flex-shrink-0">
                  <p className="text-[10px] font-mono text-[var(--muted)]">
                    Source: {agent.source_entity_type ?? 'unknown'} · {agent.profession ?? '—'}
                  </p>
                  <button
                    onClick={() => {
                      onChat(agent)
                      onClose()
                    }}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--brand)] text-white rounded-md text-xs font-medium hover:bg-[var(--ink)] transition-colors"
                  >
                    <MessageSquare className="h-3.5 w-3.5" />
                    Chat with this agent
                  </button>
                </footer>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

// ============================================
// Subcomponents
// ============================================

function DemoBox({
  label,
  value,
  accent = false,
}: {
  label: string
  value: string
  accent?: boolean
}) {
  return (
    <div className="bg-[var(--bg-soft)] border border-[var(--line)] rounded-md p-3">
      <p className="label-mono">{label}</p>
      <p
        className={`text-sm font-medium mt-1 ${
          accent ? 'text-[var(--brand)]' : 'text-[var(--ink)]'
        }`}
      >
        {value}
      </p>
    </div>
  )
}

function PersonaSectionCard({
  title,
  body,
  fallback,
}: {
  title: string
  body?: string
  fallback: string
}) {
  return (
    <div className="bg-[var(--bg-soft)] border border-[var(--line)] rounded-md p-3">
      <p className="text-[11px] font-medium text-[var(--ink)]">{title}</p>
      <p className="text-[11px] text-[var(--muted)] mt-1 leading-relaxed">
        {body || fallback}
      </p>
    </div>
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
    <div className="bg-[var(--bg-soft)] border border-[var(--line)] rounded-md p-3">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] font-mono uppercase text-[var(--muted)]">{label}</span>
        <span className="text-[10px] font-mono text-[var(--ink)] tabular-nums">
          {(value * 100).toFixed(0)}
        </span>
      </div>
      <div className="h-1 bg-[var(--bg-strong)] rounded-full overflow-hidden">
        <div className="h-full" style={{ width: `${value * 100}%`, background: color }} />
      </div>
    </div>
  )
}

function capitalize(s: string): string {
  if (!s) return s
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase()
}
