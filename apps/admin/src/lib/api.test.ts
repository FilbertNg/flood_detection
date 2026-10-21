import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { auth } from '../auth';
import { api, apiBase } from './api';

beforeEach(() => auth.logout());
afterEach(() => vi.unstubAllGlobals());

function stub(status: number, body: unknown = {}) {
  const fn = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal('fetch', fn);
  return fn;
}

describe('api', () => {
  it('sends the bearer token', async () => {
    auth.login('abc');
    const fn = stub(200, { mode: 'live' });
    await api.status();
    const init = (fn.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer abc');
  });

  it('logs out on any 401', async () => {
    auth.login('abc');
    stub(401, { detail: 'Invalid token' });
    await expect(api.streets()).rejects.toThrow();
    expect(auth.getToken()).toBeNull();
  });

  it('keeps the session on other errors', async () => {
    auth.login('abc');
    stub(500);
    await expect(api.streets()).rejects.toThrow('500');
    expect(auth.getToken()).toBe('abc');
  });

  it('login posts credentials without logging out on 401 and surfaces the detail', async () => {
    stub(401, { detail: 'Wrong email or password' });
    await expect(api.login('a@b.c', 'x')).rejects.toThrow('Wrong email or password');
  });

  it('start and stop replay use POST and DELETE on /admin/replay', async () => {
    auth.login('abc');
    const fn = stub(200, {});
    await api.startReplay('2024-11-12');
    await api.stopReplay();
    const calls = fn.mock.calls as unknown as [string, RequestInit][];
    expect(calls[0][0]).toMatch(/\/api\/v1\/admin\/replay$/);
    expect(calls[0][1].method).toBe('POST');
    // Starts at 08:30, just before the first alerts (08:45), at 10 s per 15-min step: something happens within ~15 s.
    expect(JSON.parse(calls[0][1].body as string)).toEqual({ event: '2024-11-12', speed: 90, start: '08:30' });
    expect(calls[1][1].method).toBe('DELETE');
  });

  it('admin data endpoints use the contract paths, methods and bodies', async () => {
    auth.login('abc');
    const fn = stub(200, {});
    await api.stats('2024-01-01', '2024-12-31');
    await api.report('2024-11');
    await api.suggestions('2024-01-01', '2024-12-31');
    await api.updateSuggestion('s_01', { status: 'done', note: 'cleared' });
    await api.pendingAnswers();
    await api.reviewAnswer('ans_01', { review_status: 'spam' });
    const c = fn.mock.calls as unknown as [string, RequestInit][];
    expect(c[0][0]).toMatch(/\/admin\/stats\?from=2024-01-01&to=2024-12-31$/);
    expect(c[1][0]).toMatch(/\/admin\/report\?month=2024-11$/);
    expect(c[2][0]).toMatch(/\/admin\/suggestions\?from=2024-01-01&to=2024-12-31$/);
    expect(c[3][0]).toMatch(/\/admin\/suggestions\/s_01$/);
    expect(c[3][1].method).toBe('PATCH');
    expect(JSON.parse(c[3][1].body as string)).toEqual({ status: 'done', note: 'cleared' });
    expect(c[4][0]).toMatch(/\/admin\/answers\?review_status=pending$/);
    expect(c[5][0]).toMatch(/\/admin\/answers\/ans_01$/);
    expect(c[5][1].method).toBe('PATCH');
    expect(JSON.parse(c[5][1].body as string)).toEqual({ review_status: 'spam' });
  });
});

describe('apiBase', () => {
  it('drops trailing slashes so paths never start with //', () => {
    expect(apiBase('https://api.example.ts.net/')).toBe('https://api.example.ts.net');
    expect(apiBase('https://api.example.ts.net//')).toBe('https://api.example.ts.net');
    expect(apiBase('https://api.example.ts.net')).toBe('https://api.example.ts.net');
  });
  it('falls back to the local API', () => {
    expect(apiBase(undefined)).toBe('http://localhost:8000');
  });
});
