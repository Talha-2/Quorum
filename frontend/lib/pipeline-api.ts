// Typed client for the Quorum pipeline API.

import { apiClient, APIError } from './api-client'
import type { DomainInfo, Project } from '@/types/pipeline'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'

export const pipelineApi = {
  listDomains() {
    return apiClient.get<{ domains: DomainInfo[] }>('/api/domains')
  },

  createProject(input: {
    title?: string
    brief: string
    constraints?: string
    signals?: string
    domain?: string
  }) {
    return apiClient.post<Project>('/api/projects', input)
  },

  getProject(id: string) {
    return apiClient.get<Project>(`/api/projects/${id}`, { skipCache: true })
  },

  // ============ Stage 0 — file upload (multipart) ============
  //
  // The standard apiClient is JSON-only, so this one bypasses it and goes
  // straight to fetch with FormData. Returns the updated Project.
  async uploadDocument(projectId: string, file: File): Promise<Project> {
    const form = new FormData()
    form.append('file', file)
    const response = await fetch(
      `${API_BASE}/api/projects/${projectId}/upload`,
      {
        method: 'POST',
        body: form,
        // NB: do NOT set Content-Type — fetch will set the multipart boundary
      }
    )
    if (!response.ok) {
      let detail = response.statusText || 'Upload failed'
      try {
        const data = await response.json()
        detail = data.detail ?? detail
      } catch {
        // not JSON, keep statusText
      }
      throw new APIError(response.status, response.statusText, detail)
    }
    return response.json()
  },

  generateOntology(projectId: string) {
    return apiClient.post<Project>(
      `/api/projects/${projectId}/graph/ontology/generate`,
      {}
    )
  },

  buildGraph(projectId: string) {
    return apiClient.post<Project>(`/api/projects/${projectId}/graph/build`, {})
  },

  setupEnv(projectId: string) {
    return apiClient.post<Project>(`/api/projects/${projectId}/env/setup`, {})
  },

  prepareSimulation(projectId: string) {
    return apiClient.post<Project>(`/api/projects/${projectId}/simulation/prepare`, {})
  },

  activateSimulation(projectId: string) {
    return apiClient.post<Project>(`/api/projects/${projectId}/simulation/activate`, {})
  },

  startSimulation(projectId: string, rounds = 3, agentsPerRound = 4) {
    return apiClient.post<Project>(`/api/projects/${projectId}/simulation/start`, {
      rounds,
      agents_per_round: agentsPerRound,
    })
  },

  runNextStage(projectId: string, rounds = 3, agentsPerRound = 4) {
    return apiClient.post<Project>(`/api/projects/${projectId}/pipeline/run-next`, {
      rounds,
      agents_per_round: agentsPerRound,
    })
  },

  generateReport(projectId: string) {
    return apiClient.post<Project>(`/api/projects/${projectId}/report/generate`, {})
  },

  chatWithAgent(projectId: string, agentId: string, message: string) {
    return apiClient.post<{
      agent_id: string
      agent_name: string
      user_message: string
      reply: string
    }>(`/api/projects/${projectId}/agents/${agentId}/chat`, { message })
  },
}
