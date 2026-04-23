export interface Agent {
  id: string
  name: string
  role: string
  avatar?: string
  personality: {
    optimism: number
    riskTolerance: number
    caution: number
    decisiveness: number
  }
  expertise: string[]
  memory?: {
    previousPositions: string[]
    recentArguments: string[]
  }
}

export interface DebateMessage {
  id: string
  agentId: string
  agentName: string
  content: string
  timestamp: number
  round: number
  sentiment?: 'positive' | 'neutral' | 'negative'
  confidence?: number
  isStreaming?: boolean
}

export interface DebateRound {
  roundNumber: number
  messages: DebateMessage[]
  startTime: number
  endTime?: number
  status: 'active' | 'completed' | 'pending'
}

export interface Consensus {
  reached: boolean
  agreedPosition?: string
  confidenceLevel?: number
  dissents?: Array<{
    agentId: string
    agentName: string
    position: string
  }>
  agreementRate?: number
  timestamp?: number
}

export interface DebateState {
  agents: Agent[]
  rounds: DebateRound[]
  currentRound: number
  consensus?: Consensus
  isActive: boolean
  totalRounds: number
}
