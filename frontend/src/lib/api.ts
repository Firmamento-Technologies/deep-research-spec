const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '';
const DEFAULT_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS || 30000);

type ApiConfig = {
  headers?: Record<string, string>;
  params?: Record<string, string | number | boolean | undefined>;
  responseType?: 'blob' | 'json';
  timeoutMs?: number;
  signal?: AbortSignal;
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

function mergeSignals(timeoutSignal: AbortSignal, externalSignal?: AbortSignal): AbortSignal {
  if (!externalSignal) return timeoutSignal;
  if (typeof AbortSignal.any === 'function') {
    return AbortSignal.any([timeoutSignal, externalSignal]);
  }

  const controller = new AbortController();
  const abort = () => controller.abort();
  timeoutSignal.addEventListener('abort', abort, { once: true });
  externalSignal.addEventListener('abort', abort, { once: true });
  return controller.signal;
}

async function request(method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE', url: string, data?: unknown, config: ApiConfig = {}) {
  if (config.onUploadProgress && typeof FormData !== 'undefined' && data instanceof FormData) {
    config.onUploadProgress({ loaded: 0 });
  }

  const isForm = typeof FormData !== 'undefined' && data instanceof FormData;
  const timeoutMs = config.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const timeoutSignal = AbortSignal.timeout(timeoutMs);
  const signal = mergeSignals(timeoutSignal, config.signal);

  let response: Response;
  try {
    response = await fetch(buildUrl(url, config.params), {
      method,
      signal,
      headers:
        (method === 'POST' || method === 'PUT' || method === 'PATCH') && !isForm
          ? authHeaders({ 'Content-Type': 'application/json', ...(config.headers ?? {}) })
          : authHeaders(config.headers),
      body:
        (method === 'POST' || method === 'PUT' || method === 'PATCH')
          ? isForm
            ? (data as BodyInit)
            : data === undefined
              ? undefined
              : JSON.stringify(data)
          : undefined,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError(408, `Request timeout after ${timeoutMs}ms`, null);
    }
    throw new ApiError(0, 'Network request failed', err);
  }

  const payload = await parseResponse(response, config.responseType);
  if (!response.ok) {
    throw new ApiError(response.status, toErrorMessage(response.status, payload), payload);
  }

  if (config.onUploadProgress && typeof FormData !== 'undefined' && data instanceof FormData) {
    config.onUploadProgress({ loaded: 100, total: 100 });
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
  put(url: string, data?: unknown, config: ApiConfig = {}) {
    return request('PUT', url, data, config);
  },
  patch(url: string, data?: unknown, config: ApiConfig = {}) {
    return request('PATCH', url, data, config);
  },
  delete(url: string, config: ApiConfig = {}) {
    return request('DELETE', url, undefined, config);
  },
};
