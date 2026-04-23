'use client'

import React, { useEffect, useRef } from 'react'
import { DebateState } from '@/types/debate'
import AgentSpeech from './agent-speech'
import ConsensusView from './consensus-view'
import { motion } from 'framer-motion'
import { Loader2, MessagesSquare } from 'lucide-react'

interface DebatePanelProps {
  debateState: DebateState
  isLoading?: boolean
}

export default function DebatePanel({ debateState, isLoading = false }: DebatePanelProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight
    }
  }, [debateState.rounds])

  const allMessages = debateState.rounds
    .flatMap(round => round.messages)
    .sort((a, b) => a.timestamp - b.timestamp)

  const currentRound = debateState.rounds[debateState.rounds.length - 1]
  const progress =
    debateState.totalRounds > 0
      ? (debateState.currentRound / debateState.totalRounds) * 100
      : 0

  return (
    <div className="flex flex-col h-full bg-[var(--card)] border border-[var(--line)] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-[var(--line)] flex items-center justify-between bg-[var(--bg-soft)]">
        <div>
          <div className="flex items-center gap-2">
            <MessagesSquare className="h-3.5 w-3.5 text-[var(--brand)]" />
            <span className="label-mono">Live debate</span>
          </div>
          <p className="mt-1 font-display text-base font-medium text-[var(--ink)]">
            Round {debateState.currentRound || 0} of {debateState.totalRounds}
          </p>
        </div>

        {isLoading && (
          <Loader2 className="h-4 w-4 text-[var(--brand)] animate-spin" />
        )}
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-[var(--bg-strong)]">
        <motion.div
          className="h-full bg-[var(--brand)]"
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.5 }}
        />
      </div>

      {/* Messages */}
      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto p-5 space-y-4">
        {allMessages.length === 0 ? (
          <div className="h-full flex items-center justify-center text-center">
            <div>
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-md bg-[var(--bg-soft)] border border-[var(--line)] mb-3">
                <MessagesSquare className="h-5 w-5 text-[var(--muted)]" />
              </div>
              <p className="text-sm font-medium text-[var(--ink)]">Waiting on the swarm</p>
              <p className="text-xs text-[var(--muted)] mt-1">
                Agents will start debating any moment now…
              </p>
            </div>
          </div>
        ) : (
          allMessages.map((message, idx) => {
            const agent = debateState.agents.find(a => a.id === message.agentId)
            if (!agent) return null
            return (
              <AgentSpeech
                key={message.id}
                message={message}
                agent={agent}
                index={idx}
                isStreaming={
                  currentRound?.status === 'active' &&
                  message.id === allMessages[allMessages.length - 1]?.id
                }
              />
            )
          })
        )}
      </div>

      {/* Consensus */}
      {debateState.consensus && (
        <motion.div
          className="border-t border-[var(--line)]"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <ConsensusView consensus={debateState.consensus} />
        </motion.div>
      )}
    </div>
  )
}
