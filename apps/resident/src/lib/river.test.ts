import { describe, expect, it } from 'vitest';
import { stations } from '@floodready/shared/mocks';
import { riverScale, streetRiver } from './river';

describe('streetRiver', () => {
  it('finds the first fresh river station among the street’s stations', () => {
    expect(streetRiver(stations, ['26558', 'PEKANMERU'])?.graph_id).toBe('PEKANMERU');
  });
  it('returns null for no match, a stale station, or a reply that is not a list', () => {
    expect(streetRiver(stations, ['26558'])).toBeNull();
    expect(streetRiver(stations.map((s) => ({ ...s, is_stale: true })), ['PEKANMERU'])).toBeNull();
    expect(streetRiver({ bad: true }, ['PEKANMERU'])).toBeNull();
  });
});

describe('riverScale', () => {
  const at = riverScale({ alert: 3.8, warning: 4.0, danger: 4.2 });
  it('runs from three alert-to-danger spans below alert to a little above danger', () => {
    // Scale 2.6 m (alert minus 3 × 0.4) to 4.5 m (danger plus 0.75 × 0.4).
    expect(at(3.8)).toBeCloseTo((1.2 / 1.9) * 100);
    expect(at(4.2)).toBeCloseTo((1.6 / 1.9) * 100);
    expect(at(0)).toBe(0);
    expect(at(9)).toBe(100);
  });
});
