'use client'

import React from 'react'
import { ChevronRight, Loader2 } from 'lucide-react'

export type StageStatus = 'pending' | 'processing' | 'complete' | 'failed'

interface StageCardProps {
  number: string
  title: string
  endpoint?: string
  description?: string
  status: StageStatus
  children?: React.ReactNode
  action?: React.ReactNode
}

const STATUS_LABEL: Record<StageStatus, string> = {
  pending: 'Pending',
  processing: 'Processing',
  complete: 'Build Complete',
  failed: 'Failed',
}

const STATUS_CLASS: Record<StageStatus, string> = {
  pending:
    'bg-[var(--bg-soft)] text-[var(--muted)] border border-[var(--line)]',
  processing:
    'bg-[var(--brand)] text-white border border-[var(--brand)]',
  complete:
    'bg-[#00C851]/14 text-[#00C851] border border-[#00C851]/30',
  failed: 'bg-[#b3473d]/14 text-[#b3473d] border border-[#b3473d]/30',
}

export default function StageCard({
  number,
  title,
  endpoint,
  description,
  status,
  children,
  action,
}: StageCardProps) {
  const isProcessing = status === 'processing'
  const ringClass =
    isProcessing
      ? 'border-[var(--brand)] shadow-[0_0_0_4px_rgba(255,69,0,0.06)]'
      : 'border-[var(--line)]'

  return (
    <section
      className={`bg-[var(--card)] border ${ringClass} rounded-md p-6 transition-all`}
    >
      <header className="flex items-start justify-between gap-3">
        <div className="flex items-baseline gap-3 min-w-0">
          <span className="font-mono text-xs font-medium text-[var(--muted)] tabular-nums">
            {number}
          </span>
          <h3 className="font-display text-base font-medium text-[var(--ink)] tracking-tight truncate">
            {title}
          </h3>
        </div>
        <span
          className={`text-[10px] font-mono uppercase tracking-wider px-2 py-1 rounded ${STATUS_CLASS[status]} flex-shrink-0 inline-flex items-center gap-1.5`}
        >
          {isProcessing && <Loader2 className="h-2.5 w-2.5 animate-spin" />}
          {STATUS_LABEL[status]}
        </span>
      </header>

      {endpoint && (
        <p className="mt-3 text-[10px] font-mono text-[var(--muted)]">
          <span className="text-[var(--brand)] font-medium">POST</span> {endpoint}
        </p>
      )}

      {description && (
        <p className="mt-3 text-[13px] leading-relaxed text-[var(--muted)]">
          {description}
        </p>
      )}

      {children && <div className="mt-5">{children}</div>}

      {action && <div className="mt-5">{action}</div>}
    </section>
  )
}

export function StageChips({ items, label }: { items: string[]; label: string }) {
  if (!items || items.length === 0) return null
  return (
    <div className="space-y-2">
      <p className="label-mono">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span
            key={item}
            className="inline-flex items-center px-2 py-1 rounded bg-[var(--bg-soft)] border border-[var(--line)] text-[11px] font-mono text-[var(--ink)]"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  )
}

export function StageStat({
  value,
  label,
}: {
  value: number | string
  label: string
}) {
  return (
    <div className="text-center">
      <p className="font-display text-3xl font-medium text-[var(--ink)] leading-none tabular-nums">
        {value}
      </p>
      <p className="mt-1.5 text-[10px] font-mono uppercase tracking-wider text-[var(--muted)]">
        {label}
      </p>
    </div>
  )
}

export function StageActionButton({
  onClick,
  disabled,
  children,
  variant = 'primary',
}: {
  onClick: () => void
  disabled?: boolean
  children: React.ReactNode
  variant?: 'primary' | 'ghost'
}) {
  const base =
    variant === 'primary'
      ? 'w-full bg-[var(--ink)] text-[var(--bg)] hover:bg-[var(--brand)] py-3 rounded-md font-medium text-sm'
      : 'btn btn-ghost btn-sm'
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`${base} transition-colors disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center justify-center gap-2`}
    >
      {children}
      {variant === 'primary' && <ChevronRight className="h-4 w-4" />}
    </button>
  )
}
