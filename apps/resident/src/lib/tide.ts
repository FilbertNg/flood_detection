import type { StreetDetail } from '@floodready/shared';

/** Port Klang tide: hourly heights from the API (`StreetDetail.tide`). */
export type TidePoint = StreetDetail['tide'][number];

/** Where `at` falls on the hourly series, as a fractional index (0 = first hour), clamped to the series. */
export function tideIndexAt(tide: TidePoint[], at: string): number {
  if (tide.length < 2) return 0;
  const t0 = Date.parse(tide[0].time);
  const hours = (Date.parse(at) - t0) / 3_600_000;
  return Math.min(tide.length - 1, Math.max(0, hours));
}

/** The first high and the first low water after `from` (a fractional index); null when the series ends first. */
export function tideTurns(tide: TidePoint[], from: number): { high: number | null; low: number | null } {
  let high: number | null = null, low: number | null = null;
  for (let i = Math.max(1, Math.ceil(from)); i < tide.length - 1; i++) {
    const [a, b, c] = [tide[i - 1].height_m, tide[i].height_m, tide[i + 1].height_m];
    if (high === null && b >= a && b >= c && b > Math.min(a, c)) high = i;
    if (low === null && b <= a && b <= c && b < Math.max(a, c)) low = i;
  }
  return { high, low };
}

/** Rising or falling at `at` (a fractional index), from the hourly stretch it falls in. */
export function tideTrend(tide: TidePoint[], at: number): 'rising' | 'falling' | null {
  if (tide.length < 2) return null;
  const i = Math.min(Math.floor(at), tide.length - 2);
  const d = tide[i + 1].height_m - tide[i].height_m;
  return d > 0 ? 'rising' : d < 0 ? 'falling' : null;
}
