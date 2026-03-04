import { useEffect, useState } from 'react';

/**
 * Debounce hook - delays updating the value until after specified ms
 * 
 * Usage:
 *   const debouncedQuery = useDebounce(query, 500);
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}
