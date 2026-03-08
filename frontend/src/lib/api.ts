const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || 'http://localhost:8000';

type ApiConfig = {
  headers?: Record<string, string>;
  params?: Record<string, string | number | boolean | undefined>;
  responseType?: 'blob' | 'json';
  onUploadProgress?: (event: { loaded: number; total?: number }) => void;
};

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(status: number, message: string, payload: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

function authHeaders(headers: Record<string, string> = {}) {
  const token = localStorage.getItem('access_token');
  return token ? { ...headers, Authorization: `Bearer ${token}` } : headers;
}

function buildUrl(url: string, params?: ApiConfig['params']) {
  const full = `${API_BASE_URL}${url}`;
  if (!params) return full;
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined) q.set(k, String(v));
  });
  return `${full}?${q.toString()}`;
}

async function parseResponse(response: Response, responseType: ApiConfig['responseType']) {
  if (responseType === 'blob') return response.blob();
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return text;
  }
}

function toErrorMessage(status: number, payload: unknown): string {
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === 'string') return detail;
  }
  return `Request failed with status ${status}`;
}

async function request(method: 'GET' | 'POST' | 'DELETE', url: string, data?: unknown, config: ApiConfig = {}) {
  config.onUploadProgress?.({ loaded: 100, total: 100 });
  const isForm = typeof FormData !== 'undefined' && data instanceof FormData;

  const response = await fetch(buildUrl(url, config.params), {
    method,
    headers:
      method === 'POST' && !isForm
        ? authHeaders({ 'Content-Type': 'application/json', ...(config.headers ?? {}) })
        : authHeaders(config.headers),
    body:
      method === 'POST'
        ? isForm
          ? (data as BodyInit)
          : data === undefined
            ? undefined
            : JSON.stringify(data)
        : undefined,
  });

  const payload = await parseResponse(response, config.responseType);
  if (!response.ok) {
    throw new ApiError(response.status, toErrorMessage(response.status, payload), payload);
  }

  return { data: payload, status: response.status };
}

export const api = {
  get(url: string, config: ApiConfig = {}) {
    return request('GET', url, undefined, config);
  },
  post(url: string, data?: unknown, config: ApiConfig = {}) {
    return request('POST', url, data, config);
  },
  delete(url: string, config: ApiConfig = {}) {
    return request('DELETE', url, undefined, config);
  },
};
