/**
 * Onboarding once per visit: the start screen shows each time the app is opened (a new tab or a reopened
 * PWA), then the home page for the rest of that visit. Kept in sessionStorage, which ends with the tab;
 * when storage is unavailable the screen shows once per page load.
 */
const KEY = 'floodready.intro.v1';

export function introSeen(): boolean {
  try {
    return sessionStorage.getItem(KEY) === '1';
  } catch {
    return false;
  }
}

export function markIntroSeen(): void {
  try {
    sessionStorage.setItem(KEY, '1');
  } catch {
    // storage unavailable: the in-memory state still moves on for this page load
  }
}
