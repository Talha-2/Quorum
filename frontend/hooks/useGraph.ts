'use client'

import { useState, useCallback, useRef } from 'react'
import { GraphState, GraphNode, GraphEdge, GraphData } from '@/types/graph'

export function useGraph(initialData?: GraphData) {
  const [state, setState] = useState<GraphState>({
    nodes: initialData?.nodes || [],
    edges: initialData?.edges || [],
    selectedNode: null,
    hoveredNode: null,
    animatingNodes: new Set(),
    zoomLevel: 1,
    panPosition: { x: 0, y: 0 },
  })

  const animationTimeouts = useRef<Map<string, NodeJS.Timeout>>(new Map())

  const updateGraphData = useCallback((data: GraphData) => {
    setState(prev => ({
      ...prev,
      nodes: data.nodes,
      edges: data.edges,
    }))
  }, [])

  const addNode = useCallback((node: GraphNode) => {
    setState(prev => ({
      ...prev,
      nodes: [...prev.nodes, node],
    }))
  }, [])

  const addEdge = useCallback((edge: GraphEdge) => {
    setState(prev => ({
      ...prev,
      edges: [...prev.edges, edge],
    }))
  }, [])

  const removeNode = useCallback((nodeId: string) => {
    setState(prev => ({
      ...prev,
      nodes: prev.nodes.filter(n => n.id !== nodeId),
      edges: prev.edges.filter(e => e.source !== nodeId && e.target !== nodeId),
    }))
  }, [])

  const selectNode = useCallback((node: GraphNode | null) => {
    setState(prev => ({
      ...prev,
      selectedNode: node,
    }))
  }, [])

  const hoverNode = useCallback((nodeId: string | null) => {
    setState(prev => ({
      ...prev,
      hoveredNode: nodeId,
    }))
  }, [])

  const animateNode = useCallback((nodeId: string, duration = 600) => {
    setState(prev => {
      const next = new Set(prev.animatingNodes)
      next.add(nodeId)
      return { ...prev, animatingNodes: next }
    })

    const timeout = setTimeout(() => {
      setState(prev => {
        const next = new Set(prev.animatingNodes)
        next.delete(nodeId)
        return { ...prev, animatingNodes: next }
      })
    }, duration)

    animationTimeouts.current.set(nodeId, timeout)
  }, [])

  const clearAnimations = useCallback(() => {
    animationTimeouts.current.forEach(timeout => clearTimeout(timeout))
    animationTimeouts.current.clear()
    setState(prev => ({
      ...prev,
      animatingNodes: new Set(),
    }))
  }, [])

  const setZoomLevel = useCallback((zoom: number) => {
    setState(prev => ({
      ...prev,
      zoomLevel: Math.max(0.5, Math.min(zoom, 3)),
    }))
  }, [])

  const setPanPosition = useCallback((x: number, y: number) => {
    setState(prev => ({
      ...prev,
      panPosition: { x, y },
    }))
  }, [])

  const resetView = useCallback(() => {
    setState(prev => ({
      ...prev,
      zoomLevel: 1,
      panPosition: { x: 0, y: 0 },
    }))
  }, [])

  const updateNodePosition = useCallback((nodeId: string, position: { x: number; y: number }) => {
    setState(prev => ({
      ...prev,
      nodes: prev.nodes.map(n =>
        n.id === nodeId ? { ...n, position } : n
      ),
    }))
  }, [])

  return {
    state,
    updateGraphData,
    addNode,
    addEdge,
    removeNode,
    selectNode,
    hoverNode,
    animateNode,
    clearAnimations,
    setZoomLevel,
    setPanPosition,
    resetView,
    updateNodePosition,
  }
}
