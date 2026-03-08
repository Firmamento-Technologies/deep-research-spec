import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

export class QueryClient {
  constructor(_config?: unknown) {}

  invalidateQueries(_args?: unknown): void {
    // no-op lightweight implementation
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
  queryKey: unknown[];
  queryFn: () => Promise<T>;
  enabled?: boolean;
  refetchInterval?: number | false | ((data: T | undefined) => number | false);
};

export function useQuery<T>({ queryFn, enabled = true, refetchInterval = false }: UseQueryOptions<T>) {
  const [data, setData] = useState<T | undefined>(undefined);
  const [isLoading, setLoading] = useState<boolean>(enabled);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    let mounted = true;

    const clearTimer = () => {
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };

    const scheduleRefetch = (nextData: T | undefined) => {
      const interval = typeof refetchInterval === 'function' ? refetchInterval(nextData) : refetchInterval;
      if (!interval || interval <= 0) return;
      clearTimer();
      timerRef.current = window.setTimeout(run, interval);
    };

    const run = async () => {
      if (!enabled) {
        if (mounted) setLoading(false);
        return;
      }
      if (mounted) setLoading(true);
      try {
        const result = await queryFn();
        if (mounted) setData(result);
        scheduleRefetch(result);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    void run();

    return () => {
      mounted = false;
      clearTimer();
    };
  }, [enabled, queryFn, refetchInterval]);

  return { data, isLoading };
}

export function useMutation<TData = unknown, TVars = unknown>({
  mutationFn,
  onSuccess,
}: {
  mutationFn: (vars: TVars) => Promise<TData>;
  onSuccess?: (data: TData) => void;
}) {
  const [isPending, setPending] = useState(false);

  const mutate = (vars: TVars) => {
    setPending(true);
    mutationFn(vars)
      .then((data) => onSuccess?.(data))
      .finally(() => setPending(false));
  };

  return useMemo(() => ({ mutate, isPending }), [isPending]);
}
