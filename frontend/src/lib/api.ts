const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || 'http://localhost:8000';

type ApiConfig = {
  headers?: Record<string, string>;
  params?: Record<string, string | number | boolean | undefined>;
  responseType?: 'blob' | 'json';
  onUploadProgress?: (event: { loaded: number; total?: number }) => void;
};

function authHeaders(headers: Record<string, string> = {}) {
  const token = localStorage.getItem('access_token');
  return token ? { ...headers, Authorization: `Bearer ${token}` } : headers;
}

function buildUrl(url: string, params?: ApiConfig['params']) {
  const full = `${API_BASE_URL}${url}`;
  if (!params) return full;
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined) q.set(k, String(v)); });
  return `${full}?${q.toString()}`;
}

async function parseResponse(response: Response, responseType: ApiConfig['responseType']) {
  if (responseType === 'blob') return response.blob();
  const text = await response.text();
  try { return text ? JSON.parse(text) : null; } catch { return text; }
}

export const api = {
  async get(url: string, config: ApiConfig = {}) {
    const response = await fetch(buildUrl(url, config.params), {
      headers: authHeaders(config.headers),
    });
    return { data: await parseResponse(response, config.responseType), status: response.status };
  },
  async post(url: string, data?: unknown, config: ApiConfig = {}) {
    config.onUploadProgress?.({ loaded: 100, total: 100 });
    const isForm = typeof FormData !== 'undefined' && data instanceof FormData;
    const response = await fetch(buildUrl(url, config.params), {
      method: 'POST',
      headers: isForm ? authHeaders(config.headers) : authHeaders({ 'Content-Type': 'application/json', ...(config.headers ?? {}) }),
      body: isForm ? data as BodyInit : data === undefined ? undefined : JSON.stringify(data),
    });
    return { data: await parseResponse(response, config.responseType), status: response.status };
  },
  async delete(url: string, config: ApiConfig = {}) {
    const response = await fetch(buildUrl(url, config.params), {
      method: 'DELETE',
      headers: authHeaders(config.headers),
    });
    return { data: await parseResponse(response, config.responseType), status: response.status };
  },
};
