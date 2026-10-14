import type { Lang } from '@floodready/shared';

/** Resident preferences live on the device only (no account): language, followed streets, device id. */
const KEY = 'floodready.prefs.v1';

export interface Prefs {
  lang: Lang;
  streets: string[];
  deviceId: string;
}

function newDeviceId(): string {
  return `dev_${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
}

export function loadPrefs(): Prefs {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const p = JSON.parse(raw) as Partial<Prefs>;
      return { lang: p.lang === 'ms' ? 'ms' : 'en', streets: Array.isArray(p.streets) ? p.streets : [], deviceId: p.deviceId ?? newDeviceId() };
    }
  } catch {
    // storage unavailable (private mode): fall through to defaults
  }
  return { lang: 'en', streets: [], deviceId: newDeviceId() };
}

export function savePrefs(prefs: Prefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    // ignore: preferences then last for this visit only
  }
}
