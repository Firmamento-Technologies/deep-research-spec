const BASE = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`API ${res.status}: ${err}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  // Runs
  createRun: (body: unknown) =>
    request<{ doc_id: string; status: string }>('/api/runs', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  listRuns: () => request<unknown[]>('/api/runs'),
  getRun: (docId: string) => request<unknown>(`/api/runs/${docId}`),
  approveOutline: (docId: string, body: unknown) =>
    request<{ accepted: boolean }>(`/api/runs/${docId}/approve-outline`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  approveSection: (docId: string, body: unknown) =>
    request<{ accepted: boolean }>(`/api/runs/${docId}/approve-section`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  resolveEscalation: (docId: string, body: unknown) =>
    request<{ accepted: boolean }>(`/api/runs/${docId}/resolve-escalation`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  cancelRun: (docId: string) =>
    request<{ cancelled: boolean }>(`/api/runs/${docId}`, { method: 'DELETE' }),
  updateRunConfig: (docId: string, body: unknown) =>
    request<{ updated: boolean }>(`/api/runs/${docId}/config`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  // Companion
  companionChat: (body: unknown) =>
    request<{ reply: string; chips: unknown; action: unknown }>('/api/companion/chat', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  // Analytics
  getAnalytics: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request<unknown>(`/api/analytics${qs}`)
  },

  // Settings
  getSettings: () => request<unknown>('/api/settings'),
  updateSettings: (body: unknown) =>
    request<{ updated: boolean }>('/api/settings', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  // Health
  health: () => request<{ status: string }>('/health'),
}
