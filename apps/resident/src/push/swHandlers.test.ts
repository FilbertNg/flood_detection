import { describe, expect, it, vi } from 'vitest';
import type { PushPayload } from '@floodready/shared';
import { focusOrOpen, showPushNotification } from './swHandlers';

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
    await focusOrOpen({ matchAll: async () => [win], openWindow }, '/street/BBR-x');
    expect(win.navigate).toHaveBeenCalledWith('/street/BBR-x');
    expect(win.focus).toHaveBeenCalled();
    expect(openWindow).not.toHaveBeenCalled();
  });
  it('opens the street page when no window is open', async () => {
    const openWindow = vi.fn();
    await focusOrOpen({ matchAll: async () => [], openWindow }, '/street/BBR-x');
    expect(openWindow).toHaveBeenCalledWith('/street/BBR-x');
  });
});
