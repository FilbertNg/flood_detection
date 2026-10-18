import { beforeEach, describe, expect, it, vi } from 'vitest';
import { auth } from './auth';

beforeEach(() => {
  auth.logout();
  sessionStorage.clear();
});

describe('auth', () => {
  it('keeps the token in memory and sessionStorage after login', () => {
    auth.login('tok-1');
    expect(auth.getToken()).toBe('tok-1');
    expect(sessionStorage.getItem('floodready.admin.token')).toBe('tok-1');
  });

  it('restores a token from sessionStorage', () => {
    sessionStorage.setItem('floodready.admin.token', 'tok-2');
    auth.restore();
    expect(auth.getToken()).toBe('tok-2');
  });

  it('logout clears both and notifies subscribers', () => {
    auth.login('tok-3');
    const listener = vi.fn();
    const off = auth.subscribe(listener);
    auth.logout();
    expect(auth.getToken()).toBeNull();
    expect(sessionStorage.getItem('floodready.admin.token')).toBeNull();
    expect(listener).toHaveBeenCalledTimes(1);
    off();
  });
});
