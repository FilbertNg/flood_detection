import type { Station } from '@floodready/shared';

export type Thresholds = NonNullable<Station['thresholds']>;

/** The first fresh river (wl) station with a reading among the stations that decide this street. */
export function streetRiver(stations: unknown, ids: string[]): Station | null {
  const list = Array.isArray(stations) ? (stations as Station[]) : [];
  return ids
    .map((id) => list.find((s) => s.graph_id === id))
    .find((s): s is Station => !!s && s.kind === 'wl' && !s.is_stale && typeof s.latest?.wl_m === 'number') ?? null;
}

/**
 * Position (0 to 100) of a level on the river meter. The scale starts three alert-to-danger spans
 * below the alert mark, so ordinary levels still move, and ends a little above danger.
 */
export function riverScale(th: Thresholds): (v: number) => number {
  const span = th.danger - th.alert;
  const lo = th.alert - span * 3;
  const hi = th.danger + span * 0.75;
  return (v) => Math.min(100, Math.max(0, ((v - lo) / (hi - lo)) * 100));
}
