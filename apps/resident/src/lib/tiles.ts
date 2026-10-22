import type { StreetDetail, Susceptibility } from '@floodready/shared';
import { riverScale, type Thresholds } from './river';
import { tideIndexAt, tideTurns, type TidePoint } from './tide';

/**
 * Geometry for the picture tiles on the street page (components/PanelTiles.tsx). Pure functions of the
 * readings, in each picture's own viewBox units, so the drawing maths is tested without the DOM.
 */

/** Water drop outline in an 80 × 104 box. */
export const DROP_PATH = 'M40 6C40 6 12 40 12 62a28 28 0 0 0 56 0C68 40 40 6 40 6z';
/** The drop is full from 30 mm in an hour (well into WMO "heavy", 10 mm/h). */
export const DROP_FULL_MM = 30;

/** Top of the water in the drop for mm in the last hour: 92 when empty, 8 when full (30 mm and up). */
export function dropFillTop(mm: number): number {
  const f = Math.min(Math.max(mm, 0) / DROP_FULL_MM, 1);
  return 8 + (1 - f) * 84;
}

export const BARS = { width: 112, height: 70, step: 9.4, bar: 6 };

/**
 * One rounded bar per forecast hour, bottoms on the baseline. The scale tops out at the wettest hour
 * but never below 5 mm, so light drizzle does not look like a downpour; dry hours are a 3 px stub.
 */
export function rainBars(rain: StreetDetail['rain_next_12h']): { x: number; y: number; h: number; wet: boolean }[] {
  const max = Math.max(5, ...rain.map((p) => p.mm));
  return rain.map((p, i) => {
    const h = Math.max(3, (p.mm / max) * BARS.height);
    return { x: i * BARS.step, y: BARS.height - h, h, wet: p.mm > 0 };
  });
}

/** Time of the wettest forecast hour (the first if tied), or null when no rain is expected. */
export function heaviestHour(rain: StreetDetail['rain_next_12h']): string | null {
  let best: StreetDetail['rain_next_12h'][number] | null = null;
  for (const p of rain) if (p.mm > 0 && (!best || p.mm > best.mm)) best = p;
  return best?.time ?? null;
}

/** River gauge pill: 112 px tall, 4 px inset top and bottom. */
export const PILL = { height: 112, inset: 4 };

/** Height on the pill for a river level, on the river meter's scale (clamped inside the pill). */
export function pillY(m: number, th: Thresholds): number {
  const at = riverScale(th);
  return PILL.inset + (1 - at(m) / 100) * (PILL.height - 2 * PILL.inset);
}

/** The JPS alert, warning and danger ticks on the pill. */
export function pillTicks(th: Thresholds): { mark: 'alert' | 'warning' | 'danger'; y: number }[] {
  return (['alert', 'warning', 'danger'] as const).map((mark) => ({ mark, y: pillY(th[mark], th) }));
}

/** A closed scalloped badge (n lobes between radius r and R), starting and ending at the top. */
export function scallopPath(n = 12, R = 40, r = 35, cx = 46, cy = 46): string {
  const steps = n * 8;
  let d = '';
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * Math.PI * 2;
    const rr = r + (R - r) * (0.5 + 0.5 * Math.cos(a * n));
    d += `${i ? 'L' : 'M'}${(cx + rr * Math.sin(a)).toFixed(1)},${(cy - rr * Math.cos(a)).toFixed(1)}`;
  }
  return `${d}z`;
}

/** Arc length of a ring of radius R filled to p (0 to 1), and its circumference, for stroke-dasharray. */
export function ringDash(p: number, R = 34): { len: number; C: number } {
  const C = 2 * Math.PI * R;
  return { len: Math.min(Math.max(p, 0), 1) * C, C };
}

export type TileTone = 'ok' | 'watch' | 'warn';

/** Flood model ring colour: display only (the level always follows JPS). */
export function ringTone(p: number): TileTone {
  return p >= 0.5 ? 'warn' : p >= 0.2 ? 'watch' : 'ok';
}

/** Street badge colour by flood-prone score. */
export function proneTone(s: Susceptibility): TileTone {
  return s >= 4 ? 'warn' : s === 3 ? 'watch' : 'ok';
}

/** The next high water after the data time in the hours the API sends, or null if the series ends first. */
export function nextHighWater(tide: TidePoint[], dataTime: string): TidePoint | null {
  const i = tideTurns(tide, tideIndexAt(tide, dataTime)).high;
  return i === null ? null : tide[i];
}

export const WAVE = { width: 210, height: 84 };

/**
 * The tide wave over the hours the API sends (data hour to +12 h): the line, the filled area under it, the
 * part up to now as its own area, now as a point on the line, and three hour labels (first, middle, last).
 */
export function tideWave(tide: TidePoint[], dataTime: string) {
  const { width: W, height: H } = WAVE;
  const last = tide.length - 1;
  const ys = tide.map((p) => p.height_m);
  const lo = Math.min(...ys), span = Math.max(...ys) - lo || 1;
  const x = (i: number) => (last > 0 ? (i / last) * W : 0);
  const y = (v: number) => H - 8 - ((v - lo) / span) * (H - 16);
  const pt = (i: number) => `${x(i).toFixed(1)},${y(ys[i]).toFixed(1)}`;
  const line = ys.map((_, i) => `${i ? 'L' : 'M'}${pt(i)}`).join(' ');
  const at = tideIndexAt(tide, dataTime);
  const a = Math.floor(at), b = Math.min(a + 1, last);
  const nowH = ys[a] + (ys[b] - ys[a]) * (at - a);
  const now = { x: x(at), y: y(nowH) };
  const upTo = ys.slice(0, a + 1).map((_, i) => `${i ? 'L' : 'M'}${pt(i)}`).join(' ');
  const past = `${upTo} L${now.x.toFixed(1)},${now.y.toFixed(1)} L${now.x.toFixed(1)},${H} L0,${H}z`;
  const area = `${line} L${x(last).toFixed(1)},${H} L0,${H}z`;
  const labels = [...new Set([0, Math.floor(last / 2), last])].map((i) => ({ x: x(i), time: tide[i].time, anchor: i === 0 ? 'start' : i === last ? 'end' : 'middle' }));
  return { line, area, past, now, labels };
}

/** Clock hand angles (degrees clockwise from 12) for an ISO time in MYT. */
export function clockHands(iso: string): { hour: number; minute: number } {
  const h = Number(iso.slice(11, 13)), m = Number(iso.slice(14, 16));
  return { hour: ((h % 12) + m / 60) * 30, minute: m * 6 };
}
