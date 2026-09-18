export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

export async function api<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(payload.detail || `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

export type Row = Record<string, string | number | null>
export type Metrics = Record<string, number>
