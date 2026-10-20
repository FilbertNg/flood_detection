import type { StreetFeature, StreetProperties } from '@floodready/shared';

/** Rounded to 3 decimals (about 110 m) before leaving the phone. */
export function round3(n: number): number {
  return Math.round(n * 1000) / 1000;
}

export interface Place {
  lat: number;
  lon: number;
}

/** Ask the browser for one position. Call only after the resident ticked the consent box. */
export function currentPosition(): Promise<Place> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('no geolocation'));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: round3(pos.coords.latitude), lon: round3(pos.coords.longitude) }),
      (err) => reject(err),
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 60_000 },
    );
  });
}

/** Metres per degree of latitude; longitude is scaled by cos(latitude). Accurate to well under 1 % at BBR's size. */
const M_PER_DEG = 111_320;

/**
 * The street nearest a place, by distance to its line segments, computed on the phone from the
 * /streets geometry (the position is never sent anywhere for this). Null for an empty list.
 */
export function nearestStreet(place: Place, features: StreetFeature[]): { street: StreetProperties; distanceM: number } | null {
  const kx = M_PER_DEG * Math.cos((place.lat * Math.PI) / 180);
  const ky = M_PER_DEG;
  let best: { street: StreetProperties; distanceM: number } | null = null;
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
        const d = Math.hypot(ax + tt * dx, ay + tt * dy);
        if (!best || d < best.distanceM) best = { street: f.properties, distanceM: d };
      }
    }
  }
  return best;
}
