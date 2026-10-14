import { describe, expect, it } from 'vitest';
import { dayTime, hhmm, percent, windowText } from './format';

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
