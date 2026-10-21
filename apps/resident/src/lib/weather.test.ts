import { describe, expect, it } from 'vitest';
import { gaugeRain, hourAt, parseWeather, skyFor, skyGradient, weatherKind, weatherUrl } from './weather';

describe('weatherKind (WMO codes from Open-Meteo)', () => {
  it.each([
    [0, true, 'clear-day'],
    [1, false, 'clear-night'],
    [2, true, 'partly-day'],
    [2, false, 'partly-night'],
    [3, true, 'cloudy'],
    [45, true, 'fog'],
    [51, true, 'drizzle'],
    [61, true, 'drizzle'],
    [80, false, 'drizzle'],
    [63, true, 'rain'],
    [82, true, 'rain'],
    [95, true, 'storm'],
    [99, false, 'storm'],
  ] as const)('code %i, day %s → %s', (code, isDay, kind) => {
    expect(weatherKind(code, isDay)).toBe(kind);
  });

  it('treats an unknown code as cloudy rather than inventing rain or sun', () => {
    expect(weatherKind(7, true)).toBe('cloudy');
  });
});

describe('weatherUrl', () => {
  const now = new Date('2026-10-20T17:00:00+08:00');

  it('uses the forecast API for live data', () => {
    const url = weatherUrl('2026-10-20T16:45:00+08:00', now);
    expect(url).toContain('https://api.open-meteo.com/v1/forecast?');
    expect(url).toContain('start_date=2026-10-20');
    expect(url).toContain('end_date=2026-10-21');
    expect(url).toContain('hourly=weather_code,is_day,precipitation_probability');
    expect(url).toContain('timezone=Asia%2FKuala_Lumpur');
  });

  it('uses the historical forecast API for a replay of a past flood', () => {
    const url = weatherUrl('2024-11-12T09:00:00+08:00', now);
    expect(url).toContain('https://historical-forecast-api.open-meteo.com/v1/forecast?');
    expect(url).toContain('start_date=2024-11-12');
    expect(url).toContain('end_date=2024-11-13');
  });
});

describe('parseWeather', () => {
  const body = {
    hourly: {
      time: ['2024-11-12T08:00', '2024-11-12T09:00'],
      weather_code: [3, 63],
      is_day: [1, 1],
      precipitation_probability: [40, null],
    },
  };

  it('reads hourly codes, day flags and rain chance', () => {
    expect(parseWeather(body)).toEqual([
      { hour: '2024-11-12T08', code: 3, isDay: true, rainChance: 40 },
      { hour: '2024-11-12T09', code: 63, isDay: true, rainChance: null },
    ]);
  });

  it.each([null, {}, { hourly: {} }, { hourly: { time: ['x'], weather_code: 'bad' } }, { street_id: 'not weather' }])(
    'returns null for a body that is not Open-Meteo hourly data: %j',
    (bad) => {
      expect(parseWeather(bad)).toBeNull();
    },
  );

  it('finds the hour of a MYT timestamp', () => {
    const hours = parseWeather(body)!;
    expect(hourAt(hours, '2024-11-12T09:45:00+08:00')?.code).toBe(63);
    expect(hourAt(hours, '2024-11-12T11:00:00+08:00')).toBeNull();
  });
});

describe('gaugeRain', () => {
  const stations = [
    { graph_id: 'R1', name: 'Kg. Perepat, Kapar', kind: 'rf', lat: 0, lon: 0, latest: { time: 't', rain_1h_mm: 12.5, wl_m: null }, thresholds: null, is_stale: false },
    { graph_id: 'R2', name: 'Kapar', kind: 'rf', lat: 0, lon: 0, latest: { time: 't', rain_1h_mm: 3, wl_m: null }, thresholds: null, is_stale: false },
    { graph_id: 'R3', name: 'Stale gauge', kind: 'rf', lat: 0, lon: 0, latest: { time: 't', rain_1h_mm: 80, wl_m: null }, thresholds: null, is_stale: true },
    { graph_id: 'W1', name: 'River', kind: 'wl', lat: 0, lon: 0, latest: { time: 't', rain_1h_mm: null, wl_m: 3 }, thresholds: null, is_stale: false },
  ] as const;

  it('takes the wettest fresh rain gauge that decides this street', () => {
    expect(gaugeRain([...stations], ['W1', 'R2', 'R1', 'R3'])).toEqual({ mm: 12.5, station: 'Kg. Perepat, Kapar' });
  });

  it('ignores gauges not linked to the street and copes with a non-list reply', () => {
    expect(gaugeRain([...stations], ['W1'])).toBeNull();
    expect(gaugeRain({ not: 'a list' }, ['R1'])).toBeNull();
  });
});

describe('skyFor', () => {
  it('follows the weather when the street is Normal or Watch', () => {
    expect(skyFor('normal', 'cloudy', null)).toBe('cloudy');
    expect(skyFor('watch', 'clear-night', null)).toBe('clear-night');
  });

  it('shows rain when the street’s own gauge measured rain, even if the model says cloudy', () => {
    expect(skyFor('normal', 'cloudy', { mm: 1.2, station: 'X' })).toBe('drizzle');
    expect(skyFor('normal', 'cloudy', { mm: 12, station: 'X' })).toBe('rain');
    expect(skyFor('normal', 'storm', { mm: 12, station: 'X' })).toBe('storm');
  });

  it('switches to the calm alert sky at Warning and Danger', () => {
    expect(skyFor('warning', 'storm', { mm: 40, station: 'X' })).toBe('alert');
    expect(skyFor('danger', 'clear-day', null)).toBe('alert');
  });

  it('falls back to a neutral sky when there is no weather and no gauge rain', () => {
    expect(skyFor('normal', null, null)).toBe('none');
  });
});

describe('skyGradient', () => {
  const lum = (hex: string) => {
    const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  };
  const contrastWithWhite = (hex: string) => 1.05 / (lum(hex) + 0.05);
  /** The stop with 12 % white over it: the margin for clouds drawn behind the hero text. */
  const withCloud = (hex: string) =>
    '#' + [1, 3, 5].map((i) => Math.round(parseInt(hex.slice(i, i + 2), 16) * 0.88 + 255 * 0.12).toString(16).padStart(2, '0')).join('');
  const skies = ['clear-day', 'clear-night', 'partly-day', 'partly-night', 'cloudy', 'fog', 'drizzle', 'rain', 'storm', 'alert', 'none'] as const;

  it.each(skies)('%s has three stops, dark enough for white text (>= 4.5:1) even with clouds over it', (sky) => {
    const stops = skyGradient(sky);
    expect(stops).toHaveLength(3);
    for (const s of stops) {
      expect(contrastWithWhite(s)).toBeGreaterThanOrEqual(4.5);
      expect(contrastWithWhite(withCloud(s))).toBeGreaterThanOrEqual(4.5);
    }
  });
});
