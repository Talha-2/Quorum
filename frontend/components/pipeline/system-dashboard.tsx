'use client'

import React, { useEffect, useRef } from 'react'
import type { PipelineEvent } from '@/types/pipeline'

interface SystemDashboardProps {
  events: PipelineEvent[]
  projectId?: string | null
}

const LEVEL_COLOR: Record<string, string> = {
  info: '#9b9895',
  success: '#00C851',
  warn: '#ffb020',
  error: '#ff4444',
}

function fmtTime(iso: string): string {
  try {
    const d = new Date(iso)
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    const ss = String(d.getSeconds()).padStart(2, '0')
    const ms = String(d.getMilliseconds()).padStart(3, '0')
    return `${hh}:${mm}:${ss}.${ms}`
  } catch {
    return ''
  }
}

export default function SystemDashboard({ events, projectId }: SystemDashboardProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [events])

  return (
    <div className="bg-black text-white border-t border-[var(--line)] flex-shrink-0">
      <div className="px-4 py-2 border-b border-white/10 flex items-center justify-between">
        <span className="text-[10px] font-mono uppercase tracking-wider text-white/50">
          System Dashboard
        </span>
        {projectId && (
          <span className="text-[10px] font-mono text-white/30">{projectId}</span>
        )}
      </div>
      <div
        ref={scrollRef}
        className="px-4 py-2 max-h-[140px] overflow-y-auto font-mono text-[11px] leading-relaxed"
      >
        {events.length === 0 ? (
          <p className="text-white/30">awaiting events…</p>
        ) : (
          events.slice(-30).map((ev, idx) => (
            <div key={idx} className="flex gap-3">
              <span className="text-white/40 tabular-nums flex-shrink-0">
                {fmtTime(ev.timestamp)}
              </span>
              <span
                className="flex-shrink-0"
                style={{ color: LEVEL_COLOR[ev.level] || '#9b9895' }}
              >
                ►
              </span>
              <span className="text-white/85">{ev.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
