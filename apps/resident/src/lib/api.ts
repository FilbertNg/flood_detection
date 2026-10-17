import type { AlertSummary, PushPublicKey, Station, Status, StreetCollection, StreetDetail, SubscriptionRequest } from '@floodready/shared';

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}/api/v1${path}`);
  if (!response.ok) throw new Error(`${response.status} ${path}`);
  return (await response.json()) as T;
}

async function send(method: 'POST' | 'DELETE', path: string, body?: unknown): Promise<void> {
  const response = await fetch(`${API_URL}/api/v1${path}`, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${response.status} ${path}`);
}

export const api = {
  status: () => get<Status>('/status'),
  streets: (township = 'BBR') => get<StreetCollection>(`/streets?township=${township}`),
  street: (id: string) => get<StreetDetail>(`/streets/${encodeURIComponent(id)}`),
  stations: (township = 'BBR') => get<Station[]>(`/stations?township=${township}`),
  pushPublicKey: () => get<PushPublicKey>('/push/public-key'),
  subscribe: (request: SubscriptionRequest) => send('POST', '/subscriptions', request),
  unsubscribe: (deviceId: string) => send('DELETE', `/subscriptions/${encodeURIComponent(deviceId)}`),
  alerts: (streetId: string) => get<AlertSummary[]>(`/alerts?street_id=${encodeURIComponent(streetId)}`),
};
