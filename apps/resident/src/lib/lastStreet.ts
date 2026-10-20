/** The street the resident last looked at in the pager, for this browser session only. */
const KEY = 'floodready.lastStreet';

export function readLastStreet(): string | null {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function writeLastStreet(id: string): void {
  try {
    sessionStorage.setItem(KEY, id);
  } catch {
    // storage blocked: the pager then opens on the first street next time
  }
}
