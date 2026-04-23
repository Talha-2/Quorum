import React from 'react'

interface QuorumMarkProps {
  size?: number
  className?: string
}

/**
 * Quorum logomark — a 5-dot constellation arranged in a pentagon with a center dot,
 * representing a swarm of agents converging on consensus.
 */
export default function QuorumMark({ size = 28, className = '' }: QuorumMarkProps) {
  const r = 2.6
  // Pentagon vertices around center (16,16) with radius 9
  const cx = 16
  const cy = 16
  const ringR = 9
  const points = Array.from({ length: 5 }, (_, i) => {
    const angle = (-Math.PI / 2) + (i * (2 * Math.PI)) / 5
    return {
      x: cx + ringR * Math.cos(angle),
      y: cy + ringR * Math.sin(angle),
    }
  })

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      {/* Outer rounded square mark background */}
      <rect width="32" height="32" rx="8" fill="currentColor" />
      {/* Connections from center to each vertex */}
      {points.map((p, i) => (
        <line
          key={`line-${i}`}
          x1={cx}
          y1={cy}
          x2={p.x}
          y2={p.y}
          stroke="white"
          strokeOpacity={0.45}
          strokeWidth={0.9}
          strokeLinecap="round"
        />
      ))}
      {/* Outer dots */}
      {points.map((p, i) => (
        <circle key={`dot-${i}`} cx={p.x} cy={p.y} r={r} fill="white" />
      ))}
      {/* Center dot — the consensus */}
      <circle cx={cx} cy={cy} r={r + 0.3} fill="white" />
    </svg>
  )
}
