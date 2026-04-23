'use client'

import React from 'react'
import { motion } from 'framer-motion'

interface GaugeCardProps {
  label: string
  value: number
  unit?: string
  max?: number
  color?: string
}

export default function GaugeCard({
  label,
  value,
  unit = '%',
  max = 100,
  color = 'var(--brand)',
}: GaugeCardProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100)

  const radius = 38
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (percentage / 100) * circumference

  return (
    <div className="bg-[var(--card)] border border-[var(--line)] rounded-md p-4">
      <p className="label-mono mb-3">{label}</p>

      <div className="flex items-center justify-center relative mb-3">
        <svg width="100" height="100" className="-rotate-90">
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke="var(--bg-strong)"
            strokeWidth="5"
          />
          <motion.circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="5"
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
          />
        </svg>

        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center">
            <p className="font-display text-xl font-medium text-[var(--ink)] leading-none">
              {value.toFixed(0)}
            </p>
            <p className="text-[10px] font-mono text-[var(--muted)] mt-0.5">{unit}</p>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between text-[10px] font-mono">
        <span className="text-[var(--muted)] uppercase">
          {percentage > 70 ? 'Good' : percentage > 40 ? 'Fair' : 'Low'}
        </span>
        <span style={{ color }}>{percentage.toFixed(0)}%</span>
      </div>
    </div>
  )
}
