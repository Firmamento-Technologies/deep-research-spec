import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

function withAuthHeaders(headers = {}) {
  const token = localStorage.getItem('access_token');
  if (!token) return headers;
  return { ...headers, Authorization: `Bearer ${token}` };
}

function withConfig(config: any = {}) {
  return {
    ...config,
    headers: withAuthHeaders(config.headers || {}),
  };
}

export const api = {
  get(url: string, config = {}) {
    return client.get(url, withConfig(config));
  },
  post(url: string, data?: unknown, config = {}) {
    return client.post(url, data, withConfig(config));
  },
  delete(url: string, config = {}) {
    return client.delete(url, withConfig(config));
  },
};
