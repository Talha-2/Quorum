'use client'

import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { FileText, Loader2, Download, Sparkles } from 'lucide-react'
import StageCard, { StageActionButton } from '@/components/pipeline/stage-card'
import type { Report } from '@/types/pipeline'
import type { StageStatus } from '@/components/pipeline/stage-card'

interface StageReportCardProps {
  number: string
  status: StageStatus
  report: Report | null
  onGenerate?: () => void
  loading?: boolean
}

export default function StageReportCard({
  number,
  status,
  report,
  onGenerate,
  loading = false,
}: StageReportCardProps) {
  return (
    <StageCard
      number={number}
      title="Generate Report"
      endpoint="/api/projects/{id}/report/generate"
      description="LLM plans a report outline from the simulation findings, then writes each section using the debate transcript and agent profiles as evidence."
      status={status}
      action={
        !report && onGenerate ? (
          <StageActionButton onClick={onGenerate} disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Writing report…
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Generate report
              </>
            )}
          </StageActionButton>
        ) : undefined
      }
    >
      {report && <ReportPreview report={report} />}
    </StageCard>
  )
}

// ============================================
// Inline report preview
// ============================================
function ReportPreview({ report }: { report: Report }) {
  const [expanded, setExpanded] = useState(false)
  const sections = report.sections || []

  const handleDownload = () => {
    const blob = new Blob([report.markdown || ''], {
      type: 'text/markdown;charset=utf-8',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${slugify(report.title || 'quorum-report')}.md`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-4">
      {/* Header card */}
      <div className="bg-[var(--brand-tint)] border border-[var(--brand)]/30 rounded-md p-4">
        <div className="flex items-center gap-2 mb-2">
          <FileText className="h-3.5 w-3.5 text-[var(--brand)]" />
          <span className="label-mono text-[var(--brand)]">Prediction report</span>
        </div>
        <h3 className="font-display text-lg font-medium text-[var(--ink)] tracking-tight leading-snug">
          {report.title}
        </h3>
        {report.summary && (
          <p className="mt-2 text-xs text-[var(--ink)] leading-relaxed italic">
            {report.summary}
          </p>
        )}
      </div>

      {/* Sections — collapsed view shows section titles, expanded shows bodies */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="label-mono">{sections.length} sections</p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-[10px] font-mono uppercase tracking-wider text-[var(--muted)] hover:text-[var(--brand)] transition-colors"
            >
              {expanded ? 'Collapse' : 'Expand all'}
            </button>
            <button
              onClick={handleDownload}
              className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-[var(--muted)] hover:text-[var(--brand)] transition-colors"
              title="Download as Markdown"
            >
              <Download className="h-3 w-3" />
              .md
            </button>
          </div>
        </div>

        <div className="space-y-2">
          {sections.map((sec, i) => (
            <ReportSectionCard key={i} index={i} section={sec} expanded={expanded} />
          ))}
        </div>
      </div>

      {report.generated_at && (
        <p className="text-[10px] font-mono text-[var(--muted)] text-right">
          generated {new Date(report.generated_at).toLocaleString()}
        </p>
      )}
    </div>
  )
}

// ============================================
// Single section — collapsible
// ============================================
function ReportSectionCard({
  index,
  section,
  expanded,
}: {
  index: number
  section: { title: string; content: string }
  expanded: boolean
}) {
  const [open, setOpen] = useState(false)
  const isOpen = expanded || open

  return (
    <div className="bg-[var(--bg-soft)] border border-[var(--line)] rounded-md overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-[var(--card)] transition-colors"
      >
        <span className="font-mono text-[10px] text-[var(--brand)] tabular-nums flex-shrink-0">
          §{(index + 1).toString().padStart(2, '0')}
        </span>
        <span className="text-[12px] font-medium text-[var(--ink)] flex-1 truncate">
          {section.title}
        </span>
        <span className="text-[10px] font-mono text-[var(--muted)] flex-shrink-0">
          {isOpen ? '−' : '+'}
        </span>
      </button>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          transition={{ duration: 0.15 }}
          className="border-t border-[var(--line-soft)]"
        >
          <div className="px-4 py-3">
            <MarkdownBody text={section.content} />
          </div>
        </motion.div>
      )}
    </div>
  )
}

// ============================================
// Tiny markdown renderer — paragraphs + blockquotes only
// ============================================
//
// The section bodies are short markdown with `> quotes`. Rather than pull in
// a full markdown library (~80kb), we render the two cases the section
// writer actually emits: paragraphs (separated by blank lines) and `> ...`
// blockquote lines.
function MarkdownBody({ text }: { text: string }) {
  const blocks = text.split(/\n{2,}/).map((b) => b.trim()).filter(Boolean)
  return (
    <div className="space-y-2 text-[12px] leading-relaxed text-[var(--ink)]">
      {blocks.map((block, i) => {
        const lines = block.split('\n')
        const isQuote = lines.every((l) => l.trimStart().startsWith('>'))
        if (isQuote) {
          const inner = lines
            .map((l) => l.replace(/^\s*>\s?/, ''))
            .join(' ')
          return (
            <blockquote
              key={i}
              className="border-l-2 border-[var(--brand)] pl-3 py-0.5 text-[var(--muted)] italic"
            >
              {inner}
            </blockquote>
          )
        }
        return (
          <p key={i} className="text-[var(--ink)]">
            {block}
          </p>
        )
      })}
    </div>
  )
}

function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
}
