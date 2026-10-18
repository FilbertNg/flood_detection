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
