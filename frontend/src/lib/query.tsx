import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

type QueryKey = unknown[];

function toKeyString(queryKey: QueryKey): string {
  return JSON.stringify(queryKey);
}

export class QueryClient {
  private cache = new Map<string, { data: unknown; updatedAt: number; key: QueryKey }>();
  private subscribers = new Map<string, Set<() => void>>();

  constructor(_config?: unknown) {}

  getQueryData<T>(queryKey: QueryKey): T | undefined {
    return this.cache.get(toKeyString(queryKey))?.data as T | undefined;
  }

  setQueryData<T>(queryKey: QueryKey, data: T): void {
    const key = toKeyString(queryKey);
    this.cache.set(key, { data, updatedAt: Date.now(), key: queryKey });
    this.notifyKey(key);
  }

  getQueryUpdatedAt(queryKey: QueryKey): number | undefined {
    return this.cache.get(toKeyString(queryKey))?.updatedAt;
  }

  subscribe(queryKey: QueryKey, cb: () => void): () => void {
    const key = toKeyString(queryKey);
    const set = this.subscribers.get(key) ?? new Set<() => void>();
    set.add(cb);
    this.subscribers.set(key, set);
    return () => {
      const current = this.subscribers.get(key);
      current?.delete(cb);
      if (!current || current.size === 0) this.subscribers.delete(key);
    };
  }

  invalidateQueries(args?: { queryKey?: QueryKey }): void {
    const target = args?.queryKey;
    for (const [key, entry] of this.cache.entries()) {
      const matches = !target || (target.length <= entry.key.length && target.every((v, i) => entry.key[i] === v));
      if (matches) {
        this.cache.delete(key);
        this.notifyKey(key);
      }
    }
  }

  private notifyKey(key: string): void {
    const callbacks = this.subscribers.get(key);
    callbacks?.forEach((cb) => cb());
  }
}

const QueryClientContext = createContext<QueryClient | null>(null);

export function QueryClientProvider({
  client,
  children,
}: {
  client: QueryClient;
  children: ReactNode;
}) {
  return <QueryClientContext.Provider value={client}>{children}</QueryClientContext.Provider>;
}

export function useQueryClient(): QueryClient {
  return useContext(QueryClientContext) ?? new QueryClient();
}

type UseQueryOptions<T> = {
  queryKey: QueryKey;
  queryFn: () => Promise<T>;
  enabled?: boolean;
  retry?: number;
  staleTime?: number;
  refetchInterval?: number | false | ((data: T | undefined) => number | false);
};

export function useQuery<T>({
  queryKey,
  queryFn,
  enabled = true,
  retry = 0,
  staleTime = 0,
  refetchInterval = false,
}: UseQueryOptions<T>) {
  const queryClient = useQueryClient();
  const [data, setData] = useState<T | undefined>(() => queryClient.getQueryData<T>(queryKey));
  const [error, setError] = useState<unknown>(null);
  const [isLoading, setLoading] = useState<boolean>(enabled && data === undefined);
  const timerRef = useRef<number | null>(null);

  const run = useCallback(async () => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    const cached = queryClient.getQueryData<T>(queryKey);
    const updatedAt = queryClient.getQueryUpdatedAt(queryKey) ?? 0;
    if (cached !== undefined && Date.now() - updatedAt <= staleTime) {
      setData(cached);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    let attempt = 0;
    while (true) {
      try {
        const result = await queryFn();
        queryClient.setQueryData(queryKey, result);
        setData(result);
        return;
      } catch (err) {
        attempt += 1;
        if (attempt > retry) {
          setError(err);
          return;
        }
      } finally {
        setLoading(false);
      }
    }
  }, [enabled, queryClient, queryKey, queryFn, retry, staleTime]);

  useEffect(() => {
    const clearTimer = () => {
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };

    const unsub = queryClient.subscribe(queryKey, () => {
      const fresh = queryClient.getQueryData<T>(queryKey);
      setData(fresh);
      if (fresh === undefined && enabled) {
        void run();
      }
    });

    const scheduleRefetch = (nextData: T | undefined) => {
      const interval = typeof refetchInterval === 'function' ? refetchInterval(nextData) : refetchInterval;
      if (!interval || interval <= 0) return;
      clearTimer();
      timerRef.current = window.setTimeout(async () => {
        await run();
        scheduleRefetch(queryClient.getQueryData<T>(queryKey));
      }, interval);
    };

    void run().then(() => scheduleRefetch(queryClient.getQueryData<T>(queryKey)));

    return () => {
      clearTimer();
      unsub();
    };
  }, [enabled, queryClient, queryKey, refetchInterval, run]);

  return {
    data,
    error,
    isError: Boolean(error),
    isLoading,
    refetch: run,
  };
}

export function useMutation<TData = unknown, TVars = unknown>({
  mutationFn,
  onSuccess,
  onError,
  onSettled,
}: {
  mutationFn: (vars: TVars) => Promise<TData>;
  onSuccess?: (data: TData) => void;
  onError?: (err: unknown) => void;
  onSettled?: () => void;
}) {
  const [isPending, setPending] = useState(false);

  const mutateAsync = useCallback(async (vars: TVars) => {
    setPending(true);
    try {
      const data = await mutationFn(vars);
      onSuccess?.(data);
      return data;
    } catch (err) {
      onError?.(err);
      throw err;
    } finally {
      onSettled?.();
      setPending(false);
    }
  }, [mutationFn, onSuccess, onError, onSettled]);

  const mutate = useCallback((vars: TVars) => {
    void mutateAsync(vars);
  }, [mutateAsync]);

  return useMemo(() => ({ mutate, mutateAsync, isPending }), [mutate, mutateAsync, isPending]);
}
