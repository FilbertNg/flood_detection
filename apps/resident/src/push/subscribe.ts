import type { Lang, SubscriptionRequest, WebPushSubscription } from '@floodready/shared';
import { api } from '../lib/api';

export type PushSupport = 'ok' | 'needs-install' | 'unsupported';
export type EnableResult = 'granted' | 'denied' | 'unsupported' | 'error';

export interface PushInput {
  deviceId: string;
  streetIds: string[];
  lang: Lang;
}

function isIos(): boolean {
  // iPadOS 13+ reports a Macintosh user agent but has touch points
  return /iPhone|iPad|iPod/.test(navigator.userAgent) || (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);
}

function isStandalone(): boolean {
  const nav = navigator as Navigator & { standalone?: boolean };
  return nav.standalone === true || (typeof matchMedia === 'function' && matchMedia('(display-mode: standalone)').matches);
}

/** iPhone Safari only supports Web Push for an installed (Add to Home Screen) app. */
export function pushSupport(): PushSupport {
  if (isIos() && !isStandalone()) return 'needs-install';
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || typeof Notification === 'undefined') return 'unsupported';
  return 'ok';
}

export function permissionState(): NotificationPermission | 'unsupported' {
  return typeof Notification === 'undefined' ? 'unsupported' : Notification.permission;
}

export function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padded = (base64 + '='.repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(padded);
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

async function currentSubscription(): Promise<PushSubscription | null> {
  const registration = await navigator.serviceWorker.ready;
  return registration.pushManager.getSubscription();
}

export async function isSubscribed(): Promise<boolean> {
  if (pushSupport() !== 'ok') return false;
  try {
    return (await currentSubscription()) !== null;
  } catch {
    return false;
  }
}

function request(input: PushInput, subscription: PushSubscription): SubscriptionRequest {
  return {
    device_id: input.deviceId,
    subscription: { ...(subscription.toJSON() as WebPushSubscription), expirationTime: subscription.toJSON().expirationTime ?? null },
    street_ids: input.streetIds,
    lang: input.lang,
  };
}

/** Ask permission, subscribe with the server key, register the subscription with the chosen streets and language. */
export async function enablePush(input: PushInput): Promise<EnableResult> {
  if (pushSupport() !== 'ok') return 'unsupported';
  try {
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') return 'denied';
    const registration = await navigator.serviceWorker.ready;
    const { key } = await api.pushPublicKey();
    const subscription =
      (await registration.pushManager.getSubscription()) ??
      (await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(key) as BufferSource }));
    await api.subscribe(request(input, subscription));
    return 'granted';
  } catch {
    return 'error';
  }
}

/** Re-post streets and language for a device that is already subscribed (no prompt, no new subscription). */
export async function syncPush(input: PushInput): Promise<void> {
  if (pushSupport() !== 'ok') return;
  try {
    const subscription = await currentSubscription();
    if (subscription) await api.subscribe(request(input, subscription));
  } catch {
    // best effort: the next change retries
  }
}

/** Delete this device's server data and drop the browser subscription. */
export async function stopPush(deviceId: string): Promise<void> {
  await api.unsubscribe(deviceId);
  const subscription = await currentSubscription();
  await subscription?.unsubscribe();
}
