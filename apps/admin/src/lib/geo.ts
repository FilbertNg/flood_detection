import type { StreetFeature, StreetProperties } from '@floodready/shared';

/*
 * Street geometry for the ops map, the same maths as apps/resident/src/lib/geo.ts: the nearest street to a
 * point and the street under the map centre once zoomed in, for the popup.
 */

export interface Place {
  lat: number;
  lon: number;
}

/** Metres per degree of latitude; longitude is scaled by cos(latitude). Accurate to well under 1 % at BBR's size. */
const M_PER_DEG = 111_320;

export interface StreetHit {
  street: StreetProperties;
  distanceM: number;
  /** The point on the street line nearest the place. */
  point: Place;
}

/**
 * The street nearest a place, by distance to its line segments, computed on the phone from the
 * /streets geometry (the position is never sent anywhere for this). Null for an empty list.
 */
export function nearestStreet(place: Place, features: StreetFeature[]): StreetHit | null {
  const kx = M_PER_DEG * Math.cos((place.lat * Math.PI) / 180);
  const ky = M_PER_DEG;
  let best: StreetHit | null = null;
  for (const f of features) {
    const lines = f.geometry.type === 'LineString' ? [f.geometry.coordinates] : f.geometry.coordinates;
    for (const line of lines) {
      for (let i = 0; i < line.length; i++) {
        // Local metres with the place at the origin.
        const ax = (line[i][0] - place.lon) * kx, ay = (line[i][1] - place.lat) * ky;
        const b = line[i + 1] ?? line[i];
        const bx = (b[0] - place.lon) * kx, by = (b[1] - place.lat) * ky;
        const dx = bx - ax, dy = by - ay, len2 = dx * dx + dy * dy;
        const tt = len2 === 0 ? 0 : Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len2));
        const px = ax + tt * dx, py = ay + tt * dy;
        const d = Math.hypot(px, py);
        if (!best || d < best.distanceM) best = { street: f.properties, distanceM: d, point: { lat: place.lat + py / ky, lon: place.lon + px / kx } };
      }
    }
  }
  return best;
}

/** From this map zoom on, the street under the map centre is shown in a panel (a phone has no hover). */
export const REVEAL_ZOOM = 17;
/** The centre must be this close to a street line to pick it, so a park or a field picks nothing. */
const FOCUS_M = 40;

/** The street under the map centre once zoomed in to REVEAL_ZOOM (with the point on it nearest the centre), else null. */
export function focusedStreet(center: Place, zoom: number, features: StreetFeature[]): StreetHit | null {
  if (zoom < REVEAL_ZOOM) return null;
  const hit = nearestStreet(center, features);
  return hit && hit.distanceM <= FOCUS_M ? hit : null;
}
