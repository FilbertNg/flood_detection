import type { Level, Station } from '@floodready/shared';

/**
 * Weather for the street page background, straight from Open-Meteo in the browser.
 * Display only: it never feeds the flood level, which always comes from our API (JPS rules).
 */

/** Township centre, the same point the map opens on. */
export const WEATHER_POINT = { lat: 3.0852, lon: 101.4377 };

export type WeatherKind =
  | 'clear-day' | 'clear-night' | 'partly-day' | 'partly-night'
  | 'cloudy' | 'fog' | 'drizzle' | 'rain' | 'storm';

/** What the backdrop draws: a weather kind, the calm alert sky, or a neutral sky when nothing is known. */
export type Sky = WeatherKind | 'alert' | 'none';

export interface WeatherHour {
  /** "2024-11-12T09" (MYT) */
  hour: string;
  code: number;
  isDay: boolean;
  /** Percent, or null when Open-Meteo has no value for that hour. */
  rainChance: number | null;
}

/** WMO weather code → kind. Unknown codes fall back to cloudy, never to rain or sun. */
export function weatherKind(code: number, isDay: boolean): WeatherKind {
  if (code <= 1) return isDay ? 'clear-day' : 'clear-night';
  if (code === 2) return isDay ? 'partly-day' : 'partly-night';
  if (code === 45 || code === 48) return 'fog';
  if ((code >= 51 && code <= 57) || code === 61 || code === 80) return 'drizzle';
  if ((code >= 63 && code <= 67) || code === 81 || code === 82) return 'rain';
  if (code >= 95 && code <= 99) return 'storm';
  return 'cloudy';
}

const DAY_MS = 86_400_000;

function addDay(date: string): string {
  return new Date(Date.parse(`${date}T00:00:00Z`) + DAY_MS).toISOString().slice(0, 10);
}

/** Hourly weather for the data time's day and the next: live forecast, or the archive for a replay. */
export function weatherUrl(dataTime: string, now: Date = new Date()): string {
  const date = dataTime.slice(0, 10);
  const live = Math.abs(now.getTime() - Date.parse(dataTime)) < 2 * DAY_MS;
  const host = live ? 'https://api.open-meteo.com' : 'https://historical-forecast-api.open-meteo.com';
  const params = new URLSearchParams({
    latitude: String(WEATHER_POINT.lat),
    longitude: String(WEATHER_POINT.lon),
    start_date: date,
    end_date: addDay(date),
    hourly: 'weather_code,is_day,precipitation_probability',
    timezone: 'Asia/Kuala_Lumpur',
  });
  return `${host}/v1/forecast?${params.toString().replace(/%2C/g, ',')}`;
}

/** Open-Meteo hourly body → hours, or null for anything that is not that shape. */
export function parseWeather(body: unknown): WeatherHour[] | null {
  const hourly = (body as { hourly?: Record<string, unknown> } | null)?.hourly;
  if (!hourly) return null;
  const { time, weather_code: codes, is_day: day, precipitation_probability: chance } = hourly;
  if (!Array.isArray(time) || !Array.isArray(codes) || time.length === 0 || codes.length !== time.length) return null;
  const hours: WeatherHour[] = [];
  time.forEach((t, i) => {
    const code = codes[i];
    if (typeof t !== 'string' || typeof code !== 'number') return;
    const c = Array.isArray(chance) ? chance[i] : null;
    hours.push({
      hour: t.slice(0, 13),
      code,
      isDay: Array.isArray(day) ? day[i] === 1 : true,
      rainChance: typeof c === 'number' ? c : null,
    });
  });
  return hours.length ? hours : null;
}

/** The hour containing an ISO time (MYT, as all API times are). */
export function hourAt(hours: WeatherHour[] | null, iso: string): WeatherHour | null {
  return hours?.find((h) => h.hour === iso.slice(0, 13)) ?? null;
}

export interface GaugeRain {
  mm: number;
  station: string;
}

/** Wettest fresh JPS rain gauge among the stations that decide this street; null when none is raining. */
export function gaugeRain(stations: unknown, ids: string[]): GaugeRain | null {
  if (!Array.isArray(stations)) return null;
  let best: GaugeRain | null = null;
  for (const s of stations as Station[]) {
    const mm = s.latest?.rain_1h_mm;
    if (s.kind !== 'rf' || s.is_stale || !ids.includes(s.graph_id) || typeof mm !== 'number' || mm <= 0) continue;
    if (!best || mm > best.mm) best = { mm, station: s.name };
  }
  return best;
}

/** Light rain per WMO is under 2.5 mm/h; used only to pick drizzle or rain for the picture. */
const LIGHT_RAIN_MM = 2.5;

/**
 * The backdrop for a street. Warning and Danger always get the calm alert sky, so a pretty
 * sky never softens an alert. A gauge that measured rain wins over the model's cloud.
 */
export function skyFor(level: Level, kind: WeatherKind | null, gauge: GaugeRain | null): Sky {
  if (level === 'warning' || level === 'danger') return 'alert';
  if (gauge && kind !== 'rain' && kind !== 'storm') return gauge.mm < LIGHT_RAIN_MM ? 'drizzle' : 'rain';
  return kind ?? 'none';
}

/**
 * Three vertical stops (top, middle, bottom) per sky, for the street hero card. Every stop keeps
 * white text at >= 4.5:1, also with 12 % white over it: a margin for the soft clouds the canvas draws
 * behind the text. So the proposal's light day blue is darkened.
 */
const SKY_STOPS: Record<Sky, [string, string, string]> = {
  'clear-day': ['#174f86', '#1f5f9e', '#2b679c'],
  'clear-night': ['#0a1228', '#121d3d', '#1e2d55'],
  'partly-day': ['#244f7a', '#2c5f8f', '#456585'],
  'partly-night': ['#111a31', '#1b2643', '#2b3858'],
  cloudy: ['#3f4c5d', '#4f5e70', '#576273'],
  fog: ['#4b5560', '#525c68', '#59636e'],
  drizzle: ['#2c3a57', '#3d4b5c', '#556278'],
  rain: ['#202b39', '#2b3746', '#414f62'],
  storm: ['#161c2a', '#1d2230', '#323a4d'],
  alert: ['#15171d', '#1a1d24', '#2a2e38'],
  none: ['#3c4656', '#4a5566', '#586271'],
};

export function skyGradient(sky: Sky): [string, string, string] {
  return SKY_STOPS[sky];
}
