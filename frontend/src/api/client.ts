import axios, { AxiosError } from 'axios'

const api = axios.create({ baseURL: '/' })

export function extractErrorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (error.response?.status) return `Request failed (${error.response.status})`
  }
  if (error instanceof Error) return error.message
  return 'An unexpected error occurred'
}

export interface Settings {
  model: string
  source_language: string
  target_language: string
  api_key_set: boolean
}

export interface JobInfo {
  job_id: string
  filename: string
  state: 'queued' | 'processing' | 'awaiting_review' | 'done' | 'failed'
  progress: number
  stage: string
  created_at: string
  download_token: string | null
  workflow_mode?: string
  workflow_options?: Record<string, unknown>
  queue_position?: number | null
  error?: string | null
}

export interface GlossaryTerm {
  source: string
  target: string
}

export interface LanguageOption {
  code: string
  label: string
}

export const apiClient = {
  getSettings: () => api.get<Settings>('/api/settings').then(r => r.data),
  updateSettings: (data: Partial<Settings> & { openai_api_key?: string }) =>
    api.put<Settings>('/api/settings', data).then(r => r.data),

  getLanguages: () => api.get<{ languages: LanguageOption[] }>('/api/languages').then(r => r.data.languages),

  uploadFile: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<{ upload_id: string; filename: string }>('/api/upload', form).then(r => r.data)
  },

  createJob: (data: {
    upload_id: string
    source_language: string
    target_language: string
    custom_instructions?: string
    workflow_mode?: 'classic' | 'glossary_review'
    workflow_options?: Record<string, unknown>
  }) =>
    api.post<{ job_id: string }>('/api/jobs', data).then(r => r.data),

  listJobs: () => api.get<JobInfo[]>('/api/jobs').then(r => r.data),
  getJob: (jobId: string) => api.get<JobInfo>(`/api/jobs/${jobId}`).then(r => r.data),
  getJobGlossary: (jobId: string) =>
    api.get<{ terms: GlossaryTerm[]; has_edits: boolean }>(`/api/jobs/${jobId}/glossary`).then(r => r.data),
  updateJobGlossary: (jobId: string, terms: GlossaryTerm[]) =>
    api.put<{ ok: boolean; count: number }>(`/api/jobs/${jobId}/glossary`, { terms }).then(r => r.data),
  continueJob: (jobId: string) => api.post<{ ok: boolean }>(`/api/jobs/${jobId}/continue`).then(r => r.data),
  retryJob: (jobId: string) => api.post<{ ok: boolean }>(`/api/jobs/${jobId}/retry`).then(r => r.data),
  deleteJob: (jobId: string) => api.delete<{ ok: boolean }>(`/api/jobs/${jobId}`).then(r => r.data),
}
