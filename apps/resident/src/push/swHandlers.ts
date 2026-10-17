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
    badge: '/icon-192.png',
  });
}

/** On click: reuse an open app window if there is one, otherwise open the street page. */
export async function focusOrOpen(clients: ClientsLike, url: string): Promise<void> {
  const windows = await clients.matchAll({ type: 'window', includeUncontrolled: true });
  const open = windows[0];
  if (open) {
    await open.navigate?.(url);
    await open.focus();
    return;
  }
  await clients.openWindow(url);
}
