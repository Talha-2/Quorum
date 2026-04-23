'use client'

import React from 'react'
import { DebateMessage, Agent } from '@/types/debate'
import { motion } from 'framer-motion'

interface AgentSpeechProps {
  message: DebateMessage
  agent: Agent
  isStreaming?: boolean
  index?: number
}

// Stable agent color from name (so each agent always renders the same color)
function colorForAgent(name: string): string {
  const palette = [
    '#FF4500', // brand orange
    '#00B0FF', // accent blue
    '#00C851', // accent green
    '#9b51e0', // purple
    '#f59e0b', // amber
    '#0ea5e9', // sky
    '#ec4899', // pink
    '#10b981', // emerald
  ]
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = (hash << 5) - hash + name.charCodeAt(i)
    hash |= 0
  }
  return palette[Math.abs(hash) % palette.length]
}

const sentimentLabel = {
  positive: 'Supports',
  negative: 'Concerns',
  neutral: 'Neutral',
} as const

const sentimentColor = {
  positive: 'text-[#00C851]',
  negative: 'text-[var(--brand)]',
  neutral: 'text-[var(--muted)]',
} as const

export default function AgentSpeech({
  message,
  agent,
  isStreaming = false,
  index = 0,
}: AgentSpeechProps) {
  const color = colorForAgent(agent.name)
  const sentiment = (message.sentiment || 'neutral') as keyof typeof sentimentLabel

  return (
    <motion.div
      className="flex gap-3"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.04 }}
    >
      {/* Avatar */}
      <div className="flex-shrink-0">
        <div
          className="w-8 h-8 rounded-md flex items-center justify-center font-mono font-semibold text-white text-xs"
          style={{ background: color }}
        >
          {agent.name.charAt(0)}
        </div>
      </div>

      {/* Bubble */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="font-medium text-sm text-[var(--ink)]">{agent.name}</span>
          <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--muted)]">
            {agent.role}
          </span>
          {isStreaming && (
            <motion.span
              className="w-1.5 h-1.5 rounded-full bg-[var(--brand)]"
              animate={{ opacity: [0.3, 1, 0.3] }}
              transition={{ duration: 1, repeat: Infinity }}
            />
          )}
        </div>

        <div className="bg-[var(--card)] border border-[var(--line)] rounded-md p-3 hover:border-[var(--line-strong)] transition-colors">
          <p className="text-sm leading-relaxed text-[var(--ink)]">{message.content}</p>

          <div className="mt-3 pt-3 border-t border-[var(--line-soft)] flex items-center justify-between gap-3">
            {message.confidence !== undefined && (
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <span className="text-[10px] font-mono uppercase text-[var(--muted)]">
                  Conf
                </span>
                <div className="flex-1 max-w-[120px] h-1 bg-[var(--bg-strong)] rounded-full overflow-hidden">
                  <motion.div
                    className="h-full"
                    style={{ background: color }}
                    initial={{ width: 0 }}
                    animate={{ width: `${message.confidence * 100}%` }}
                    transition={{ duration: 0.6 }}
                  />
                </div>
                <span className="text-[10px] font-mono text-[var(--ink)]">
                  {(message.confidence * 100).toFixed(0)}%
                </span>
              </div>
            )}
            <div className="flex items-center gap-2 text-[10px] font-mono">
              <span className={sentimentColor[sentiment]}>{sentimentLabel[sentiment]}</span>
              <span className="text-[var(--muted)]">·</span>
              <span className="text-[var(--muted)]">R{message.round}</span>
            </div>
          </div>
        </div>

        {/* Personality bars */}
        <div className="mt-2 flex gap-3 flex-wrap">
          {[
            { label: 'opt', value: agent.personality.optimism },
            { label: 'risk', value: agent.personality.riskTolerance },
            { label: 'caut', value: agent.personality.caution },
          ].map(trait => (
            <div key={trait.label} className="flex items-center gap-1">
              <span className="text-[10px] font-mono uppercase text-[var(--muted)]">
                {trait.label}
              </span>
              <div className="w-10 h-0.5 bg-[var(--bg-strong)] rounded-full overflow-hidden">
                <div
                  className="h-full"
                  style={{ width: `${trait.value * 100}%`, background: color }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}
