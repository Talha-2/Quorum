'use client'

import { useState, useCallback } from 'react'
import { SimulationState, SimulationStatus, SimulationConfig, SimulationMetrics, SimulationEvent } from '@/types/simulation'

const defaultMetrics: SimulationMetrics = {
  agentsActive: 0,
  agreementRate: 0,
  confidenceScore: 0,
  consensusReached: false,
  debateRounds: 0,
  executionTime: 0,
  nodesInGraph: 0,
  edgesInGraph: 0,
}

export function useSimulation() {
  const [state, setState] = useState<SimulationState>({
    id: '',
    status: 'idle',
    config: {
      domain: 'generic',
      artifacts: {
        brief: '',
        constraints: [],
        signals: [],
      },
      agents: {
        count: 0,
        complexity: 'medium',
      },
      debate: {
        rounds: 3,
      },
    },
    metrics: defaultMetrics,
    events: [],
  })

  const initializeSimulation = useCallback((config: SimulationConfig) => {
    const simulationId = `sim_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    setState(prev => ({
      ...prev,
      id: simulationId,
      status: 'initializing',
      config,
      startTime: Date.now(),
      events: [
        {
          id: `evt_${Date.now()}`,
          type: 'simulation.initialized',
          timestamp: Date.now(),
          data: { domain: config.domain },
        },
      ],
    }))

    return simulationId
  }, [])

  const setStatus = useCallback((status: SimulationStatus) => {
    setState(prev => ({
      ...prev,
      status,
      error: status === 'error' ? prev.error : undefined,
    }))
  }, [])

  const updateMetrics = useCallback((metrics: Partial<SimulationMetrics>) => {
    setState(prev => ({
      ...prev,
      metrics: { ...prev.metrics, ...metrics },
    }))
  }, [])

  const addEvent = useCallback((event: SimulationEvent) => {
    setState(prev => ({
      ...prev,
      events: [...prev.events, event],
    }))
  }, [])

  const setError = useCallback((error: string) => {
    setState(prev => ({
      ...prev,
      status: 'error',
      error,
    }))
  }, [])

  const completeSimulation = useCallback(() => {
    setState(prev => ({
      ...prev,
      status: 'completed',
      endTime: Date.now(),
      metrics: {
        ...prev.metrics,
        executionTime: prev.startTime ? Date.now() - prev.startTime : 0,
      },
    }))
  }, [])

  const resetSimulation = useCallback(() => {
    setState({
      id: '',
      status: 'idle',
      config: {
        domain: 'generic',
        artifacts: {
          brief: '',
          constraints: [],
          signals: [],
        },
        agents: {
          count: 0,
          complexity: 'medium',
        },
        debate: {
          rounds: 3,
        },
      },
      metrics: defaultMetrics,
      events: [],
    })
  }, [])

  return {
    state,
    initializeSimulation,
    setStatus,
    updateMetrics,
    addEvent,
    setError,
    completeSimulation,
    resetSimulation,
  }
}
