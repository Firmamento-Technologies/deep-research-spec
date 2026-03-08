import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

export class QueryClient {
  constructor(_config?: unknown) {}
  invalidateQueries(_args?: unknown): void {}
}

const QueryClientContext = createContext<QueryClient | null>(null);

export function QueryClientProvider({ client, children }: { client: QueryClient; children: ReactNode }) {
  return <QueryClientContext.Provider value={client}>{children}</QueryClientContext.Provider>;
}

export function useQueryClient(): QueryClient {
  return useContext(QueryClientContext) ?? new QueryClient();
}

export function useQuery<T>({ queryFn, enabled = true }: { queryKey: unknown[]; queryFn: () => Promise<T>; enabled?: boolean; refetchInterval?: number }) {
  const [data, setData] = useState<T | undefined>(undefined);
  const [isLoading, setLoading] = useState<boolean>(enabled);

  useEffect(() => {
    let mounted = true;
    if (!enabled) {
      setLoading(false);
      return;
    }
    setLoading(true);
    queryFn()
      .then((result) => {
        if (mounted) setData(result);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [enabled, queryFn]);

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
