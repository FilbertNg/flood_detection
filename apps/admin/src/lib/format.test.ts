import { describe, expect, it } from 'vitest';
import { daysInclusive, ensureSuffix, leadMin, pct, shiftDays, SUGGESTION_SUFFIX } from './format';

describe('format', () => {
  it('formats fractions as percent', () => {
    expect(pct(0.42)).toBe('42%');
    expect(pct(0)).toBe('0%');
  });
  it('shows n/a for a missing lead time', () => {
    expect(leadMin(null)).toBe('n/a');
    expect(leadMin(54.6)).toBe('55 min');
  });
  it('appends the screening suffix only once', () => {
    expect(ensureSuffix('Check drains.')).toBe(`Check drains. ${SUGGESTION_SUFFIX}`);
    expect(ensureSuffix(`Check drains. ${SUGGESTION_SUFFIX}`)).toBe(`Check drains. ${SUGGESTION_SUFFIX}`);
  });
});

describe('date range helpers', () => {
  it('shifts a calendar date by whole days, across months and leap days', () => {
    expect(shiftDays('2024-03-01', -1)).toBe('2024-02-29');
    expect(shiftDays('2024-12-31', 1)).toBe('2025-01-01');
    expect(shiftDays('2026-10-21', -29)).toBe('2026-09-22');
  });

  it('counts the days in a range, both ends included', () => {
    expect(daysInclusive('2024-11-01', '2024-11-30')).toBe(30);
    expect(daysInclusive('2024-11-12', '2024-11-12')).toBe(1);
  });
});
