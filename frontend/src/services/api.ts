import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

export default api

// Types
export interface Session {
  id: string
  status: 'created' | 'running' | 'completed' | 'failed' | 'cancelled'
  requirement: string
  created_at: string
  updated_at: string
  project_id?: string
  error?: string | null
}

export interface AgentProgress {
  status: 'pending' | 'running' | 'completed' | 'failed'
  started_at?: string
  completed_at?: string
  error?: string
}

export interface Artifact {
  agent_role: string
  type: string
  name: string
  content?: string
  content_preview?: string
  metadata?: Record<string, any>
}

export interface ProjectCommit {
  hash: string
  message: string
  author: string
  time: string
}

export interface ProjectFile {
  name: string
  path: string
  type: 'file' | 'directory'
  size: number
}

export interface Workflow {
  name: string
  description?: string
  steps: string[]
}

export interface Experience {
  id: string
  error_type: string
  error_message: string
  context: Record<string, string>
  solution: string
  success: boolean
  occurrences: number
  status: string
  rating: number
  created_at: string
}

// API functions
export const createSession = async (
  requirement: string,
  project_id?: string
): Promise<{ success: boolean; data: Session }> => {
  const response = await api.post('/sessions', { requirement, project_id })
  return response.data
}

export const listSessions = async (): Promise<{ data: Session[] }> => {
  const response = await api.get('/sessions')
  return response.data
}

export const getSession = async (sessionId: string): Promise<{ data: Session & { agent_progress: Record<string, AgentProgress>; artifacts: Artifact[] } }> => {
  const response = await api.get(`/sessions/${sessionId}`)
  return response.data
}

export const getArtifacts = async (sessionId: string): Promise<{ data: Artifact[] }> => {
  const response = await api.get(`/sessions/${sessionId}/artifacts`)
  return response.data
}

export const cancelSession = async (sessionId: string): Promise<{ success: boolean }> => {
  const response = await api.post(`/sessions/${sessionId}/cancel`)
  return response.data
}

export const listWorkflows = async (): Promise<{ workflows: string[] }> => {
  const response = await api.get('/workflows')
  return response.data
}

export const selectWorkflow = async (
  requirement: string,
  project_id?: string
): Promise<{ analysis: any; workflow: Workflow }> => {
  const response = await api.post('/workflows/select', { requirement, project_id })
  return response.data
}

export const listAgents = async (): Promise<{ roles: string[] }> => {
  const response = await api.get('/agents')
  return response.data
}

// Project / Git
export const createProject = async (
  project_id: string,
  name: string
): Promise<{ data: { id: string; name: string; path: string } }> => {
  const response = await api.post('/projects', { project_id, name })
  return response.data
}

export const listProjects = async (): Promise<{ data: any[] }> => {
  const response = await api.get('/projects')
  return response.data
}

export const getProjectCommits = async (
  project_id: string,
  limit = 20
): Promise<{ data: ProjectCommit[]; count: number }> => {
  const response = await api.get(`/projects/${project_id}/commits`, { params: { limit } })
  return response.data
}

export const listProjectFiles = async (
  project_id: string,
  directory = ''
): Promise<{ data: ProjectFile[]; count: number }> => {
  const response = await api.get(`/projects/${project_id}/files`, { params: { directory } })
  return response.data
}

export const readProjectFile = async (
  project_id: string,
  path: string
): Promise<{ data: { path: string; content: string } }> => {
  const response = await api.get(`/projects/${project_id}/files/${path}`)
  return response.data
}

export const rollbackProject = async (
  project_id: string,
  commit_hash: string
): Promise<{ success: boolean }> => {
  const response = await api.post(`/projects/${project_id}/rollback`, { commit_hash })
  return response.data
}

// Experience
export const listExperiences = async (
  error_message?: string,
  top_k = 5
): Promise<{ data: Experience[]; count: number }> => {
  const response = await api.get('/experiences', { params: { error_message, top_k } })
  return response.data
}

export const createExperience = async (data: {
  error_message: string
  error_type: string
  context: Record<string, string>
  solution: string
  success?: boolean
}): Promise<{ success: boolean; exp_id: string }> => {
  const response = await api.post('/experiences', data)
  return response.data
}

export const rateExperience = async (
  exp_id: string,
  rating: number
): Promise<{ success: boolean }> => {
  const response = await api.post(`/experiences/${exp_id}/rate`, { rating })
  return response.data
}

export const healthCheck = async (): Promise<{ status: string }> => {
  const response = await api.get('/health')
  return response.data
}

// SSE event stream
export const streamSessionEvents = (sessionId: string): EventSource => {
  return new EventSource(`/api/sessions/${sessionId}/stream`)
}
