'use client'

import React from 'react'
import { GraphNode as GraphNodeType } from '@/types/graph'
import { motion } from 'framer-motion'
import { Bot, Box, Target, BookOpen, Ban } from 'lucide-react'

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  agent: Bot,
  entity: Box,
  theme: Target,
  context: BookOpen,
  blocker: Ban,
}

interface GraphNodeProps {
  node: GraphNodeType
  color: string
  isSelected: boolean
  isHovered: boolean
  isAnimating: boolean
  isDragging?: boolean
  onClick: () => void
  onHover: () => void
  onHoverEnd: () => void
  onMouseDown?: (e: React.MouseEvent) => void
  style?: React.CSSProperties
}

export default function GraphNodeComponent({
  node,
  color,
  isSelected,
  isHovered,
  isAnimating,
  isDragging = false,
  onClick,
  onHover,
  onHoverEnd,
  onMouseDown,
  style,
}: GraphNodeProps) {
  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!isDragging) onClick()
  }

  return (
    <motion.div
      className={`absolute w-20 h-20 -translate-x-1/2 -translate-y-1/2 group ${
        isDragging ? 'cursor-grabbing' : 'cursor-grab'
      }`}
      style={style}
      initial={{ scale: 0, opacity: 0 }}
      animate={{
        scale: isSelected ? 1.18 : isHovered ? 1.08 : 1,
        opacity: 1,
      }}
      transition={{ type: 'spring', stiffness: 260, damping: 22 }}
      onClick={handleClick}
      onMouseDown={onMouseDown}
      onMouseEnter={onHover}
      onMouseLeave={onHoverEnd}
    >
      {/* Glow effect for animating nodes */}
      {isAnimating && (
        <motion.div
          className="absolute inset-0 rounded-full"
          style={{ backgroundColor: color, opacity: 0.3 }}
          animate={{
            scale: [1, 1.6, 1],
            opacity: [0.3, 0, 0.3],
          }}
          transition={{ duration: 1.4, repeat: Infinity }}
        />
      )}

      {/* Main node circle */}
      <motion.div
        className="absolute inset-0 rounded-full flex items-center justify-center text-white text-sm transition-all duration-200"
        style={{
          backgroundColor: color,
          border: isSelected ? '2px solid var(--brand)' : '2px solid var(--card)',
          boxShadow: isSelected
            ? `0 0 0 4px rgba(255, 69, 0, 0.22), 0 6px 16px ${color}40`
            : isHovered
              ? `0 6px 16px ${color}40`
              : '0 1px 3px rgba(0,0,0,0.12)',
        }}
      >
        {(() => {
          const Icon = ICONS[node.type] || Box
          return <Icon className="h-4 w-4 text-white" />
        })()}
      </motion.div>

      {/* Label tooltip on hover */}
      <motion.div
        className="absolute top-full mt-2 left-1/2 -translate-x-1/2 bg-[var(--ink)] text-[var(--bg)] text-[10px] font-mono px-2 py-1 rounded whitespace-nowrap pointer-events-none"
        initial={{ opacity: 0, y: -5 }}
        animate={{ opacity: isHovered && !isSelected ? 1 : 0, y: isHovered && !isSelected ? 0 : -5 }}
        transition={{ duration: 0.15 }}
      >
        {node.label}
      </motion.div>
    </motion.div>
  )
}
