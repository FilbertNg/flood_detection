/// <reference lib="webworker" />
import { precacheAndRoute } from 'workbox-precaching';
import { focusOrOpen, showPushNotification } from './push/swHandlers';
import type { PushPayload } from '@floodready/shared';

declare let self: ServiceWorkerGlobalScope;

precacheAndRoute(self.__WB_MANIFEST);

// Web Push (task R4 / B2): show the alert; tapping it opens the street page.
self.addEventListener('push', (event) => {
  if (!event.data) return;
  const payload = event.data.json() as PushPayload;
  event.waitUntil(showPushNotification(self.registration, payload));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data as { url?: string } | undefined)?.url ?? '/';
  event.waitUntil(focusOrOpen(self.clients as unknown as Parameters<typeof focusOrOpen>[0], url));
});
