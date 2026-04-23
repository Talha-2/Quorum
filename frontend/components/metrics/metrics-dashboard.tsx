'use client'

import React from 'react'
import { SimulationMetrics } from '@/types/simulation'
import { motion } from 'framer-motion'
import GaugeCard from './gauge-card'
import StatsCard from './stats-card'
import { Activity } from 'lucide-react'

interface MetricsDashboardProps {
  metrics: SimulationMetrics
}

export default function MetricsDashboard({ metrics }: MetricsDashboardProps) {
  const itemVariants = {
    hidden: { opacity: 0, y: 8 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.3 } },
  }

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.06, delayChildren: 0.1 },
    },
  }

  return (
    <motion.div
      className="space-y-3"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Header */}
      <div className="px-4 py-3 bg-[var(--card)] border border-[var(--line)] rounded-md flex items-center gap-2">
        <Activity className="h-3.5 w-3.5 text-[var(--brand)]" />
        <span className="label-mono">Live metrics</span>
      </div>

      {/* Gauges */}
      <motion.div className="grid grid-cols-2 gap-3" variants={itemVariants}>
        <GaugeCard
          label="Agreement"
          value={metrics.agreementRate}
          unit="%"
          max={100}
          color="var(--brand)"
        />
        <GaugeCard
          label="Confidence"
          value={metrics.confidenceScore * 100}
          unit="%"
          max={100}
          color="#000000"
        />
      </motion.div>

      {/* Stats */}
      <motion.div className="grid grid-cols-2 gap-3" variants={itemVariants}>
        <StatsCard
          label="Active agents"
          value={metrics.agentsActive}
          change={metrics.agentsActive > 0 ? `${metrics.agentsActive} debating` : 'idle'}
          trend="up"
        />
        <StatsCard
          label="Rounds"
          value={`${metrics.debateRounds}`}
          change="of debate"
          trend="neutral"
        />
      </motion.div>

      <motion.div className="grid grid-cols-2 gap-3" variants={itemVariants}>
        <StatsCard
          label="Graph nodes"
          value={metrics.nodesInGraph}
          change="entities"
          trend="neutral"
        />
        <StatsCard
          label="Edges"
          value={metrics.edgesInGraph}
          change="relationships"
          trend="neutral"
        />
      </motion.div>

      {/* Status card */}
      <motion.div
        className="bg-[var(--card)] border border-[var(--line)] rounded-md p-4"
        variants={itemVariants}
      >
        <p className="label-mono mb-3">Consensus status</p>
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${
              metrics.consensusReached ? 'bg-[var(--brand)] pulse-dot' : 'bg-[var(--muted-soft)]'
            }`}
          />
          <span className="text-sm font-medium text-[var(--ink)]">
            {metrics.consensusReached ? 'Reached' : 'In progress'}
          </span>
        </div>
        {metrics.executionTime > 0 && (
          <p className="mt-3 text-[10px] font-mono text-[var(--muted)]">
            Started · {new Date(metrics.executionTime).toLocaleTimeString()}
          </p>
        )}
      </motion.div>
    </motion.div>
  )
}
