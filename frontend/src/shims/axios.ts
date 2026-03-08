export interface AxiosResponse<T = unknown> {
  data: T;
  status: number;
}

export interface InternalAxiosRequestConfig {
  headers: Record<string, string>;
}

export interface AxiosError extends Error {
  response?: { status?: number; data?: unknown };
  config?: Record<string, unknown>;
}

type RequestConfig = {
  params?: Record<string, string | number | boolean>;
  headers?: Record<string, string>;
  responseType?: 'json' | 'blob';
  onUploadProgress?: (event: { loaded: number; total?: number }) => void;
};

function buildUrl(baseURL: string, url: string, params?: RequestConfig['params']) {
  const full = `${baseURL ?? ''}${url}`;
  if (!params) return full;
  const usp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => usp.set(k, String(v)));
  return `${full}?${usp.toString()}`;
}

function create(config: { baseURL?: string; headers?: Record<string, string> }) {
  const baseURL = config.baseURL ?? '';
  const defaultHeaders = config.headers ?? {};

  return {
    interceptors: {
      request: { use: () => {} },
      response: { use: () => {} },
    },
    async get(url: string, cfg: RequestConfig = {}) {
      const response = await fetch(buildUrl(baseURL, url, cfg.params), {
        headers: { ...defaultHeaders, ...(cfg.headers ?? {}) },
      });
      const data = cfg.responseType === 'blob' ? await response.blob() : await response.json();
      return { data, status: response.status } as AxiosResponse;
    },
    async post(url: string, body?: BodyInit | object, cfg: RequestConfig = {}) {
      cfg.onUploadProgress?.({ loaded: 100, total: 100 });
      const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
      const response = await fetch(buildUrl(baseURL, url, cfg.params), {
        method: 'POST',
        headers: isForm ? cfg.headers : { ...defaultHeaders, ...(cfg.headers ?? {}) },
        body: isForm || body === undefined ? (body as BodyInit | null | undefined) : JSON.stringify(body),
      });
      const data = await response.json();
      return { data, status: response.status } as AxiosResponse;
    },
    async delete(url: string, cfg: RequestConfig = {}) {
      const response = await fetch(buildUrl(baseURL, url, cfg.params), {
        method: 'DELETE',
        headers: { ...defaultHeaders, ...(cfg.headers ?? {}) },
      });
      return { data: undefined, status: response.status } as AxiosResponse;
    },
  };
}

const axios = { create, post: async (url: string, body?: object) => create({}).post(url, body) };
export default axios;
