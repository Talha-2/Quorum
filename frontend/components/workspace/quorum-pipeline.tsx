'use client'

import React, { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  RotateCcw,
  Sparkles,
  Loader2,
  Bot,
  CheckCircle2,
  Users,
} from 'lucide-react'

import { pipelineApi } from '@/lib/pipeline-api'
import { getErrorMessage } from '@/lib/api-client'
import type {
  AgentProfile,
  Project,
  ProjectState,
} from '@/types/pipeline'

import GraphCanvasD3 from '@/components/graph/graph-canvas-d3'
import type { D3GraphNode, D3GraphEdge } from '@/components/graph/graph-canvas-d3'

import StageCard, {
  StageActionButton,
  StageChips,
  StageStat,
} from '@/components/pipeline/stage-card'
import StageConfigCard from '@/components/pipeline/stage-config-card'
import StageActivationCard from '@/components/pipeline/stage-activation-card'
import StageReportCard from '@/components/pipeline/stage-report-card'
import SystemDashboard from '@/components/pipeline/system-dashboard'
import AgentChatPanel from '@/components/pipeline/agent-chat-panel'
import AgentDetailModal from '@/components/pipeline/agent-detail-modal'
import FileUploadField from '@/components/pipeline/file-upload-field'
import QuorumGraphView from '@/components/workspace/quorum-graph-view'
import QuorumAgentsView from '@/components/workspace/quorum-agents-view'

import QuorumMark from '@/components/site/quorum-mark'
import ThemeToggle from '@/components/site/theme-toggle'

// ============ Helpers ============

const STATE_LABEL: Record<ProjectState, string> = {
  created: 'Created',
  ontology_generated: 'Ontology ready',
  graph_building: 'Graph building',
  graph_completed: 'Graph ready',
  env_ready: 'Env ready',
  config_ready: 'Config ready',
  activation_ready: 'Activation ready',
  simulating: 'Simulating',
  sim_completed: 'Simulation done',
  report_ready: 'Report ready',
  failed: 'Failed',
}

type ViewMode = 'pipeline' | 'graph' | 'agents'

/**
 * Map a backend pipeline graph to the shape the d3-force canvas wants.
 * The canvas handles its own layout via d3-force; we just hand it nodes + edges.
 */
function mapPipelineGraphD3(project: Project | null): {
  nodes: D3GraphNode[]
  edges: D3GraphEdge[]
} {
  if (!project?.graph) return { nodes: [], edges: [] }
  return {
    nodes: project.graph.nodes.map((n) => ({
      id: n.id,
      name: n.name,
      type: n.type,
      description: n.description,
      is_individual: n.is_individual,
    })),
    edges: project.graph.edges.map((e) => ({
      id: e.id,
      source: e.source_id,
      target: e.target_id,
      type: e.type,
      description: e.description,
    })),
  }
}

// ============ Component ============

export default function QuorumPipeline() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [project, setProject] = useState<Project | null>(null)
  const [briefDraft, setBriefDraft] = useState('')
  const [constraintsDraft, setConstraintsDraft] = useState('')
  const [domainDraft, setDomainDraft] = useState<string>('general')
  const [availableDomains, setAvailableDomains] = useState<
    { key: string; name: string; description: string }[]
  >([])
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [view, setView] = useState<ViewMode>('pipeline')
  const [error, setError] = useState<string | null>(null)
  const [createLoading, setCreateLoading] = useState(false)
  const [ontologyLoading, setOntologyLoading] = useState(false)
  const [graphLoading, setGraphLoading] = useState(false)
  const [stage2Loading, setStage2Loading] = useState(false)
  const [stage3Loading, setStage3Loading] = useState(false)
  const [activationLoading, setActivationLoading] = useState(false)
  const [stage4Loading, setStage4Loading] = useState(false)
  const [stage5Loading, setStage5Loading] = useState(false)
  const [projectLoading, setProjectLoading] = useState(false)
  const [chatAgent, setChatAgent] = useState<AgentProfile | null>(null)
  const [detailAgent, setDetailAgent] = useState<AgentProfile | null>(null)

  // Selected node id (for the right sidebar / chat panel coordination).
  // The d3 canvas manages its own visual selection internally.
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  // Memoized d3 graph data — recomputed whenever the project graph changes.
  // The d3 canvas does its own incremental layout via the force simulation.
  const d3Graph = useMemo(() => mapPipelineGraphD3(project), [project])

  const status = project?.state ?? 'created'
  const isInitialized = project !== null
  const anyStageLoading =
    createLoading ||
    ontologyLoading ||
    graphLoading ||
    stage2Loading ||
    stage3Loading ||
    activationLoading ||
    stage4Loading ||
    stage5Loading ||
    projectLoading

  useEffect(() => {
    // Load the list of available domains so the user can pick one when
    // creating a new project. Best-effort — falls back to "general" if the
    // backend is unreachable at this moment.
    let cancelled = false
    pipelineApi
      .listDomains()
      .then((resp) => {
        if (!cancelled) setAvailableDomains(resp.domains)
      })
      .catch(() => {
        /* leave the picker hidden if we can't fetch */
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const requestedView = searchParams.get('view')
    if (
      requestedView === 'pipeline' ||
      requestedView === 'graph' ||
      requestedView === 'agents'
    ) {
      setView(requestedView)
    }
  }, [searchParams])

  useEffect(() => {
    const projectId = searchParams.get('project')
    if (!projectId || project?.id === projectId) return

    let cancelled = false
    setError(null)
    setProjectLoading(true)

    pipelineApi
      .getProject(projectId)
      .then((proj) => {
        if (!cancelled) {
          setProject(proj)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(getErrorMessage(err))
        }
      })
      .finally(() => {
        if (!cancelled) {
          setProjectLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [project?.id, searchParams])

  // ============ Stage actions ============

  const handleCreateProject = async () => {
    if (!briefDraft.trim()) return
    setError(null)
    setCreateLoading(true)
    try {
      // 1. Create project
      let proj = await pipelineApi.createProject({
        brief: briefDraft.trim(),
        constraints: constraintsDraft.trim(),
        domain: domainDraft,
      })
      setProject(proj)

      // 2. Upload any reality-seed files (sequentially so the events log
      //    shows each upload as it happens)
      for (const file of pendingFiles) {
        try {
          proj = await pipelineApi.uploadDocument(proj.id, file)
          setProject(proj)
        } catch (uploadErr) {
          // Log but don't abort — let the user know one file failed but
          // continue with the rest of the pipeline
          console.warn(`Failed to upload ${file.name}:`, uploadErr)
        }
      }

    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setCreateLoading(false)
    }
  }

  const handleGenerateOntology = async () => {
    if (!project) return
    setError(null)
    setOntologyLoading(true)
    try {
      const proj = await pipelineApi.generateOntology(project.id)
      setProject(proj)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setOntologyLoading(false)
    }
  }

  const handleBuildGraph = async () => {
    if (!project) return
    setError(null)
    setGraphLoading(true)
    try {
      const proj = await pipelineApi.buildGraph(project.id)
      setProject(proj)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setGraphLoading(false)
    }
  }

  const handleGenerateReport = async () => {
    if (!project) return
    setError(null)
    setStage5Loading(true)
    try {
      const proj = await pipelineApi.generateReport(project.id)
      setProject(proj)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setStage5Loading(false)
    }
  }

  const handleEnvSetup = async () => {
    if (!project) return
    setError(null)
    setStage2Loading(true)
    try {
      const proj = await pipelineApi.setupEnv(project.id)
      setProject(proj)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setStage2Loading(false)
    }
  }

  const handleStartSimulation = async () => {
    if (!project) return
    setError(null)
    setStage4Loading(true)
    try {
      const proj = await pipelineApi.startSimulation(project.id, 3, 4)
      setProject(proj)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setStage4Loading(false)
    }
  }

  const handleGenerateActivation = async () => {
    if (!project) return
    setError(null)
    setActivationLoading(true)
    try {
      const proj = await pipelineApi.activateSimulation(project.id)
      setProject(proj)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setActivationLoading(false)
    }
  }

  const handleReset = () => {
    setProject(null)
    setBriefDraft('')
    setConstraintsDraft('')
    setPendingFiles([])
    setError(null)
    setChatAgent(null)
    setDetailAgent(null)
    setSelectedNodeId(null)
    setView('pipeline')
    router.replace('/workspace')
  }

  // d3 canvas → click handler. If the clicked node maps to an agent, open
  // the rich detail modal; otherwise just remember the selection.
  const handleD3NodeClick = (node: D3GraphNode) => {
    setSelectedNodeId(node.id)
    if (project?.agents) {
      const matched = project.agents.find(
        (a) => a.source_entity_id === node.id || a.id === node.id
      )
      if (matched) setDetailAgent(matched)
    }
  }

  // Stage 04 — Generate Config (calls /simulation/prepare)
  const handlePrepareSimulation = async () => {
    if (!project) return
    setError(null)
    setStage3Loading(true)
    try {
      const proj = await pipelineApi.prepareSimulation(project.id)
      setProject(proj)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setStage3Loading(false)
    }
  }

  // Stage status computations
  const stage1Status = useMemo(() => {
    if (!project) return 'pending'
    if (ontologyLoading) return 'processing'
    if (project.ontology) return 'complete'
    return 'pending'
  }, [project, ontologyLoading]) as
    | 'pending'
    | 'processing'
    | 'complete'
    | 'failed'

  const stage1bStatus = useMemo(() => {
    if (!project) return 'pending'
    if (graphLoading || project.state === 'graph_building') return 'processing'
    if (project.graph_stats) return 'complete'
    return 'pending'
  }, [project, graphLoading]) as
    | 'pending'
    | 'processing'
    | 'complete'
    | 'failed'

  const stage2Status = useMemo(() => {
    if (!project) return 'pending'
    if (stage2Loading) return 'processing'
    if (project.agent_count > 0) return 'complete'
    return 'pending'
  }, [project, stage2Loading]) as
    | 'pending'
    | 'processing'
    | 'complete'
    | 'failed'

  // Stage 04 — Generate Config
  const stage3Status = useMemo(() => {
    if (!project) return 'pending'
    if (stage3Loading) return 'processing'
    if (project.simulation_parameters) return 'complete'
    return 'pending'
  }, [project, stage3Loading]) as
    | 'pending'
    | 'processing'
    | 'complete'
    | 'failed'

  // Stage 05 — Initial Activation
  const stage4ActivationStatus = useMemo(() => {
    if (!project) return 'pending'
    if (activationLoading) return 'processing'
    if (project.activation) return 'complete'
    return 'pending'
  }, [project, activationLoading]) as
    | 'pending'
    | 'processing'
    | 'complete'
    | 'failed'

  // Stage 06 — Run Simulation
  const stage4Status = useMemo(() => {
    if (!project) return 'pending'
    if (stage4Loading) return 'processing'
    if (project.consensus) return 'complete'
    return 'pending'
  }, [project, stage4Loading]) as
    | 'pending'
    | 'processing'
    | 'complete'
    | 'failed'

  // Stage 07 — Generate Report
  const stage5ReportStatus = useMemo(() => {
    if (!project) return 'pending'
    if (stage5Loading) return 'processing'
    if (project.report) return 'complete'
    return 'pending'
  }, [project, stage5Loading]) as
    | 'pending'
    | 'processing'
    | 'complete'
    | 'failed'

  // Stage 08 — Deep Interaction
  const stage5Status = useMemo(() => {
    if (!project) return 'pending'
    if (project.consensus) return 'complete'
    return 'pending'
  }, [project]) as 'pending' | 'processing' | 'complete' | 'failed'

  const events = project?.events ?? []

  return (
    <div className="h-screen w-full bg-[var(--bg)] overflow-hidden flex flex-col">
      {/* ============ Header ============ */}
      <header className="border-b border-[var(--line)] bg-[var(--bg)] px-6 h-14 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-6">
          <a href="/" className="flex items-center gap-2.5 group">
            <span className="text-[var(--brand)] inline-flex group-hover:rotate-12 transition-transform">
              <QuorumMark size={26} />
            </span>
            <span className="font-display text-base font-semibold tracking-tight text-[var(--ink)]">
              Quorum
            </span>
          </a>

          {/* View tabs */}
          <div className="flex items-center bg-[var(--bg-soft)] border border-[var(--line)] rounded-md p-0.5">
            {(['pipeline', 'graph', 'agents'] as ViewMode[]).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`px-3 py-1 text-xs font-mono uppercase tracking-wider rounded transition-colors ${
                  view === v
                    ? 'bg-[var(--card)] text-[var(--ink)] shadow-sm'
                    : 'text-[var(--muted)] hover:text-[var(--ink)]'
                }`}
              >
                {v === 'pipeline'
                  ? 'Workbench'
                  : v === 'graph'
                    ? 'Graph'
                    : 'Agents'}
              </button>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--bg-soft)] border border-[var(--line)]">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                status === 'simulating' || status === 'graph_building'
                  ? 'bg-[var(--brand)] pulse-dot'
                  : status === 'sim_completed' ||
                      status === 'env_ready' ||
                      status === 'graph_completed'
                    ? 'bg-[#00C851]'
                    : status === 'failed'
                      ? 'bg-[#b3473d]'
                      : 'bg-[var(--muted-soft)]'
              }`}
            />
            <span className="text-[11px] font-mono uppercase tracking-wider text-[var(--muted)]">
              {STATE_LABEL[status as ProjectState] ?? status}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <a href="/docs" className="btn btn-ghost btn-sm">
            Docs
          </a>
          {isInitialized && (
            <button
              onClick={handleReset}
              disabled={anyStageLoading}
              className="btn btn-primary btn-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              New project
            </button>
          )}
        </div>
      </header>

      {/* Error banner */}
      {error && (
        <div className="px-6 py-2 bg-[var(--brand-tint)] border-b border-[var(--brand)] text-sm text-[var(--ink)]">
          {error}
        </div>
      )}

      {/* ============ Main content ============ */}
      <div className="flex-1 overflow-hidden flex">
        {!isInitialized ? (
          // Empty state — initial form
          <div className="flex-1 flex items-center justify-center p-6 overflow-y-auto bg-[var(--bg-soft)]">
            <div className="w-full max-w-2xl">
              <div className="bg-[var(--card)] border border-[var(--line)] rounded-lg overflow-hidden">
                <div className="px-8 py-6 border-b border-[var(--line)] bg-[var(--bg-soft)]">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="h-3.5 w-3.5 text-[var(--brand)]" />
                    <span className="label-mono">New project</span>
                  </div>
                  <h2 className="font-display text-2xl font-medium tracking-tight text-[var(--ink)]">
                    Spin up a swarm
                  </h2>
                  <p className="mt-2 text-sm text-[var(--muted)]">
                    Describe the topic. Quorum will design an ontology, build a
                    knowledge graph, instantiate one agent per real-world entity,
                    and run a multi-round debate.
                  </p>
                </div>
                <div className="p-8 space-y-6">
                  {projectLoading ? (
                    <div className="flex flex-col items-center justify-center py-10 text-center">
                      <Loader2 className="h-6 w-6 animate-spin text-[var(--brand)]" />
                      <p className="mt-4 text-sm text-[var(--muted)]">
                        Loading existing project…
                      </p>
                    </div>
                  ) : (
                    <>
                  <div>
                    <label className="label-mono mb-2 block">Brief</label>
                    <textarea
                      value={briefDraft}
                      onChange={(e) => setBriefDraft(e.target.value)}
                      placeholder="What should the swarm debate? E.g. 'A 64-year-old with HER2+ stage IIA disease' (oncology MDT) or 'Should we adopt the new workflow next quarter?' (general)"
                      className="input min-h-[120px] resize-y"
                      rows={4}
                    />
                  </div>
                  {availableDomains.length > 1 && (
                    <div>
                      <label className="label-mono mb-2 block">Domain</label>
                      <select
                        value={domainDraft}
                        onChange={(e) => setDomainDraft(e.target.value)}
                        className="input"
                      >
                        {availableDomains.map((d) => (
                          <option key={d.key} value={d.key}>
                            {d.name}
                          </option>
                        ))}
                      </select>
                      <p className="mt-2 text-[11px] text-[var(--muted)] leading-relaxed">
                        {availableDomains.find((d) => d.key === domainDraft)?.description}
                      </p>
                    </div>
                  )}
                  <div>
                    <label className="label-mono mb-2 block">
                      Constraints (optional)
                    </label>
                    <textarea
                      value={constraintsDraft}
                      onChange={(e) => setConstraintsDraft(e.target.value)}
                      placeholder="One per line"
                      className="input min-h-[72px] resize-y font-mono text-[13px]"
                      rows={2}
                    />
                  </div>
                  <FileUploadField
                    files={pendingFiles}
                    onFilesChange={setPendingFiles}
                    disabled={createLoading}
                  />
                  <button
                    onClick={handleCreateProject}
                    disabled={createLoading || !briefDraft.trim()}
                    className="btn btn-primary btn-lg w-full disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {createLoading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Creating project…
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" />
                        Create project
                      </>
                    )}
                  </button>
                  <p className="text-[11px] text-[var(--muted)] text-center">
                    Backend: <span className="font-mono">localhost:8000</span> ·
                    LLM: <span className="font-mono text-[var(--brand)]">google/gemini</span>
                  </p>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : view === 'graph' ? (
          // Full-screen graph view
          <QuorumGraphView project={project} onChatWithAgent={setChatAgent} />
        ) : view === 'agents' ? (
          // Full-screen agents gallery
          <QuorumAgentsView project={project} onChatWithAgent={setChatAgent} />
        ) : (
          // WORKBENCH (default) — pipeline view with mini graph + stage cards
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] min-h-0">
            {/* Left: graph */}
            <div className="flex flex-col p-3 min-w-0 min-h-0 border-r border-[var(--line)]">
              <div className="flex-1 min-h-0">
                <GraphCanvasD3
                  nodes={d3Graph.nodes}
                  edges={d3Graph.edges}
                  selectedNodeId={selectedNodeId}
                  onNodeClick={handleD3NodeClick}
                  height="h-full"
                  showLegend={false}
                />
              </div>
            </div>

            {/* Right: stage cards */}
            <div className="overflow-y-auto p-4 space-y-4 bg-[var(--bg-soft)]">
              {/* Stage 1a — Ontology */}
              <StageCard
                number="01"
                title="Ontology Generation"
                endpoint="/api/projects/{id}/graph/ontology/generate"
                description="LLM analyzes the brief and automatically generates a topic-specific ontology of entity types and relationship types."
                status={stage1Status}
                action={
                  project &&
                  !project.ontology && (
                    <StageActionButton
                      onClick={handleGenerateOntology}
                      disabled={ontologyLoading}
                    >
                      {ontologyLoading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Generating ontology…
                        </>
                      ) : (
                        'Generate ontology'
                      )}
                    </StageActionButton>
                  )
                }
              >
                {project?.ontology && (
                  <div className="space-y-4">
                    <StageChips
                      label="Generated entity types"
                      items={project.ontology.entity_types.map((e) => e.name)}
                    />
                    <StageChips
                      label="Generated relation types"
                      items={project.ontology.edge_types.map((e) => e.name)}
                    />
                  </div>
                )}
              </StageCard>

              {/* Stage 1b — GraphRAG Build */}
              <StageCard
                number="02"
                title="GraphRAG Build"
                endpoint="/api/projects/{id}/graph/build"
                description="Based on the generated ontology, extracts every concrete entity and every relationship from the brief into a typed knowledge graph."
                status={stage1bStatus}
                action={
                  project?.ontology &&
                  !project.graph_stats && (
                    <StageActionButton
                      onClick={handleBuildGraph}
                      disabled={graphLoading}
                    >
                      {graphLoading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Building graph…
                        </>
                      ) : (
                        'Build knowledge graph'
                      )}
                    </StageActionButton>
                  )
                }
              >
                {project?.graph_stats && (
                  <div className="grid grid-cols-3 gap-4 py-2">
                    <StageStat
                      value={project.graph_stats.entity_nodes}
                      label="Entity nodes"
                    />
                    <StageStat
                      value={project.graph_stats.relation_edges}
                      label="Relation edges"
                    />
                    <StageStat
                      value={project.graph_stats.schema_types}
                      label="Schema types"
                    />
                  </div>
                )}
              </StageCard>

              {/* Stage 2 — Env Setup */}
              <StageCard
                number="03"
                title="Environment Setup"
                endpoint="/api/projects/{id}/env/setup"
                description="One agent is generated per real-world entity in the graph. Each persona is LLM-designed with a stance, bias, and personality based on the entity it represents."
                status={stage2Status}
                action={
                  project?.graph_stats &&
                  !project.agent_count && (
                    <StageActionButton
                      onClick={handleEnvSetup}
                      disabled={stage2Loading}
                    >
                      {stage2Loading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Generating personas…
                        </>
                      ) : (
                        'Generate agent personas'
                      )}
                    </StageActionButton>
                  )
                }
              >
                {project && project.agent_count > 0 && (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-[var(--ink)]">
                      <Users className="h-4 w-4 text-[var(--brand)]" />
                      <span className="text-sm">
                        <span className="font-display text-base font-medium">
                          {project.agent_count}
                        </span>{' '}
                        <span className="text-[var(--muted)]">
                          agents instantiated from graph entities
                        </span>
                      </span>
                    </div>
                    {project.agents && project.agents.length > 0 && (
                      <div className="grid grid-cols-2 gap-2 max-h-[200px] overflow-y-auto pr-1">
                        {project.agents.slice(0, 12).map((a) => (
                          <button
                            key={a.id}
                            onClick={() => setDetailAgent(a)}
                            className="text-left p-2 bg-[var(--bg-soft)] border border-[var(--line)] rounded hover:border-[var(--brand)] hover:bg-[var(--brand-tint)] transition-colors"
                          >
                            <div className="flex items-center gap-1.5">
                              <Bot className="h-3 w-3 text-[var(--brand)] flex-shrink-0" />
                              <p className="text-[11px] font-medium text-[var(--ink)] truncate">
                                {a.name}
                              </p>
                            </div>
                            <p className="text-[10px] font-mono text-[var(--muted)] truncate mt-0.5">
                              @{a.user_name}
                            </p>
                            <p className="text-[10px] text-[var(--muted)] truncate mt-0.5">
                              {a.role}
                            </p>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </StageCard>

              {/* Stage 04 — Generate Config */}
              <StageConfigCard
                number="04"
                status={stage3Status}
                params={project?.simulation_parameters ?? null}
                onGenerate={project?.agent_count ? handlePrepareSimulation : undefined}
                loading={stage3Loading}
              />

              {/* Stage 05 — Initial Activation Orchestration (NEW) */}
              <StageActivationCard
                number="05"
                status={stage4ActivationStatus}
                event={project?.activation ?? null}
                agents={project?.agents}
                onGenerate={project?.simulation_parameters ? handleGenerateActivation : undefined}
                loading={activationLoading}
              />

              {/* Stage 06 — Simulation */}
              <StageCard
                number="06"
                title="Run Simulation"
                endpoint="/api/projects/{id}/simulation/start"
                description="Round-by-round debate. Each round selects a diverse subset of agents who reason about the brief in character, given the running transcript."
                status={stage4Status}
                action={
                  project &&
                  project.activation &&
                  !project.consensus && (
                    <StageActionButton
                      onClick={handleStartSimulation}
                      disabled={stage4Loading}
                    >
                      {stage4Loading ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Running rounds…
                        </>
                      ) : (
                        'Start simulation'
                      )}
                    </StageActionButton>
                  )
                }
              >
                {project?.debate_messages && project.debate_messages.length > 0 && (
                  <div className="space-y-2">
                    <p className="label-mono">
                      Debate transcript ({project.debate_messages.length} messages)
                    </p>
                    <div className="max-h-[260px] overflow-y-auto space-y-2 pr-1">
                      {project.debate_messages.map((m) => (
                        <div
                          key={m.id}
                          className="p-2 bg-[var(--bg-soft)] border border-[var(--line)] rounded text-xs"
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-medium text-[var(--ink)]">
                              {m.agent_name}
                            </span>
                            <span className="text-[10px] font-mono text-[var(--muted)]">
                              R{m.round} · {m.stance}
                            </span>
                          </div>
                          <p className="text-[var(--muted)] leading-relaxed">
                            {m.content}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {project?.consensus && (
                  <div className="mt-4 p-3 bg-[var(--brand-tint)] border border-[var(--brand)]/30 rounded">
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircle2 className="h-4 w-4 text-[var(--brand)]" />
                      <span className="label-mono text-[var(--brand)]">Consensus</span>
                    </div>
                    <p className="text-xs text-[var(--ink)] leading-relaxed">
                      {project.consensus.agreed_position}
                    </p>
                    <div className="mt-2 flex gap-3 text-[10px] font-mono text-[var(--muted)]">
                      <span>
                        Agreement: {(project.consensus.agreement_rate * 100).toFixed(0)}%
                      </span>
                      <span>
                        Confidence: {(project.consensus.confidence_level * 100).toFixed(0)}%
                      </span>
                      {project.consensus.dissents.length > 0 && (
                        <span>{project.consensus.dissents.length} dissents</span>
                      )}
                    </div>
                  </div>
                )}
              </StageCard>

              {/* Stage 07 — Generate Report (NEW) */}
              <StageReportCard
                number="07"
                status={stage5ReportStatus}
                report={project?.report ?? null}
                onGenerate={handleGenerateReport}
                loading={stage5Loading}
              />

              {/* Stage 08 — Deep Interaction */}
              <StageCard
                number="08"
                title="Deep Interaction"
                endpoint="/api/projects/{id}/agents/{agent_id}/chat"
                description="Chat with any individual agent in the simulated world. Each agent responds in character, drawing on its persona and the post-debate state."
                status={stage5Status}
              >
                {project?.consensus ? (
                  <p className="text-xs text-[var(--muted)]">
                    Click any agent above (or any node on the graph) to ask them a
                    follow-up question.
                  </p>
                ) : (
                  <p className="text-xs text-[var(--muted)]">
                    Available after the simulation finishes.
                  </p>
                )}
              </StageCard>
            </div>
          </div>
        )}
      </div>

      {/* ============ System dashboard ============ */}
      <SystemDashboard events={events} projectId={project?.id} />

      {/* ============ Floating chat panel ============ */}
      {chatAgent && project && (
        <AgentChatPanel
          projectId={project.id}
          agent={chatAgent}
          onClose={() => setChatAgent(null)}
        />
      )}

      {/* ============ Agent detail modal ============ */}
      <AgentDetailModal
        agent={detailAgent}
        onClose={() => setDetailAgent(null)}
        onChat={(a) => setChatAgent(a)}
      />
    </div>
  )
}
