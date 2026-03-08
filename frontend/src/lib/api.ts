import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

function withAuthHeaders(headers: Record<string, string> = {}) {
  const token = localStorage.getItem('access_token');
  if (!token) return headers;
  return { ...headers, Authorization: `Bearer ${token}` };
}

export const api = {
  get: (url: string, config: Record<string, unknown> = {}) =>
    client.get(url, { ...(config as object), headers: withAuthHeaders((config.headers as Record<string, string>) || {}) }),
  post: (url: string, data?: unknown, config: Record<string, unknown> = {}) =>
    client.post(url, data as object, { ...(config as object), headers: withAuthHeaders((config.headers as Record<string, string>) || {}) }),
  delete: (url: string, config: Record<string, unknown> = {}) =>
    client.delete(url, { ...(config as object), headers: withAuthHeaders((config.headers as Record<string, string>) || {}) }),
};
