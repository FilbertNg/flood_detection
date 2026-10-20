import { describe, expect, it } from 'vitest';
import { tideIndexAt, tideTrend, tideTurns } from './tide';

const T = (hm: string) => `2024-11-12T${hm}:00+08:00`;
const tide = [
  { time: T('08:00'), height_m: 0.4, filled: false },
  { time: T('09:00'), height_m: 0.2, filled: false },
  { time: T('10:00'), height_m: 0.9, filled: false },
  { time: T('11:00'), height_m: 1.3, filled: false },
  { time: T('12:00'), height_m: 1.1, filled: false },
  { time: T('13:00'), height_m: 0.6, filled: false },
];

describe('tideIndexAt', () => {
  it('places the data time between the hourly points', () => {
    expect(tideIndexAt(tide, T('09:00'))).toBe(1);
    expect(tideIndexAt(tide, T('09:30'))).toBeCloseTo(1.5);
  });

  it('clamps to the series (data time before the first or after the last hour)', () => {
    expect(tideIndexAt(tide, T('07:15'))).toBe(0);
    expect(tideIndexAt(tide, T('20:00'))).toBe(tide.length - 1);
  });
});

describe('tideTurns', () => {
  it('finds the next high and the next low after now', () => {
    expect(tideTurns(tide, 0.5)).toEqual({ high: 3, low: 1 });
    expect(tideTurns(tide, 2)).toEqual({ high: 3, low: null });
  });
});

describe('tideTrend', () => {
  it('says whether the water is rising or falling at now', () => {
    expect(tideTrend(tide, 1.5)).toBe('rising');
    expect(tideTrend(tide, 4.2)).toBe('falling');
    // At the last point the last stretch decides.
    expect(tideTrend(tide, 5)).toBe('falling');
  });
});
