/** Geometry for the "rain in the next 12 hours" curve: one column per hour, chance 0 to 100 %. */
export const CURVE = { col: 64, height: 92, top: 26, bottom: 14 };

export interface CurvePoint {
  x: number;
  /** null when Open-Meteo has no chance for this hour: the line breaks there. */
  y: number | null;
  chance: number | null;
}

export function curvePoints(chances: (number | null)[]): CurvePoint[] {
  const span = CURVE.height - CURVE.top - CURVE.bottom;
  return chances.map((c, i) => ({
    x: i * CURVE.col + CURVE.col / 2,
    y: c === null ? null : CURVE.top + (1 - c / 100) * span,
    chance: c,
  }));
}

const r = (v: number) => Math.round(v * 10) / 10;

export interface CurveRun {
  /** The smooth line. */
  d: string;
  /** x of the first and last point, for closing the soft area fill under the line. */
  x0: number;
  x1: number;
}

/** Smooth Catmull-Rom paths through each run of known hours; a missing hour starts a new path. */
export function curvePaths(points: CurvePoint[]): string[] {
  return curveRuns(points).map((run) => run.d);
}

export function curveRuns(points: CurvePoint[]): CurveRun[] {
  const runs: { x: number; y: number }[][] = [];
  let run: { x: number; y: number }[] = [];
  for (const p of points) {
    if (p.y === null) {
      if (run.length) runs.push(run);
      run = [];
    } else run.push({ x: p.x, y: p.y });
  }
  if (run.length) runs.push(run);

  return runs.map((pts) => {
    let d = `M${r(pts[0].x)},${r(pts[0].y)}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] ?? pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] ?? p2;
      d += ` C${r(p1.x + (p2.x - p0.x) / 6)},${r(p1.y + (p2.y - p0.y) / 6)} ${r(p2.x - (p3.x - p1.x) / 6)},${r(p2.y - (p3.y - p1.y) / 6)} ${r(p2.x)},${r(p2.y)}`;
    }
    return { d, x0: pts[0].x, x1: pts[pts.length - 1].x };
  });
}

/** Stroke colour by chance: blue, amber from 40 %, orange from 70 %. */
export function chanceColor(chance: number): string {
  if (chance >= 70) return '#ff9f43';
  if (chance >= 40) return '#ffd166';
  return '#a8dcff';
}
