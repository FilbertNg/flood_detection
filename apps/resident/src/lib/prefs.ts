import type { Lang } from '@floodready/shared';

/** Resident preferences live on the device only (no account): language, followed streets, device id. */
const KEY = 'floodready.prefs.v1';

export interface Prefs {
  lang: Lang;
  streets: string[];
  deviceId: string;
}

/** The API accepts device ids matching this (docs/api-contract.md); the id authorises deleting the device's data. */
const DEVICE_ID = /^[A-Za-z0-9_-]{16,64}$/;

/** crypto.randomUUID only exists in secure contexts (https, localhost); a LAN http demo needs the fallback. */
function newDeviceId(): string {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
    if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
      const bytes = crypto.getRandomValues(new Uint8Array(16));
      return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
    }
  } catch {
    // fall through to the last resort
  }
  return Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join(''); // last resort; id only, not a secret key
}

function validDeviceId(id: unknown): id is string {
  return typeof id === 'string' && DEVICE_ID.test(id);
}

/** First visit, nothing saved: Malay when the phone's language is Malay, otherwise English. */
function phoneLang(): Lang {
  try {
    return navigator.language?.toLowerCase().startsWith('ms') ? 'ms' : 'en';
  } catch {
    return 'en';
  }
}

export function loadPrefs(): Prefs {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const p = JSON.parse(raw) as Partial<Prefs>;
      return { lang: p.lang === 'ms' ? 'ms' : 'en', streets: Array.isArray(p.streets) ? p.streets : [], deviceId: validDeviceId(p.deviceId) ? p.deviceId : newDeviceId() };
    }
  } catch {
    // storage unavailable (private mode): fall through to defaults
  }
  return { lang: phoneLang(), streets: [], deviceId: newDeviceId() };
}

export function savePrefs(prefs: Prefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    // ignore: preferences then last for this visit only
  }
}
