// Typed API client — thin fetch wrapper around the FastAPI backend.
// Base URL da VITE_API_BASE_URL (iniettato in Docker) o proxied a
// localhost:8000 via vite.config.ts in dev.
//
// Encoding: Content-Type sempre application/json; charset=utf-8 per
// garantire la corretta trasmissione di caratteri non-ASCII (italiano).

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

const JSON_HEADERS = {
  'Content-Type': 'application/json; charset=utf-8',
  'Accept':       'application/json',
} as const

export interface ApiError extends Error {
  status: number
  body:   string
}

function makeError(method: string, path: string, status: number, body: string): ApiError {
  const err = new Error(`${method} ${path} → ${status}: ${body}`) as ApiError
  err.status = status
  err.body   = body
  return err
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body !== undefined ? JSON_HEADERS : { Accept: 'application/json' },
    body:    body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw makeError(method, path, res.status, text)
  }

  // 204 No Content — ritorna undefined castato a T
  if (res.status === 204) return undefined as T

  return res.json() as Promise<T>
}

export const api = {
  get:    <T>(path: string)                => request<T>('GET',    path),
  post:   <T>(path: string, body: unknown) => request<T>('POST',   path, body),
  put:    <T>(path: string, body: unknown) => request<T>('PUT',    path, body),
  patch:  <T>(path: string, body: unknown) => request<T>('PATCH',  path, body),
  delete: <T>(path: string)               => request<T>('DELETE', path),
}
