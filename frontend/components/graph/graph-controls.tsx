'use client'

import React from 'react'
import { ZoomIn, ZoomOut, Maximize2, Filter } from 'lucide-react'

interface GraphControlsProps {
  zoomLevel: number
  onZoomIn: () => void
  onZoomOut: () => void
  onReset: () => void
  onFilterChange?: (filter: string) => void
  activeFilter?: string
}

const filters = ['all', 'agent', 'entity', 'theme', 'context', 'blocker']

export default function GraphControls({
  zoomLevel,
  onZoomIn,
  onZoomOut,
  onReset,
  onFilterChange,
  activeFilter = 'all',
}: GraphControlsProps) {
  return (
    <div className="flex gap-1 bg-[var(--card)] border border-[var(--line)] rounded-md p-1 items-center">
      <button
        onClick={onZoomOut}
        disabled={zoomLevel <= 0.5}
        className="p-2 hover:bg-[var(--bg-soft)] rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        title="Zoom out"
      >
        <ZoomOut className="h-4 w-4" />
      </button>
      <span className="px-2 text-[10px] font-mono text-[var(--muted)] min-w-[40px] text-center">
        {(zoomLevel * 100).toFixed(0)}%
      </span>
      <button
        onClick={onZoomIn}
        disabled={zoomLevel >= 3}
        className="p-2 hover:bg-[var(--bg-soft)] rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        title="Zoom in"
      >
        <ZoomIn className="h-4 w-4" />
      </button>
      <div className="w-px h-5 bg-[var(--line)] mx-1" />
      <button
        onClick={onReset}
        className="p-2 hover:bg-[var(--bg-soft)] rounded transition-colors"
        title="Reset view"
      >
        <Maximize2 className="h-4 w-4" />
      </button>
      {onFilterChange && (
        <>
          <div className="w-px h-5 bg-[var(--line)] mx-1" />
          <Filter className="h-3.5 w-3.5 text-[var(--muted)] ml-1" />
          <select
            value={activeFilter}
            onChange={(e) => onFilterChange(e.target.value)}
            className="text-[11px] font-mono px-2 py-1.5 bg-transparent border-0 text-[var(--ink)] cursor-pointer focus:outline-none capitalize"
          >
            {filters.map(filter => (
              <option key={filter} value={filter}>
                {filter}
              </option>
            ))}
          </select>
        </>
      )}
    </div>
  )
}
