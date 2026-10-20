import { useQuery } from '@tanstack/react-query';
import { api } from './api';

/** street_id -> name from GET /streets. Falls back to the id until loaded or if the call fails. */
export function useStreetNames(): (id: string) => string {
  const q = useQuery({ queryKey: ['streets', 'BBR'], queryFn: () => api.streets(), staleTime: 300_000, retry: false });
  const names = new Map((q.data?.features ?? []).map((f) => [f.properties.street_id, f.properties.name]));
  return (id) => names.get(id) ?? id;
}
