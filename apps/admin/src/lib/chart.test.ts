import { describe, expect, it } from 'vitest';
import { linearScale, rollingSum, shiftIso } from './chart';

describe('chart helpers', () => {
  it('linearScale maps the domain onto the range', () => {
    const s = linearScale([0, 10], [100, 0]);
    expect(s(0)).toBe(100);
    expect(s(10)).toBe(0);
    expect(s(5)).toBe(50);
  });

  it('linearScale of a flat domain does not divide by zero', () => {
    expect(Number.isFinite(linearScale([3, 3], [0, 10])(3))).toBe(true);
  });

  it('rollingSum adds the last n values, treating gaps as missing', () => {
    expect(rollingSum([1, 2, null, 4, 5], 4)).toEqual([1, 3, 3, 7, 11]);
  });

  it('shiftIso moves a +08:00 timestamp and keeps the offset', () => {
    expect(shiftIso('2024-11-12T09:00:00+08:00', -24)).toBe('2024-11-11T09:00:00+08:00');
    expect(shiftIso('2024-11-12T01:30:00+08:00', -3)).toBe('2024-11-11T22:30:00+08:00');
  });
});
