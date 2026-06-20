import type { Course, CourseCreate, CourseState, PreflightResult } from '../types'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
    ...options
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(JSON.stringify(body.detail ?? body))
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<Record<string, unknown>>('/api/health'),
  preflight: (prepareRepository = false) => request<PreflightResult>(`/api/devin/preflight?prepare_repository=${prepareRepository}`),
  createCourse: (payload: CourseCreate) => request<Course>('/api/courses', { method: 'POST', body: JSON.stringify(payload) }),
  listCourses: () => request<Course[]>('/api/courses'),
  getCourse: (id: string) => request<CourseState>(`/api/courses/${id}`),
  generatePlan: (id: string) => request('/api/courses/' + id + '/plan', { method: 'POST' }),
  approve: (id: string, chapters: Array<{ id: string; title: string; duration_minutes: number }>) =>
    request(`/api/courses/${id}/approve`, { method: 'POST', body: JSON.stringify({ chapters }) }),
  launchPhase: (id: string, phase: string) => request(`/api/courses/${id}/devin/launch`, { method: 'POST', body: JSON.stringify({ phase }) }),
  evidence: (id: string) => request<CourseState>(`/api/courses/${id}/evidence`),
  reporting: (id: string) => request<Record<string, unknown>>(`/api/courses/${id}/reporting`)
}
