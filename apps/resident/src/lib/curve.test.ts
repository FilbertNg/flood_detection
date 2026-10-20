import { describe, expect, it } from 'vitest';
import { CURVE, curvePaths, curvePoints } from './curve';

describe('curvePoints', () => {
  it('puts one point per hour, 64 px apart, higher chance higher up', () => {
    const pts = curvePoints([100, 50, 0]);
    expect(pts.map((p) => p.x)).toEqual([32, 96, 160]);
    expect(pts[0].y).toBe(CURVE.top);
    expect(pts[2].y).toBe(CURVE.height - CURVE.bottom);
    expect(pts[1].y).toBeCloseTo((CURVE.top + CURVE.height - CURVE.bottom) / 2);
  });

  it('keeps hours without a chance as gaps', () => {
    expect(curvePoints([20, null, 40]).map((p) => p.y === null)).toEqual([false, true, false]);
  });
});

describe('curvePaths', () => {
  it('draws one smooth path through consecutive known hours', () => {
    const [path, ...rest] = curvePaths(curvePoints([10, 40, 70, 20]));
    expect(rest).toHaveLength(0);
    expect(path.startsWith('M32,')).toBe(true);
    expect(path.match(/C/g)).toHaveLength(3);
  });

  it('breaks the line at a missing hour instead of guessing', () => {
    const paths = curvePaths(curvePoints([10, 40, null, 70, 20]));
    expect(paths).toHaveLength(2);
    expect(paths[1].startsWith('M224,')).toBe(true);
  });

  it('returns nothing when no hour has a chance', () => {
    expect(curvePaths(curvePoints([null, null]))).toEqual([]);
  });
});
