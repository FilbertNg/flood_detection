import { describe, expect, it, vi } from 'vitest';
import type { PushPayload } from '@floodready/shared';
import { focusOrOpen, sameOriginPath, showPushNotification } from './swHandlers';

const ORIGIN = 'https://app.test';
const payload: PushPayload = { title: 'Warning', body: 'Jalan Makyong', url: '/street/BBR-jalan-makyong', alert_id: 'a1', level: 'warning' };

describe('showPushNotification', () => {
  it('shows title, body and the url in data', async () => {
    const show = vi.fn(async () => undefined);
    await showPushNotification({ showNotification: show }, payload);
    expect(show).toHaveBeenCalledWith('Warning', expect.objectContaining({ body: 'Jalan Makyong', data: { url: '/street/BBR-jalan-makyong' }, tag: 'a1' }));
  });
});

describe('focusOrOpen', () => {
  it('focuses and navigates an open window', async () => {
    const win = { url: 'https://app.test/', focus: vi.fn(async () => win), navigate: vi.fn(async () => win) };
    const openWindow = vi.fn();
    await focusOrOpen({ matchAll: async () => [win], openWindow }, '/street/BBR-x', ORIGIN);
    expect(win.navigate).toHaveBeenCalledWith('/street/BBR-x');
    expect(win.focus).toHaveBeenCalled();
    expect(openWindow).not.toHaveBeenCalled();
  });
  it('opens the street page when no window is open', async () => {
    const openWindow = vi.fn();
    await focusOrOpen({ matchAll: async () => [], openWindow }, '/street/BBR-x', ORIGIN);
    expect(openWindow).toHaveBeenCalledWith('/street/BBR-x');
  });
});

describe('sameOriginPath', () => {
  it('keeps a relative path', () => {
    expect(sameOriginPath('/street/BBR-x', ORIGIN)).toBe('/street/BBR-x');
  });
  it('keeps a same-origin absolute URL as a path', () => {
    expect(sameOriginPath('https://app.test/street/BBR-x?a=1', ORIGIN)).toBe('/street/BBR-x?a=1');
  });
  it('falls back to / for a foreign absolute URL', () => {
    expect(sameOriginPath('https://evil.example/phish', ORIGIN)).toBe('/');
  });
  it('falls back to / for a protocol-relative URL', () => {
    expect(sameOriginPath('//evil.example', ORIGIN)).toBe('/');
  });
  it('falls back to / for javascript: and empty values', () => {
    expect(sameOriginPath('javascript:alert(1)', ORIGIN)).toBe('/');
    expect(sameOriginPath('', ORIGIN)).toBe('/');
    expect(sameOriginPath(undefined, ORIGIN)).toBe('/');
  });
});

describe('focusOrOpen origin check', () => {
  it('opens / instead of a foreign URL', async () => {
    const openWindow = vi.fn();
    await focusOrOpen({ matchAll: async () => [], openWindow }, 'https://evil.example/x', ORIGIN);
    expect(openWindow).toHaveBeenCalledWith('/');
  });
});
