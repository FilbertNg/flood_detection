import { describe, expect, it } from 'vitest';
import { orderStreets } from './order';

describe('orderStreets', () => {
  const levels = { a: 'normal', b: 'warning', c: 'danger', d: 'watch', e: 'warning' } as const;

  it('puts Danger first, then Warning, Watch and Normal', () => {
    expect(orderStreets(['a', 'b', 'c', 'd'], levels)).toEqual(['c', 'b', 'd', 'a']);
  });

  it('keeps the resident’s saved order within a level', () => {
    expect(orderStreets(['e', 'a', 'b'], levels)).toEqual(['e', 'b', 'a']);
    expect(orderStreets(['b', 'e'], levels)).toEqual(['b', 'e']);
  });

  it('keeps streets with no known level, after the others, in saved order', () => {
    expect(orderStreets(['x', 'a', 'y', 'c'], levels)).toEqual(['c', 'a', 'x', 'y']);
  });
});
