'use client'

import React, { useState } from 'react'
import { SimulationConfig } from '@/types/simulation'
import { motion } from 'framer-motion'
import {
  Play,
  Loader2,
  Sparkles,
  Settings2,
  LineChart,
  Scale,
  Palette,
  Hexagon,
} from 'lucide-react'

interface ControlPanelProps {
  onInitialize: (config: SimulationConfig) => void
  onStop?: () => void
  isRunning?: boolean
  isLoading?: boolean
}

const domains = [
  { id: 'execution', label: 'Execution', Icon: Settings2, desc: 'Delivery and project risk' },
  { id: 'finance', label: 'Finance', Icon: LineChart, desc: 'Forecasting and modeling' },
  { id: 'policy', label: 'Policy', Icon: Scale, desc: 'Governance and impact' },
  { id: 'creative', label: 'Creative', Icon: Palette, desc: 'Design and ideation' },
  { id: 'generic', label: 'Generic', Icon: Hexagon, desc: 'Any topic, any domain' },
] as const

export default function ControlPanel({
  onInitialize,
  onStop,
  isRunning = false,
  isLoading = false,
}: ControlPanelProps) {
  const [domain, setDomain] = useState<'execution' | 'finance' | 'policy' | 'creative' | 'generic'>(
    'generic'
  )
  const [brief, setBrief] = useState('')
  const [constraints, setConstraints] = useState('')
  const [rounds, setRounds] = useState(3)
  const [agentCount, setAgentCount] = useState(6)
  const [complexity, setComplexity] = useState<'low' | 'medium' | 'high'>('high')

  const handleInitialize = () => {
    if (!brief.trim()) return

    const config: SimulationConfig = {
      domain,
      artifacts: {
        brief,
        constraints: constraints.split('\n').filter(c => c.trim()),
        signals: [],
        stakeholders: [],
      },
      agents: {
        count: agentCount,
        complexity,
      },
      debate: {
        rounds,
      },
    }

    onInitialize(config)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="w-full max-w-2xl mx-auto"
    >
      <div className="bg-[var(--card)] border border-[var(--line)] rounded-lg overflow-hidden">
        {/* Header strip */}
        <div className="px-8 py-6 border-b border-[var(--line)] bg-[var(--bg-soft)]">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="h-3.5 w-3.5 text-[var(--brand)]" />
            <span className="label-mono">New simulation</span>
          </div>
          <h2 className="font-display text-2xl font-medium tracking-tight">
            Spin up a swarm
          </h2>
          <p className="mt-2 text-sm text-[var(--muted)]">
            Define the topic, pick a domain, and launch six AI agents to debate it.
          </p>
        </div>

        {isRunning ? (
          <div className="p-8 space-y-4">
            <div className="bg-[var(--brand-tint)] border border-[var(--brand)] rounded-md p-4">
              <p className="font-medium text-[var(--brand)] mb-1">Simulation running</p>
              <p className="text-sm text-[var(--muted)]">Agents are debating in real-time.</p>
            </div>
            {onStop && (
              <button
                onClick={onStop}
                className="btn btn-ghost w-full"
                disabled={isLoading}
              >
                Stop simulation
              </button>
            )}
          </div>
        ) : (
          <div className="p-8 space-y-6">
            {/* Domain selection */}
            <div>
              <label className="label-mono mb-3 block">Domain</label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {domains.map(d => (
                  <button
                    key={d.id}
                    type="button"
                    onClick={() => setDomain(d.id)}
                    className={`p-3 rounded-md border text-left transition-colors ${
                      domain === d.id
                        ? 'border-[var(--brand)] bg-[var(--brand-tint)]'
                        : 'border-[var(--line)] bg-[var(--bg)] hover:border-[var(--line-strong)] hover:bg-[var(--bg-soft)]'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <d.Icon
                        className={`h-3.5 w-3.5 ${
                          domain === d.id ? 'text-[var(--brand)]' : 'text-[var(--muted)]'
                        }`}
                      />
                      <span className="text-sm font-medium text-[var(--ink)]">{d.label}</span>
                    </div>
                    <p className="mt-1 text-[11px] text-[var(--muted)]">{d.desc}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Brief */}
            <div>
              <label className="label-mono mb-2 block">Brief</label>
              <textarea
                value={brief}
                onChange={e => setBrief(e.target.value)}
                placeholder="What should the agents debate? E.g. 'Should we ship the new payments API in Q2?'"
                className="input min-h-[88px] resize-y"
                rows={3}
              />
            </div>

            {/* Constraints */}
            <div>
              <label className="label-mono mb-2 block">Constraints (one per line)</label>
              <textarea
                value={constraints}
                onChange={e => setConstraints(e.target.value)}
                placeholder="Limited budget&#10;Regulatory deadline in Q3&#10;Hiring freeze"
                className="input min-h-[72px] resize-y font-mono text-[13px]"
                rows={3}
              />
            </div>

            {/* Parameters */}
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="label-mono mb-2 block">Rounds</label>
                <input
                  type="number"
                  value={rounds}
                  onChange={e => setRounds(Math.max(1, Math.min(10, parseInt(e.target.value) || 1)))}
                  min="1"
                  max="10"
                  className="input font-mono text-center"
                />
              </div>
              <div>
                <label className="label-mono mb-2 block">Agents</label>
                <input
                  type="number"
                  value={agentCount}
                  onChange={e => setAgentCount(Math.max(2, Math.min(12, parseInt(e.target.value) || 2)))}
                  min="2"
                  max="12"
                  className="input font-mono text-center"
                />
              </div>
              <div>
                <label className="label-mono mb-2 block">Complexity</label>
                <select
                  value={complexity}
                  onChange={e => setComplexity(e.target.value as any)}
                  className="input cursor-pointer"
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>
            </div>

            {/* Launch */}
            <button
              type="button"
              onClick={handleInitialize}
              disabled={isLoading || !brief.trim()}
              className="btn btn-primary btn-lg w-full disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Initializing swarm…
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  Launch simulation
                </>
              )}
            </button>

            <p className="text-[11px] text-[var(--muted)] text-center">
              Backend: <span className="font-mono">localhost:8000</span> · Provider:{' '}
              <span className="font-mono text-[var(--brand)]">google/gemini</span>
            </p>
          </div>
        )}
      </div>
    </motion.div>
  )
}
