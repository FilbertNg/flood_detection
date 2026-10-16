import { describe, expect, it } from 'vitest';
import { streetDetail } from '@floodready/shared/mocks';
import { dayTime, hhmm, percent, riverForecastText, windowText } from './format';

const mockForecast = streetDetail.river_forecast!;
const W = { start: '2024-11-12T09:30:00+08:00', end: '2024-11-12T10:30:00+08:00' };

describe('format', () => {
  it('shows the expected flooding window in the chosen language', () => {
    expect(windowText(W, 'en')).toBe('between 09:30 and 10:30');
    expect(windowText(W, 'ms')).toBe('antara 09:30 dan 10:30');
  });

  it('formats times and probabilities', () => {
    expect(hhmm('2024-11-12T09:00:00+08:00')).toBe('09:00');
    expect(dayTime('2024-11-12T09:00:00+08:00')).toBe('12 Nov 2024, 09:00');
    expect(percent(0.539)).toBe('54%');
  });
});

describe('riverForecastText', () => {
  it('shows now, both horizons with their ranges, and the time, in both languages', () => {
    const en = riverForecastText(mockForecast, 'en')!;
    expect(en.now).toBe('Sg. Binjai di Pekan Meru: 3.52 m now (09:00)');
    expect(en.points).toEqual([
      'likely 3.90 m (3.70 to 4.10 m) by 10:00',
      'likely 4.10 m (3.80 to 4.40 m) by 11:00',
    ]);
    expect(en.warning).toBe('Warning level: 4.00 m');
    expect(en.mayReachWarning).toBe(true);
    const ms = riverForecastText(mockForecast, 'ms')!;
    expect(ms.now).toBe('Sg. Binjai di Pekan Meru: 3.52 m sekarang (09:00)');
    expect(ms.points[0]).toBe('dijangka 3.90 m (3.70 hingga 4.10 m) menjelang 10:00');
  });

  it('writes negative ranges with a minus sign and "to"', () => {
    const neg = { ...mockForecast, points: [{ time: mockForecast.points[0].time, wl_m: -0.5, wl_m_p10: -0.8, wl_m_p90: -0.1 }] };
    expect(riverForecastText(neg, 'en')!.points[0]).toBe('likely −0.50 m (−0.80 to −0.10 m) by 10:00');
  });

  it('flags the warning level when the upper estimate of either horizon reaches it', () => {
    expect(riverForecastText({ ...mockForecast, warning_m: 4.1 }, 'en')!.mayReachWarning).toBe(true); // +2 h p90 4.40
    expect(riverForecastText({ ...mockForecast, warning_m: 3.95 }, 'en')!.mayReachWarning).toBe(true); // +1 h p90 4.10
    expect(riverForecastText({ ...mockForecast, warning_m: 5 }, 'en')!.mayReachWarning).toBe(false);
    expect(riverForecastText({ ...mockForecast, warning_m: null }, 'en')!.warning).toBeNull();
  });

  it('is null when there is no forecast', () => {
    expect(riverForecastText(null, 'en')).toBeNull();
    expect(riverForecastText({ ...mockForecast, points: [] }, 'en')).toBeNull();
  });
});
