export type NodeType = 'agent' | 'entity' | 'theme' | 'context' | 'blocker'
export type EdgeType = 'depends_on' | 'blocks' | 'influences'

export interface GraphNode {
  id: string
  label: string
  type: NodeType
  data: {
    description?: string
    importance?: number
    active?: boolean
    properties?: Record<string, any>
  }
  position?: { x: number; y: number }
  metadata?: Record<string, any>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  type: EdgeType
  animated?: boolean
  data?: Record<string, any>
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  metadata?: {
    totalNodes: number
    totalEdges: number
    activationLevel?: number
    lastUpdate?: string
  }
}

export interface GraphState {
  nodes: GraphNode[]
  edges: GraphEdge[]
  selectedNode: GraphNode | null
  hoveredNode: string | null
  animatingNodes: Set<string>
  zoomLevel: number
  panPosition: { x: number; y: number }
}
