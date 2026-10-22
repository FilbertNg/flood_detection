import type { Suggestion, SuggestionStatus } from '@floodready/shared';
import { SUGGESTION_SUFFIX } from './format';

/**
 * Display helpers for the suggestion card. Everything comes from the structured evidence the API sends
 * (floodready/stats/suggestions.py); `evidence.notes` is shown as text only, never parsed for numbers.
 */

/** The action (headline) and the screening caveat. The contract always ends the text with the caveat. */
export function splitText(text: string): { action: string; caveat: string } {
  const t = text.trim();
  const action = t.endsWith(SUGGESTION_SUFFIX) ? t.slice(0, -SUGGESTION_SUFFIX.length).trim() : t;
  return { action, caveat: SUGGESTION_SUFFIX };
}

export interface StatTile {
  key: string;
  value: string;
  /** Small text after the value: "of 79", "mm". */
  of?: string;
  label: string;
  /** Spans both columns on phones (long values such as a station name). */
  wide?: boolean;
}

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const isText = (v: unknown): v is string => typeof v === 'string' && v.trim() !== '';
const dates = (v: unknown): string[] => (Array.isArray(v) ? v.filter(isText) : []);

/** What a rule's flood dates are: one street's confirmed floods, distinct days across a cluster, or resident reports. */
const FLOOD_LABEL: Partial<Record<Suggestion['rule'], string>> = { 'SUG-4': 'Days with confirmed floods', 'SUG-6': 'Resident-reported floods' };

/** Stat tiles for a suggestion, only for values the API sent; a missing value gives no tile. */
export function statTiles(s: Suggestion): StatTile[] {
  const e = s.evidence;
  const out: StatTile[] = [];
  if (isNum(e.rank) && isNum(e.eligible_streets)) {
    out.push({ key: 'rank', value: String(e.rank), of: `of ${e.eligible_streets}`, label: 'Rank among eligible streets' });
  }
  const episodes = dates(e.episode_dates);
  if (episodes.length) out.push({ key: 'episodes', value: String(episodes.length), label: 'Separate alert episodes' });
  const floods = dates(e.flood_dates);
  if (floods.length) out.push({ key: 'floods', value: String(floods.length), label: FLOOD_LABEL[s.rule] ?? 'Confirmed floods' });
  if (isText(e.max_depth)) out.push({ key: 'depth', value: e.max_depth.replace(/_/g, ' '), label: 'Deepest reported' });
  const rain = Array.isArray(e.rain_at_onset_mm) ? e.rain_at_onset_mm.filter(isNum) : [];
  if (rain.length) out.push({ key: 'rain', value: Math.max(...rain).toFixed(1), of: 'mm', label: 'Heaviest rain at onset' });
  if (isText(e.river_station_name)) {
    const shared = e.eligible_streets_on_same_river_station;
    out.push({
      key: 'station', value: e.river_station_name, wide: true,
      label: `River station driving the count${isNum(shared) ? `, shared by ${shared} eligible streets` : ''}`,
    });
  }
  return out;
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

export interface MonthStrip {
  /** "2024-04" */
  key: string;
  /** "April 2024" */
  label: string;
  /** Days in the month. */
  days: number;
  /** Days of the month that have a date, ascending. */
  on: number[];
}

/** Dates (ISO, MYT) grouped into one strip per month, oldest first; null beyond three months (show a list). */
export function dateMonths(list: string[], max = 3): MonthStrip[] | null {
  const byMonth = new Map<string, Set<number>>();
  for (const d of list) {
    const key = d.slice(0, 7);
    if (!byMonth.has(key)) byMonth.set(key, new Set());
    byMonth.get(key)!.add(Number(d.slice(8, 10)));
  }
  if (byMonth.size === 0 || byMonth.size > max) return null;
  return [...byMonth.keys()].sort().map((key) => {
    const [y, m] = key.split('-').map(Number);
    return { key, label: `${MONTHS[m - 1]} ${y}`, days: new Date(Date.UTC(y, m, 0)).getUTCDate(), on: [...byMonth.get(key)!].sort((a, b) => a - b) };
  });
}

/** "16, 17 and 22 April 2024; 2 May 2024": the dates in words, per month, for screen readers. */
export function datesInWords(list: string[]): string {
  const months = dateMonths(list, Infinity) ?? [];
  return months.map((m) => {
    const d = m.on.map(String);
    const days = d.length > 1 ? `${d.slice(0, -1).join(', ')} and ${d[d.length - 1]}` : d[0];
    return `${days} ${m.label}`;
  }).join('; ');
}

export interface NextStep { label: string; to: SuggestionStatus; kind: 'primary' | 'outline' | 'text' }

/** The buttons for each status: only the next step, never all four statuses. */
export const NEXT_STEPS: Record<SuggestionStatus, NextStep[]> = {
  open: [{ label: 'Accept', to: 'accepted', kind: 'primary' }, { label: 'Dismiss', to: 'dismissed', kind: 'outline' }],
  accepted: [{ label: 'Mark done', to: 'done', kind: 'primary' }, { label: 'Back to open', to: 'open', kind: 'text' }],
  dismissed: [{ label: 'Reopen', to: 'open', kind: 'outline' }],
  done: [{ label: 'Reopen', to: 'open', kind: 'text' }],
};

export const STATUS_LABEL: Record<SuggestionStatus, string> = { open: 'Open', accepted: 'Accepted', dismissed: 'Dismissed', done: 'Done' };
