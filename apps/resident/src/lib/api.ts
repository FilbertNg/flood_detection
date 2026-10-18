import type { AlertSummary, AnswerCreated, AnswerForm, PushPublicKey, Station, Status, StreetCollection, StreetDetail, SubscriptionRequest } from '@floodready/shared';

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

/** Thrown by postAnswer for any non-2xx reply; 409 means this device already answered this alert. */
export class AnswerError extends Error {
  constructor(readonly status: number) {
    super(`answer failed: ${status}`);
  }
}

/** POST /answers is multipart (photo); the browser sets the boundary, so no Content-Type header. */
export async function postAnswer(form: AnswerForm): Promise<AnswerCreated> {
  const body = new FormData();
  body.set('device_id', form.device_id);
  body.set('street_id', form.street_id);
  body.set('answer', form.answer);
  if (form.alert_id) body.set('alert_id', form.alert_id);
  if (form.depth) body.set('depth', form.depth);
  if (form.lat !== undefined && form.lon !== undefined) {
    body.set('lat', String(form.lat));
    body.set('lon', String(form.lon));
  }
  if (form.photo) body.set('photo', form.photo);
  const response = await fetch(`${API_URL}/api/v1/answers`, { method: 'POST', body });
  if (!response.ok) throw new AnswerError(response.status);
  return (await response.json()) as AnswerCreated;
}
