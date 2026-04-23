'use client'

import React, { useState } from 'react'
import { Send, MessageSquare, X, Loader2 } from 'lucide-react'
import type { AgentProfile } from '@/types/pipeline'
import { pipelineApi } from '@/lib/pipeline-api'
import { motion, AnimatePresence } from 'framer-motion'

interface AgentChatPanelProps {
  projectId: string
  agent: AgentProfile
  onClose: () => void
}

interface ChatTurn {
  role: 'user' | 'agent'
  content: string
}

export default function AgentChatPanel({
  projectId,
  agent,
  onClose,
}: AgentChatPanelProps) {
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(false)

  const send = async () => {
    const message = draft.trim()
    if (!message || loading) return

    setTurns((prev) => [...prev, { role: 'user', content: message }])
    setDraft('')
    setLoading(true)

    try {
      const res = await pipelineApi.chatWithAgent(projectId, agent.id, message)
      setTurns((prev) => [...prev, { role: 'agent', content: res.reply }])
    } catch (err) {
      setTurns((prev) => [
        ...prev,
        {
          role: 'agent',
          content: `(error: ${err instanceof Error ? err.message : 'unknown'})`,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: 20 }}
        transition={{ duration: 0.2 }}
        className="fixed right-4 bottom-44 w-[380px] max-h-[60vh] bg-[var(--card)] border border-[var(--line-strong)] rounded-md shadow-lg z-50 flex flex-col overflow-hidden"
      >
        <header className="px-4 py-3 border-b border-[var(--line)] bg-[var(--bg-soft)] flex items-start justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <MessageSquare className="h-3.5 w-3.5 text-[var(--brand)]" />
              <span className="label-mono">Deep interaction</span>
            </div>
            <p className="font-display text-sm font-medium text-[var(--ink)] truncate">
              {agent.name}
            </p>
            <p className="text-[10px] font-mono text-[var(--muted)] truncate">
              @{agent.user_name} · {agent.role}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-[var(--muted)] hover:text-[var(--ink)] p-1"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-[160px]">
          {turns.length === 0 && (
            <p className="text-xs text-[var(--muted)] text-center py-6">
              Ask {agent.name.split(' ')[0]} a follow-up question.
            </p>
          )}
          {turns.map((turn, i) => (
            <div
              key={i}
              className={`flex ${turn.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-md px-3 py-2 text-xs leading-relaxed ${
                  turn.role === 'user'
                    ? 'bg-[var(--ink)] text-[var(--bg)]'
                    : 'bg-[var(--bg-soft)] text-[var(--ink)] border border-[var(--line)]'
                }`}
              >
                {turn.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-[var(--bg-soft)] border border-[var(--line)] rounded-md px-3 py-2">
                <Loader2 className="h-3 w-3 animate-spin text-[var(--brand)]" />
              </div>
            </div>
          )}
        </div>

        <div className="p-3 border-t border-[var(--line)] flex gap-2">
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
            placeholder={`Ask ${agent.name.split(' ')[0]}…`}
            className="input text-xs py-2"
            disabled={loading}
          />
          <button
            onClick={send}
            disabled={loading || !draft.trim()}
            className="bg-[var(--brand)] text-white p-2 rounded-md disabled:opacity-50"
            aria-label="Send"
          >
            <Send className="h-3.5 w-3.5" />
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  )
}
