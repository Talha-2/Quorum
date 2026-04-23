'use client'

import React, { useState } from 'react'
import { useGraph } from '@/hooks/useGraph'
import { useDebate } from '@/hooks/useDebate'
import { useSimulation } from '@/hooks/useSimulation'
import { GraphNode } from '@/types/graph'
import { Agent, DebateMessage, Consensus } from '@/types/debate'
import GraphCanvas from '@/components/graph/graph-canvas'
import GraphControls from '@/components/graph/graph-controls'
import GraphLegend from '@/components/graph/graph-legend'
import DebatePanel from '@/components/debate/debate-panel'
import MetricsDashboard from '@/components/metrics/metrics-dashboard'
import ControlPanel from '@/components/control/control-panel'
import QuorumMark from '@/components/site/quorum-mark'
import ThemeToggle from '@/components/site/theme-toggle'
import { motion } from 'framer-motion'
import { AlertCircle, RotateCcw } from 'lucide-react'
import { apiClient, getErrorMessage } from '@/lib/api-client'

interface QuorumWorkspaceProps {
  initialDomain?: string
}

export default function QuorumWorkspace({ initialDomain = 'generic' }: QuorumWorkspaceProps) {
  const {
    state: graphState,
    updateGraphData,
    addNode,
    addEdge,
    setZoomLevel,
    setPanPosition,
    resetView,
    animateNode,
    updateNodePosition,
  } = useGraph()
  const simulationController = useSimulation()

  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const [legendOpen, setLegendOpen] = useState(false)
  const [filterMode, setFilterMode] = useState('all')
  const [isInitialized, setIsInitialized] = useState(false)

  // Initialize debate controller — agents are replaced with backend agents on launch
  const debateController = useDebate([], 3)

  // Map backend agents to frontend Agent format
  const mapBackendAgents = (backendAgents: any[]): Agent[] => {
    return backendAgents.map((a: any) => ({
      id: a.id,
      name: a.name,
      role: a.expertise?.[1] || a.name,
      personality: {
        optimism: a.personality?.optimism ?? 0.5,
        riskTolerance: a.personality?.risk_tolerance ?? 0.5,
        caution: a.personality?.caution ?? 0.5,
        decisiveness: a.personality?.speed_preference ?? 0.5,
      },
      expertise: a.expertise || [],
    }))
  }

  // Pick sentiment based on agent personality
  const sentimentFor = (agent: any): 'negative' | 'positive' | 'neutral' => {
    const optimism = agent?.personality?.optimism ?? 0.5
    if (optimism > 0.6) return 'positive'
    if (optimism < 0.4) return 'negative'
    return 'neutral'
  }

  // Pull a short theme keyword from a longer message
  const extractTheme = (text: string): string => {
    const stopWords = new Set([
      'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
      'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have',
      'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
      'may', 'might', 'must', 'shall', 'can', 'this', 'that', 'these', 'those',
      'we', 'they', 'it', 'i', 'you', 'he', 'she', 'them', 'their', 'our',
      'from', 'as', 'if', 'so', 'about', 'than', 'then', 'because', 'while',
      'which', 'who', 'what', 'when', 'where', 'why', 'how', 'not', 'no', 'yes',
      'also', 'too', 'very', 'just', 'only', 'one', 'two', 'into', 'over',
    ])
    const words = text
      .toLowerCase()
      .replace(/[^a-z\s]/g, ' ')
      .split(/\s+/)
      .filter(w => w.length > 4 && !stopWords.has(w))
    if (words.length === 0) return 'topic'
    // Take first non-stopword
    return words[0].charAt(0).toUpperCase() + words[0].slice(1)
  }

  // Compute a position on a ring around the graph center
  const positionOnRing = (
    index: number,
    total: number,
    radius: number,
    cx = 400,
    cy = 280,
    offset = -Math.PI / 2
  ) => {
    const angle = offset + (index / Math.max(total, 1)) * Math.PI * 2
    return {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    }
  }

  // Handle simulation initialization
  const handleInitialize = async (config: any) => {
    try {
      simulationController.initializeSimulation(config)
      setIsInitialized(true)
      simulationController.setStatus('initializing')

      // Resolve user-selected parameters once and use them everywhere
      const userRounds = Math.max(1, Math.min(config.debate?.rounds || 3, 10))
      const userAgentCount = Math.max(2, Math.min(config.agents?.count || 6, 12))
      const userComplexity = config.agents?.complexity || 'high'

      // Push the chosen rounds into the debate hook so the UI shows X / Y correctly
      debateController.setTotalRounds(userRounds)

      const constraintsArr: string[] = config.artifacts?.constraints || []
      const artifactsPayload = {
        brief: config.artifacts?.brief || '',
        constraints: constraintsArr.join('\n') || 'No specific constraints',
        signals: 'User-provided topic for multi-agent analysis',
      }

      // 1. Initialize a generic simulation on the backend
      const initResponse: any = await apiClient.post('/initialize/generic', {
        artifacts: artifactsPayload,
        swarm: {
          debate_rounds: userRounds,
          agent_count: userAgentCount,
          scenario_complexity: userComplexity,
        },
      })

      const simId = initResponse.simulation_id
      const backendAgents = initResponse.agents || []

      // 2. Replace local agents with backend agents in the debate state
      const realAgents = mapBackendAgents(backendAgents)
      debateController.setAgents(realAgents)

      // 3. Seed the graph with ONLY the context + brief artifact (incremental build)
      const briefText = config.artifacts?.brief || 'Topic'
      const seedNodes: GraphNode[] = [
        {
          id: 'ctx-root',
          label: 'Decision context',
          type: 'context',
          position: { x: 400, y: 280 },
          data: { importance: 1, description: briefText },
        },
        {
          id: 'artifact-brief',
          label: 'Brief',
          type: 'entity',
          position: { x: 200, y: 280 },
          data: { importance: 0.9, description: briefText },
        },
      ]
      const seedEdges: import('@/types/graph').GraphEdge[] = [
        {
          id: 'edge-brief',
          source: 'artifact-brief',
          target: 'ctx-root',
          type: 'depends_on',
        },
      ]
      // Add constraint nodes
      constraintsArr.slice(0, 3).forEach((c, i) => {
        const id = `constraint-${i}`
        seedNodes.push({
          id,
          label: c.length > 18 ? c.slice(0, 18) + '…' : c,
          type: 'blocker',
          position: positionOnRing(i, Math.max(constraintsArr.length, 3), 130, 400, 280, Math.PI),
          data: { importance: 0.7, description: c },
        })
        seedEdges.push({
          id: `edge-c-${i}`,
          source: id,
          target: 'ctx-root',
          type: 'blocks' as const,
        })
      })
      updateGraphData({ nodes: seedNodes, edges: seedEdges })

      // 4. Start debate
      debateController.startDebate()
      simulationController.setStatus('running')

      // 5. Send the user's brief to /chat to get LLM-generated agent responses + consensus
      await runBackendDebate(simId, config, realAgents, backendAgents)
    } catch (error) {
      console.error('Simulation error:', error)
      simulationController.setError(getErrorMessage(error))
      simulationController.setStatus('error')
    }
  }

  // Run debate via backend chat endpoint
  const runBackendDebate = async (
    simId: string,
    config: any,
    agents: Agent[],
    backendAgentProfiles: any[]
  ) => {
    const brief: string = config.artifacts?.brief || 'Discuss the topic'
    const totalRounds: number = config.debate?.rounds || 3

    // Call backend chat with consensus
    const chatResponse: any = await apiClient.post(`/chat/${simId}`, {
      message: brief,
      get_consensus: true,
      swarm: {
        debate_rounds: totalRounds,
        max_debate_agents: Math.min(6, agents.length),
      },
    })

    const responses: any[] = chatResponse.responses || []
    const messagesPerRound = Math.max(1, Math.ceil(responses.length / totalRounds))

    // Track which agents already have nodes in the graph (so we add each only once)
    const spawnedAgentIds = new Set<string>()
    // Track theme nodes already created
    const themeNodeIds = new Set<string>()

    let messageIdx = 0
    for (let round = 1; round <= totalRounds; round++) {
      const roundMessages = responses.slice(
        (round - 1) * messagesPerRound,
        round * messagesPerRound
      )

      for (let i = 0; i < roundMessages.length; i++) {
        const r = roundMessages[i]
        await new Promise(resolve => setTimeout(resolve, 1100))

        const matchingAgent = agents.find(a => a.name === r.agent)
        const matchingProfile = backendAgentProfiles.find(p => p.name === r.agent)

        const message: DebateMessage = {
          id: `msg_${round}_${messageIdx++}`,
          agentId: matchingAgent?.id || `unknown_${messageIdx}`,
          agentName: r.agent || 'Agent',
          content: r.message || '',
          timestamp: Date.now(),
          round,
          confidence: 0.7 + Math.random() * 0.25,
          sentiment: sentimentFor(matchingProfile),
        }

        debateController.addMessage(message)

        // === Incremental graph build ===
        // Spawn an agent node the FIRST time this agent speaks
        if (matchingAgent && !spawnedAgentIds.has(matchingAgent.id)) {
          const agentNodeId = `agent-${matchingAgent.id}`
          const agentIndex = spawnedAgentIds.size
          // Place agents on outer ring
          const pos = positionOnRing(agentIndex, agents.length, 220)
          addNode({
            id: agentNodeId,
            label: matchingAgent.name,
            type: 'agent',
            position: pos,
            data: { importance: 0.8, description: matchingAgent.role },
          })
          addEdge({
            id: `edge-agent-${matchingAgent.id}`,
            source: agentNodeId,
            target: 'ctx-root',
            type: 'influences' as const,
          })
          spawnedAgentIds.add(matchingAgent.id)
          // Briefly animate the new node
          setTimeout(() => animateNode(agentNodeId, 1000), 50)
        }

        // Extract a theme from the message and add it to the graph
        const themeKeyword = extractTheme(r.message || '')
        const themeNodeId = `theme-${themeKeyword.toLowerCase()}`
        if (themeKeyword && !themeNodeIds.has(themeNodeId)) {
          const themeIndex = themeNodeIds.size
          const pos = positionOnRing(themeIndex, 8, 110, 400, 280, -Math.PI / 4)
          addNode({
            id: themeNodeId,
            label: themeKeyword,
            type: 'theme',
            position: pos,
            data: { importance: 0.6, description: `Theme raised in round ${round}` },
          })
          addEdge({
            id: `edge-theme-${themeNodeId}`,
            source: 'ctx-root',
            target: themeNodeId,
            type: 'influences' as const,
          })
          themeNodeIds.add(themeNodeId)
          setTimeout(() => animateNode(themeNodeId, 800), 100)
        }

        // Connect the speaking agent to the theme it raised
        if (matchingAgent && themeKeyword) {
          const agentNodeId = `agent-${matchingAgent.id}`
          const edgeId = `edge-${agentNodeId}-${themeNodeId}`
          addEdge({
            id: edgeId,
            source: agentNodeId,
            target: themeNodeId,
            type: 'depends_on' as const,
          })
          animateNode(agentNodeId, 900)
          animateNode(themeNodeId, 900)
        }

        simulationController.updateMetrics({
          agentsActive: spawnedAgentIds.size,
          agreementRate: 40 + (round - 1) * 18 + i * 2,
          confidenceScore: 0.6 + (round - 1) * 0.1 + i * 0.02,
          consensusReached: false,
          debateRounds: round,
          executionTime: Date.now(),
          nodesInGraph: graphState.nodes.length + spawnedAgentIds.size + themeNodeIds.size,
          edgesInGraph: graphState.edges.length,
        })
      }

      if (round < totalRounds) {
        await new Promise(resolve => setTimeout(resolve, 1200))
        debateController.completeRound()
      }
    }

    // Build consensus from backend response
    await new Promise(resolve => setTimeout(resolve, 1500))

    const backendConsensus = chatResponse.consensus
    const confidence = chatResponse.confidence ?? 0.8

    let agreedPosition = ''
    if (typeof backendConsensus === 'string') {
      agreedPosition = backendConsensus
    } else if (backendConsensus?.agreed_position) {
      agreedPosition = backendConsensus.agreed_position
    } else if (backendConsensus?.summary) {
      agreedPosition = backendConsensus.summary
    } else if (responses.length > 0) {
      agreedPosition = responses[responses.length - 1]?.message || `Discussion on "${brief}" complete.`
    } else {
      agreedPosition = `Discussion on "${brief}" complete.`
    }

    const consensus: Consensus = {
      reached: true,
      agreedPosition,
      confidenceLevel: confidence,
      agreementRate: 0.8,
      dissents: [],
      timestamp: Date.now(),
    }

    debateController.setConsensus(consensus)

    // Spawn a "consensus" node connected to every spawned agent
    const consensusNodeId = 'consensus-node'
    addNode({
      id: consensusNodeId,
      label: 'Consensus',
      type: 'theme',
      position: { x: 600, y: 280 },
      data: {
        importance: 1,
        description: agreedPosition.slice(0, 140),
      },
    })
    spawnedAgentIds.forEach(agentId => {
      addEdge({
        id: `edge-consensus-${agentId}`,
        source: `agent-${agentId}`,
        target: consensusNodeId,
        type: 'depends_on' as const,
      })
    })
    setTimeout(() => animateNode(consensusNodeId, 1500), 100)

    // Final metrics update
    simulationController.updateMetrics({
      agentsActive: spawnedAgentIds.size,
      agreementRate: 80,
      confidenceScore: 0.85,
      consensusReached: true,
      debateRounds: totalRounds,
      executionTime: Date.now(),
      nodesInGraph: graphState.nodes.length + 1,
      edgesInGraph: graphState.edges.length,
    })

    simulationController.setStatus('completed')
  }

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node)
  }

  const handleReset = () => {
    setIsInitialized(false)
    debateController.resetDebate()
    simulationController.resetSimulation()
    resetView()
    setSelectedNode(null)
  }

  const status = simulationController.state.status

  return (
    <div className="h-screen w-full bg-[var(--bg)] overflow-hidden flex flex-col">
      {/* Header */}
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
          <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--bg-soft)] border border-[var(--line)]">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                status === 'running'
                  ? 'bg-[var(--brand)] pulse-dot'
                  : status === 'completed'
                    ? 'bg-[var(--accent-green)]'
                    : status === 'error'
                      ? 'bg-[#b3473d]'
                      : 'bg-[var(--muted-soft)]'
              }`}
            />
            <span className="text-[11px] font-mono uppercase tracking-wider text-[var(--muted)]">
              {status}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <a href="/docs" className="btn btn-ghost btn-sm">
            Docs
          </a>
          {isInitialized && (
            <button onClick={handleReset} className="btn btn-primary btn-sm">
              <RotateCcw className="h-3.5 w-3.5" />
              New simulation
            </button>
          )}
        </div>
      </header>

      {/* Error Display (top) */}
      {simulationController.state.status === 'error' && (
        <motion.div
          className="px-6 py-3 bg-[var(--brand-tint)] border-b border-[var(--brand)] flex items-center gap-3"
          initial={{ y: -8, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.2 }}
        >
          <AlertCircle className="h-4 w-4 text-[var(--brand)] flex-shrink-0" />
          <p className="text-sm text-[var(--ink)]">{simulationController.state.error}</p>
        </motion.div>
      )}

      {/* Main Content */}
      <div className="flex-1 overflow-hidden flex">
        {!isInitialized ? (
          <div className="flex-1 flex items-center justify-center p-6 overflow-y-auto bg-[var(--bg-soft)]">
            <ControlPanel
              onInitialize={handleInitialize}
              isLoading={simulationController.state.status === 'initializing'}
            />
          </div>
        ) : (
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1.4fr_minmax(360px,1fr)_320px] gap-3 p-3 min-h-0">
            {/* Left: Graph */}
            <motion.div
              className="flex flex-col gap-2 min-w-0 min-h-0"
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3 }}
            >
              <div className="flex-1 min-h-0">
                <GraphCanvas
                  data={{ nodes: graphState.nodes, edges: graphState.edges }}
                  selectedNodeId={selectedNode?.id ?? null}
                  hoveredNodeId={hoveredNode}
                  animatingNodeIds={graphState.animatingNodes}
                  zoomLevel={graphState.zoomLevel}
                  panPosition={graphState.panPosition}
                  onNodeClick={handleNodeClick}
                  onNodeHover={setHoveredNode}
                  onNodeDrag={(id, pos) => updateNodePosition(id, pos)}
                  onZoomChange={setZoomLevel}
                  onPanChange={(p) => setPanPosition(p.x, p.y)}
                  height="h-full"
                  showLegend={false}
                />
              </div>
              <div className="flex justify-between items-center gap-2 flex-shrink-0">
                <GraphControls
                  zoomLevel={graphState.zoomLevel}
                  onZoomIn={() => setZoomLevel(graphState.zoomLevel * 1.2)}
                  onZoomOut={() => setZoomLevel(graphState.zoomLevel / 1.2)}
                  onReset={resetView}
                  onFilterChange={setFilterMode}
                  activeFilter={filterMode}
                />
                <div className="text-[10px] font-mono text-[var(--muted)] px-2">
                  {graphState.nodes.length} nodes · {graphState.edges.length} edges
                </div>
              </div>
            </motion.div>

            {/* Middle: Debate */}
            <motion.div
              className="flex flex-col gap-2 min-h-0"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: 0.05 }}
            >
              <div className="flex-1 min-h-0">
                <DebatePanel
                  debateState={debateController.state}
                  isLoading={simulationController.state.status === 'running'}
                />
              </div>
              <div className="flex-shrink-0">
                <GraphLegend isOpen={legendOpen} onToggle={() => setLegendOpen(!legendOpen)} />
              </div>
            </motion.div>

            {/* Right: Metrics */}
            <motion.div
              className="flex flex-col gap-3 overflow-y-auto min-h-0"
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3, delay: 0.1 }}
            >
              <MetricsDashboard metrics={simulationController.state.metrics} />

              {selectedNode && (
                <motion.div
                  className="bg-[var(--card)] border border-[var(--line)] rounded-md p-4"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="label-mono mb-2">Selected node</p>
                      <p className="font-display text-base font-medium text-[var(--ink)] truncate">
                        {selectedNode.label}
                      </p>
                      <p className="text-[10px] font-mono uppercase text-[var(--brand)] mt-1">
                        {selectedNode.type}
                      </p>
                    </div>
                    <button
                      onClick={() => setSelectedNode(null)}
                      className="text-[var(--muted)] hover:text-[var(--ink)] text-xs font-mono"
                      aria-label="Deselect"
                    >
                      ×
                    </button>
                  </div>
                  {selectedNode.data?.description && (
                    <p className="text-xs text-[var(--muted)] mt-3 leading-relaxed">
                      {selectedNode.data.description}
                    </p>
                  )}
                  {typeof selectedNode.data?.importance === 'number' && (
                    <div className="mt-3">
                      <p className="text-[10px] font-mono uppercase text-[var(--muted)] mb-1">
                        Importance
                      </p>
                      <div className="h-1 bg-[var(--bg-strong)] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-[var(--brand)]"
                          style={{ width: `${(selectedNode.data.importance ?? 0) * 100}%` }}
                        />
                      </div>
                    </div>
                  )}
                </motion.div>
              )}
            </motion.div>
          </div>
        )}
      </div>
    </div>
  )
}
