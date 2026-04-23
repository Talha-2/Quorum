export type SimulationStatus = 'idle' | 'initializing' | 'running' | 'debating' | 'completed' | 'error'
export type Domain = 'execution' | 'finance' | 'policy' | 'creative' | 'generic'

export interface Artifact {
  brief: string
  constraints: string[]
  signals: string[]
  stakeholders?: string[]
  context?: string
}

export interface SimulationConfig {
  domain: Domain
  artifacts: Artifact
  agents: {
    count: number
    complexity: 'low' | 'medium' | 'high'
  }
  debate: {
    rounds: number
    timeout?: number
  }
  parameters?: Record<string, any>
}

export interface SimulationMetrics {
  agentsActive: number
  agreementRate: number
  confidenceScore: number
  consensusReached: boolean
  debateRounds: number
  executionTime: number
  nodesInGraph: number
  edgesInGraph: number
}

export interface SimulationEvent {
  id: string
  type: string
  timestamp: number
  data: Record<string, any>
  severity?: 'info' | 'warning' | 'error'
}

export interface SimulationState {
  id: string
  status: SimulationStatus
  config: SimulationConfig
  metrics: SimulationMetrics
  events: SimulationEvent[]
  startTime?: number
  endTime?: number
  error?: string
}
