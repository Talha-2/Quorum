'use client'

import React from 'react'
import { motion } from 'framer-motion'
import { ChevronUp, ChevronDown, Bot, Box, Target, BookOpen, Ban } from 'lucide-react'

interface NodeTypeInfo {
  type: string
  color: string
  Icon: React.ComponentType<{ className?: string }>
  description: string
}

const nodeTypes: NodeTypeInfo[] = [
  { type: 'agent', color: '#FF4500', Icon: Bot, description: 'AI agent with personality' },
  { type: 'entity', color: '#00B0FF', Icon: Box, description: 'Business entity or resource' },
  { type: 'theme', color: '#9b51e0', Icon: Target, description: 'Main discussion theme' },
  { type: 'context', color: '#000000', Icon: BookOpen, description: 'Contextual information' },
  { type: 'blocker', color: '#b3473d', Icon: Ban, description: 'Blocking constraint' },
]

const edgeTypes = [
  { type: 'depends_on', description: 'A depends on B' },
  { type: 'blocks', description: 'A blocks B' },
  { type: 'influences', description: 'A influences B' },
]

interface GraphLegendProps {
  isOpen: boolean
  onToggle: () => void
}

export default function GraphLegend({ isOpen, onToggle }: GraphLegendProps) {
  return (
    <div className="bg-[var(--card)] border border-[var(--line)] rounded-md overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-[var(--bg-soft)] transition-colors"
      >
        <span className="label-mono">Legend</span>
        {isOpen ? (
          <ChevronUp className="h-3.5 w-3.5 text-[var(--muted)]" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-[var(--muted)]" />
        )}
      </button>

      {isOpen && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.2 }}
          className="border-t border-[var(--line)]"
        >
          <div className="p-4 space-y-3">
            <div>
              <p className="label-mono mb-2">Nodes</p>
              <div className="space-y-1.5">
                {nodeTypes.map((nt) => (
                  <div key={nt.type} className="flex items-center gap-2">
                    <span
                      className="inline-flex h-4 w-4 items-center justify-center rounded-sm flex-shrink-0"
                      style={{ background: nt.color }}
                    >
                      <nt.Icon className="h-2.5 w-2.5 text-white" />
                    </span>
                    <span className="text-[11px] capitalize text-[var(--ink)] font-medium">
                      {nt.type}
                    </span>
                    <span className="text-[10px] text-[var(--muted)] truncate">
                      · {nt.description}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-3 border-t border-[var(--line-soft)]">
              <p className="label-mono mb-2">Edges</p>
              <div className="space-y-1.5">
                {edgeTypes.map((et) => (
                  <div key={et.type} className="flex items-center gap-2">
                    <span className="font-mono text-[10px] text-[var(--brand)]">
                      {et.type}
                    </span>
                    <span className="text-[10px] text-[var(--muted)]">· {et.description}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  )
}
