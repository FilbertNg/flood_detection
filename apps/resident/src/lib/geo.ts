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
