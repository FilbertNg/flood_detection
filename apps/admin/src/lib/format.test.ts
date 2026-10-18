import { describe, expect, it } from 'vitest';
import { ensureSuffix, leadMin, pct, SUGGESTION_SUFFIX } from './format';

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
