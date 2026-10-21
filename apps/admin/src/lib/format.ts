export const SUGGESTION_SUFFIX = 'Screening suggestion; site survey needed.';

/** 0.42 -> "42%". */
export const pct = (fraction: number): string => `${Math.round(fraction * 100)}%`;

/** Median lead time in minutes, or "n/a" when no alert had a confirmed flood after it. */
export const leadMin = (m: number | null): string => (m === null ? 'n/a' : `${Math.round(m)} min`);

export function ensureSuffix(text: string): string {
  const t = text.trim();
  return t.endsWith(SUGGESTION_SUFFIX) ? t : `${t} ${SUGGESTION_SUFFIX}`;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "2024-11-12" -> "12 Nov 2024". */
export function dateLabel(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split('-');
  return `${Number(d)} ${MONTHS[Number(m) - 1]} ${y}`;
}

const two = (n: number) => String(n).padStart(2, '0');

/** Today in local time as YYYY-MM-DD. */
export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())}`;
}

const DAY_MS = 86_400_000;
const utc = (iso: string) => Date.UTC(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10)));

/** A YYYY-MM-DD date moved by whole days (calendar arithmetic in UTC, so no time-zone drift). */
export function shiftDays(iso: string, days: number): string {
  return new Date(utc(iso) + days * DAY_MS).toISOString().slice(0, 10);
}

/** Days in a YYYY-MM-DD range, both ends included. */
export function daysInclusive(from: string, to: string): number {
  return Math.round((utc(to) - utc(from)) / DAY_MS) + 1;
}

const FULL_MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/** "2024-11" -> "November 2024". */
export function monthLabel(month: string): string {
  const [y, m] = month.split('-');
  return FULL_MONTHS[Number(m) - 1] ? `${FULL_MONTHS[Number(m) - 1]} ${y}` : month;
}
