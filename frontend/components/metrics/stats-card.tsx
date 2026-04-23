'use client'

import React from 'react'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface StatsCardProps {
  label: string
  value: number | string
  change?: string
  trend?: 'up' | 'down' | 'neutral'
}

export default function StatsCard({
  label,
  value,
  change,
  trend = 'neutral',
}: StatsCardProps) {
  const Icon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus
  const trendColor =
    trend === 'up'
      ? 'text-[#00C851]'
      : trend === 'down'
        ? 'text-[var(--brand)]'
        : 'text-[var(--muted)]'

  return (
    <div className="bg-[var(--card)] border border-[var(--line)] rounded-md p-4 hover:border-[var(--line-strong)] transition-colors">
      <p className="label-mono mb-2">{label}</p>
      <p className="font-display text-2xl font-medium text-[var(--ink)] leading-none">
        {value}
      </p>
      {change && (
        <div className={`mt-2 flex items-center gap-1 ${trendColor}`}>
          <Icon className="h-3 w-3" />
          <span className="text-[10px] font-mono">{change}</span>
        </div>
      )}
    </div>
  )
}
