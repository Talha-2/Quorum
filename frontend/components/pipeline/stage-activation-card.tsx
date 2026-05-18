'use client'

import React from 'react'
import { Compass, Hash } from 'lucide-react'
import StageCard, { StageActionButton } from '@/components/pipeline/stage-card'
import type { EventConfig, AgentProfile } from '@/types/pipeline'
import type { StageStatus } from '@/components/pipeline/stage-card'

interface StageActivationCardProps {
  number: string
  status: StageStatus
  event: EventConfig | null
  agents?: AgentProfile[]
  onGenerate?: () => void
  loading?: boolean
}

export default function StageActivationCard({
  number,
  status,
  event,
  agents = [],
  onGenerate,
  loading = false,
}: StageActivationCardProps) {
  return (
    <StageCard
      number={number}
      title="Initial Activation Orchestration"
      endpoint="/api/projects/{id}/simulation/activate"
      description="Generate the narrative direction, hot topics, and starter posts that seed round zero before the live debate begins."
      status={status}
      action={
        !event && onGenerate ? (
          <StageActionButton onClick={onGenerate} disabled={loading}>
            {loading ? 'Generating activation…' : 'Generate activation plan'}
          </StageActionButton>
        ) : undefined
      }
    >
      {event && (
        <div className="space-y-5">
          {event.narrative_direction && (
            <NarrativeCard direction={event.narrative_direction} />
          )}
          {event.hot_topics.length > 0 && <HotTopicsRow topics={event.hot_topics} />}
          {event.initial_posts.length > 0 && (
            <ActivationSequence posts={event.initial_posts} agents={agents} />
          )}
        </div>
      )}
    </StageCard>
  )
}

// ============================================
// Narrative direction
// ============================================
function NarrativeCard({ direction }: { direction: string }) {
  return (
    <div className="bg-[var(--brand-tint)] border border-[var(--brand)]/30 rounded-md p-4">
      <div className="flex items-center gap-2 mb-2">
        <Compass className="h-3.5 w-3.5 text-[var(--brand)]" />
        <span className="label-mono text-[var(--brand)]">Narrative guide direction</span>
      </div>
      <p className="text-[12px] text-[var(--ink)] leading-relaxed">{direction}</p>
    </div>
  )
}

// ============================================
// Hot topics — colored hashtag pills
// ============================================
function HotTopicsRow({ topics }: { topics: string[] }) {
  return (
    <div>
      <p className="label-mono mb-2">Initial hot topics</p>
      <div className="flex flex-wrap gap-1.5">
        {topics.map((t) => (
          <span
            key={t}
            className="inline-flex items-center gap-1 px-2 py-1 rounded bg-[var(--brand-soft)] border border-[var(--brand)]/20 text-[11px] font-medium text-[var(--brand)]"
          >
            <Hash className="h-2.5 w-2.5" />
            {t}
          </span>
        ))}
      </div>
    </div>
  )
}

// ============================================
// Initial activation sequence — list of starter posts
// ============================================
function ActivationSequence({
  posts,
  agents,
}: {
  posts: { content: string; poster_type: string; poster_agent_id: number | null }[]
  agents: AgentProfile[]
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="label-mono">Initial activation sequence</p>
        <span className="text-[10px] font-mono text-[var(--muted)]">
          {posts.length} posts
        </span>
      </div>
      <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
        {posts.map((post, i) => (
          <PostCard key={i} post={post} index={i} agents={agents} />
        ))}
      </div>
    </div>
  )
}

function PostCard({
  post,
  index,
  agents,
}: {
  post: { content: string; poster_type: string; poster_agent_id: number | null }
  index: number
  agents: AgentProfile[]
}) {
  // Try to resolve agent_id back to a real agent name. agent_id is the
  // batch index from the config generator (0-based offset in agents list).
  const matchingAgent =
    typeof post.poster_agent_id === 'number' ? agents[post.poster_agent_id] : null

  return (
    <div className="bg-[var(--bg-soft)] border border-[var(--line)] rounded-md p-3">
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--brand)]">
          {post.poster_type || 'Unknown'}
        </span>
        <span className="text-[10px] font-mono text-[var(--muted)] flex-shrink-0">
          Agent {post.poster_agent_id ?? '?'}
          {matchingAgent ? ` @${matchingAgent.user_name}` : ''}
        </span>
      </div>
      <p className="text-[12px] text-[var(--ink)] leading-relaxed">{post.content}</p>
    </div>
  )
}
