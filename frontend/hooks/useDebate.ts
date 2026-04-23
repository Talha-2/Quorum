'use client'

import { useState, useCallback } from 'react'
import { DebateState, DebateMessage, Agent, Consensus, DebateRound } from '@/types/debate'

export function useDebate(agents: Agent[], totalRounds = 3) {
  const [state, setState] = useState<DebateState>({
    agents,
    rounds: [],
    currentRound: 0,
    isActive: false,
    totalRounds,
  })

  const startDebate = useCallback(() => {
    setState(prev => ({
      ...prev,
      isActive: true,
      currentRound: 1,
      rounds: [
        {
          roundNumber: 1,
          messages: [],
          startTime: Date.now(),
          status: 'active',
        },
      ],
    }))
  }, [])

  const addMessage = useCallback((message: DebateMessage) => {
    setState(prev => {
      const updatedRounds = [...prev.rounds]
      const currentRoundIndex = updatedRounds.length - 1

      if (currentRoundIndex >= 0) {
        updatedRounds[currentRoundIndex] = {
          ...updatedRounds[currentRoundIndex],
          messages: [...updatedRounds[currentRoundIndex].messages, message],
        }
      }

      return {
        ...prev,
        rounds: updatedRounds,
      }
    })
  }, [])

  const completeRound = useCallback(() => {
    setState(prev => {
      if (prev.currentRound >= prev.totalRounds) {
        return prev
      }

      const updatedRounds = [...prev.rounds]
      const currentRoundIndex = updatedRounds.length - 1

      if (currentRoundIndex >= 0) {
        updatedRounds[currentRoundIndex] = {
          ...updatedRounds[currentRoundIndex],
          status: 'completed',
          endTime: Date.now(),
        }
      }

      const nextRound = prev.currentRound + 1
      updatedRounds.push({
        roundNumber: nextRound,
        messages: [],
        startTime: Date.now(),
        status: nextRound > prev.totalRounds ? 'completed' : 'pending',
      })

      return {
        ...prev,
        rounds: updatedRounds,
        currentRound: nextRound,
      }
    })
  }, [])

  const setConsensus = useCallback((consensus: Consensus) => {
    setState(prev => ({
      ...prev,
      consensus,
      isActive: false,
    }))
  }, [])

  const getAgentMessages = useCallback((agentId: string): DebateMessage[] => {
    return state.rounds.flatMap(r => r.messages).filter(m => m.agentId === agentId)
  }, [state.rounds])

  const getAgreementRate = useCallback((): number => {
    if (!state.consensus) return 0
    const totalAgents = state.agents.length
    const dissents = state.consensus.dissents?.length || 0
    return ((totalAgents - dissents) / totalAgents) * 100
  }, [state.agents.length, state.consensus])

  const resetDebate = useCallback(() => {
    setState(prev => ({
      ...prev,
      rounds: [],
      currentRound: 0,
      isActive: false,
      consensus: undefined,
    }))
  }, [])

  const setAgents = useCallback((newAgents: Agent[]) => {
    setState(prev => ({
      ...prev,
      agents: newAgents,
    }))
  }, [])

  const setTotalRounds = useCallback((rounds: number) => {
    setState(prev => ({
      ...prev,
      totalRounds: Math.max(1, Math.min(rounds, 20)),
    }))
  }, [])

  return {
    state,
    startDebate,
    addMessage,
    completeRound,
    setConsensus,
    getAgentMessages,
    getAgreementRate,
    resetDebate,
    setAgents,
    setTotalRounds,
  }
}
