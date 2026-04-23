'use client'

import React from 'react'
import { Consensus } from '@/types/debate'
import { motion } from 'framer-motion'
import { CheckCircle2, AlertCircle } from 'lucide-react'

interface ConsensusViewProps {
  consensus: Consensus
}

export default function ConsensusView({ consensus }: ConsensusViewProps) {
  if (!consensus.reached) {
    return (
      <div className="p-5 bg-[var(--bg-soft)]">
        <div className="flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-[var(--brand)] mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-medium text-sm text-[var(--ink)]">Debate continues</p>
            <p className="text-xs text-[var(--muted)] mt-1">
              Agents are still working towards consensus.
            </p>
          </div>
        </div>
      </div>
    )
  }

  const dissentCount = consensus.dissents?.length || 0
  const agreementPercent = (consensus.agreementRate ?? 0.8) * 100
  const confidencePercent = (consensus.confidenceLevel ?? 0.8) * 100

  return (
    <div className="bg-[var(--brand-tint)] border-t border-[var(--brand)] p-5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', stiffness: 260, damping: 20 }}
        >
          <CheckCircle2 className="h-5 w-5 text-[var(--brand)]" />
        </motion.div>
        <span className="label-mono text-[var(--brand)]">Consensus reached</span>
      </div>

      {/* Agreed position */}
      <div className="bg-[var(--card)] border border-[var(--brand)]/30 rounded-md p-4 mb-4">
        <p className="label-mono mb-2">Agreed position</p>
        <p className="text-sm leading-relaxed text-[var(--ink)]">{consensus.agreedPosition}</p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-[var(--card)] border border-[var(--line)] rounded-md p-3">
          <p className="label-mono">Agreement</p>
          <p className="font-display text-2xl font-medium text-[var(--brand)] mt-1">
            {agreementPercent.toFixed(0)}%
          </p>
          <div className="mt-2 h-1 bg-[var(--bg-strong)] rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-[var(--brand)]"
              initial={{ width: 0 }}
              animate={{ width: `${agreementPercent}%` }}
              transition={{ duration: 0.8 }}
            />
          </div>
        </div>
        <div className="bg-[var(--card)] border border-[var(--line)] rounded-md p-3">
          <p className="label-mono">Confidence</p>
          <p className="font-display text-2xl font-medium text-[var(--ink)] mt-1">
            {confidencePercent.toFixed(0)}%
          </p>
          <div className="mt-2 h-1 bg-[var(--bg-strong)] rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-[var(--ink)]"
              initial={{ width: 0 }}
              animate={{ width: `${confidencePercent}%` }}
              transition={{ duration: 0.8, delay: 0.1 }}
            />
          </div>
        </div>
      </div>

      {/* Dissents */}
      {dissentCount > 0 && (
        <div className="bg-[var(--card)] border border-[var(--line)] rounded-md p-3">
          <p className="label-mono mb-2">Dissents · {dissentCount}</p>
          <div className="space-y-2">
            {consensus.dissents?.map((d, idx) => (
              <motion.div
                key={d.agentId}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2 + idx * 0.1 }}
                className="text-xs"
              >
                <span className="font-medium text-[var(--ink)]">{d.agentName}:</span>{' '}
                <span className="text-[var(--muted)]">{d.position}</span>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {consensus.timestamp && (
        <p className="mt-3 text-[10px] font-mono text-[var(--muted)]">
          Reached at {new Date(consensus.timestamp).toLocaleTimeString()}
        </p>
      )}
    </div>
  )
}
