// Types for the 5-stage Quorum pipeline (mirrors backend/pipeline/models.py)

export type ProjectState =
  | 'created'
  | 'ontology_generated'
  | 'graph_building'
  | 'graph_completed'
  | 'env_ready'
  | 'config_ready'
  | 'activation_ready'
  | 'simulating'
  | 'sim_completed'
  | 'report_ready'
  | 'failed'

export interface OntologyEntityType {
  name: string
  description: string
  examples: string[]
  is_individual: boolean
}

export interface OntologyEdgeType {
  name: string
  description: string
  source_targets: string[][]
}

export interface Ontology {
  entity_types: OntologyEntityType[]
  edge_types: OntologyEdgeType[]
}

export interface PipelineGraphNode {
  id: string
  name: string
  type: string
  description: string
  attributes: Record<string, unknown>
  is_individual: boolean
}

export interface PipelineGraphEdge {
  id: string
  source_id: string
  target_id: string
  type: string
  description: string
  strength: number
}

export interface PipelineGraph {
  nodes: PipelineGraphNode[]
  edges: PipelineGraphEdge[]
}

export interface GraphStats {
  entity_nodes: number
  relation_edges: number
  schema_types: number
}

export interface AgentProfile {
  id: string
  user_name: string
  name: string
  role: string
  bio: string
  persona: string
  expertise: string[]
  interested_topics: string[]
  optimism: number
  risk_tolerance: number
  caution: number
  stance: 'support' | 'oppose' | 'neutral'
  bias: string
  // Apparent demographics (rendered in the agent detail modal)
  age?: number | null
  gender?: string | null
  mbti?: string | null
  country?: string | null
  profession?: string | null
  source_entity_id: string | null
  source_entity_type: string | null
  is_individual: boolean
}

// ============================================
// Simulation parameters (Stage 03 — Generate Config)
// ============================================

export interface TimeSimulationConfig {
  total_simulation_hours: number
  minutes_per_round: number
  agents_per_hour_min: number
  agents_per_hour_max: number
  peak_hours: number[]
  peak_activity_multiplier: number
  off_peak_hours: number[]
  off_peak_activity_multiplier: number
  morning_hours: number[]
  morning_activity_multiplier: number
  work_hours: number[]
  work_activity_multiplier: number
}

export interface AgentActivityConfig {
  agent_id: number
  entity_uuid: string
  entity_name: string
  entity_type: string
  activity_level: number
  posts_per_hour: number
  comments_per_hour: number
  active_hours: number[]
  response_delay_min: number
  response_delay_max: number
  sentiment_bias: number
  stance: string
  influence_weight: number
}

export interface InitialPost {
  content: string
  poster_type: string
  poster_agent_id: number | null
}

export interface EventConfig {
  initial_posts: InitialPost[]
  scheduled_events: unknown[]
  hot_topics: string[]
  narrative_direction: string
  generated_at: string
}

export interface PlatformConfig {
  platform: string
  recency_weight: number
  popularity_weight: number
  relevance_weight: number
  viral_threshold: number
  echo_chamber_strength: number
}

export interface SimulationParameters {
  time_config: TimeSimulationConfig
  agent_configs: AgentActivityConfig[]
  event_config: EventConfig | null
  feed_config: PlatformConfig | null
  community_config: PlatformConfig | null
  generation_reasoning: string
  generated_at: string
}

export interface DebateMessage {
  id: string
  agent_id: string
  agent_user_name: string
  agent_name: string
  agent_role: string
  round: number
  content: string
  confidence: number
  stance: 'support' | 'oppose' | 'neutral'
}

export interface Consensus {
  agreed_position: string
  agreement_rate: number
  confidence_level: number
  dissents: { agent_name: string; position: string }[]
}

export interface PipelineEvent {
  timestamp: string
  level: 'info' | 'warn' | 'error' | 'success'
  message: string
  project_id: string
  stage: string
}

export interface UploadedDocumentMeta {
  filename: string
  char_count: number
}

export interface ReportSection {
  title: string
  content: string
}

export interface Report {
  title: string
  summary: string
  sections: ReportSection[]
  markdown: string
  generated_at: string
}

export interface Project {
  id: string
  title: string
  brief: string
  constraints: string
  signals: string
  state: ProjectState
  created_at: string
  updated_at: string
  last_error?: string | null
  ontology: Ontology | null
  graph_stats: GraphStats | null
  agent_count: number
  events: PipelineEvent[]
  graph?: PipelineGraph
  agents?: AgentProfile[]
  simulation_parameters?: SimulationParameters
  activation?: EventConfig
  debate_messages?: DebateMessage[]
  consensus?: Consensus
  report?: Report
  uploaded_documents?: UploadedDocumentMeta[]
  pipeline?: {
    project_id: string
    state: ProjectState
    failed: boolean
    last_error?: string | null
    current_step: string | null
    steps: Array<{
      id: string
      order: number
      label: string
      detail: string
      path?: string
      done: boolean
      optional: boolean
    }>
  }
}
