import type { AlertSummary, Station, Status, StreetCollection, StreetDetail } from '@floodready/shared';

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}/api/v1${path}`);
  if (!response.ok) throw new Error(`${response.status} ${path}`);
  return (await response.json()) as T;
}

export const api = {
  status: () => get<Status>('/status'),
  streets: (township = 'BBR') => get<StreetCollection>(`/streets?township=${township}`),
  street: (id: string) => get<StreetDetail>(`/streets/${encodeURIComponent(id)}`),
  stations: (township = 'BBR') => get<Station[]>(`/stations?township=${township}`),
  alerts: (streetId: string) => get<AlertSummary[]>(`/alerts?street_id=${encodeURIComponent(streetId)}`),
};
