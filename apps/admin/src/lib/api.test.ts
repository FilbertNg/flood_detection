import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { auth } from '../auth';
import { api } from './api';

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
    expect(JSON.parse(calls[0][1].body as string)).toEqual({ event: '2024-11-12', speed: 60 });
    expect(calls[1][1].method).toBe('DELETE');
  });
});
