import type { PushPayload } from '@floodready/shared';

interface Notifier {
  showNotification(title: string, options?: NotificationOptions): Promise<void>;
}

interface WindowLike {
  url: string;
  focus(): Promise<unknown>;
  navigate?(url: string): Promise<unknown>;
}

interface ClientsLike {
  matchAll(options?: { type?: 'window'; includeUncontrolled?: boolean }): Promise<readonly WindowLike[]>;
  openWindow(url: string): Promise<unknown>;
}

/** Show a Web Push message; the street path travels in `data.url` for the click handler. */
export function showPushNotification(registration: Notifier, payload: PushPayload): Promise<void> {
  return registration.showNotification(payload.title, {
    body: payload.body,
    tag: payload.alert_id,
    data: { url: payload.url },
    icon: '/icon-192.png',
    badge: '/badge-96.png',
  });
}

/** Resolve a push-supplied URL to a same-origin path; anything else falls back to the home page. */
export function sameOriginPath(url: string | undefined, origin: string): string {
  if (!url) return '/';
  try {
    const resolved = new URL(url, origin);
    if (resolved.origin !== new URL(origin).origin) return '/';
    return resolved.pathname + resolved.search + resolved.hash;
  } catch {
    return '/';
  }
}

/** On click: reuse an open app window if there is one, otherwise open the street page. */
export async function focusOrOpen(clients: ClientsLike, rawUrl: string | undefined, origin: string): Promise<void> {
  const url = sameOriginPath(rawUrl, origin);
  const windows = await clients.matchAll({ type: 'window', includeUncontrolled: true });
  const open = windows[0];
  if (open) {
    await open.navigate?.(url);
    await open.focus();
    return;
  }
  await clients.openWindow(url);
}
