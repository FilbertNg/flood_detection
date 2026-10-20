import type {
  AlertSummary,
  Answer,
  AnswerReview,
  Report,
  Stats,
  Suggestion,
  SuggestionUpdate,
  LoginResponse,
  SeriesPoint,
  Station,
  Status,
  StreetCollection,
  StreetDetail,
} from '@floodready/shared';
import { auth } from '../auth';

/** The API origin without a trailing slash (a `VITE_API_URL` ending in `/` made every path `//api/v1/...` → 404). */
export function apiBase(raw: string | undefined): string {
  return (raw ?? 'http://localhost:8000').replace(/\/+$/, '');
}

export const API_URL: string = apiBase(import.meta.env.VITE_API_URL);

/** The one event with a verified replay (12 Nov 2024 flash flood). */
export const REPLAY_EVENT = '2024-11-12';

async function detailOf(response: Response, path: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === 'string') return body.detail;
  } catch {
    // not JSON
  }
  return `${response.status} ${path}`;
}

async function request<T>(path: string, init: RequestInit = {}, opts: { login?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string> | undefined) };
  const token = auth.getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_URL}/api/v1${path}`, { ...init, headers });
  if (!response.ok) {
    // Any 401 outside the login call means the session is gone: the App then shows the login page.
    if (response.status === 401 && !opts.login) auth.logout();
    throw new Error(response.status === 401 || response.status === 422 ? await detailOf(response, path) : `${response.status} ${path}`);
  }
  return (await response.json()) as T;
}

const json = (body: unknown, method: string): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const api = {
  login: (email: string, password: string) =>
    request<LoginResponse>('/admin/login', json({ email, password }, 'POST'), { login: true }),
  status: () => request<Status>('/status'),
  streets: (township = 'BBR') => request<StreetCollection>(`/streets?township=${township}`),
  street: (id: string) => request<StreetDetail>(`/streets/${encodeURIComponent(id)}`),
  alerts: () => request<AlertSummary[]>('/alerts'),
  stations: (township = 'BBR') => request<Station[]>(`/stations?township=${township}`),
  series: (graphId: string, from?: string, to?: string) => {
    const q = new URLSearchParams();
    if (from) q.set('from', from);
    if (to) q.set('to', to);
    const qs = q.toString();
    return request<SeriesPoint[]>(`/stations/${encodeURIComponent(graphId)}/series${qs ? `?${qs}` : ''}`);
  },
  startReplay: (event: string = REPLAY_EVENT, speed = 60) =>
    request<Status>('/admin/replay', json({ event, speed }, 'POST')),
  stats: (from: string, to: string) => request<Stats>(`/admin/stats?${new URLSearchParams({ from, to })}`),
  report: (month: string) => request<Report>(`/admin/report?${new URLSearchParams({ month })}`),
  suggestions: (from: string, to: string) => request<Suggestion[]>(`/admin/suggestions?${new URLSearchParams({ from, to })}`),
  updateSuggestion: (id: string, body: SuggestionUpdate) =>
    request<Suggestion>(`/admin/suggestions/${encodeURIComponent(id)}`, json(body, 'PATCH')),
  pendingAnswers: () => request<Answer[]>('/admin/answers?review_status=pending'),
  reviewAnswer: (id: string, body: AnswerReview) =>
    request<Answer>(`/admin/answers/${encodeURIComponent(id)}`, json(body, 'PATCH')),
  stopReplay: () => request<Status>('/admin/replay', { method: 'DELETE' }),
};
