import { hhmm } from '../lib/format';

/** Small dependency-free charts for the street page. */
export function RainBars({ points }: { points: { time: string; mm: number }[] }) {
  if (!points.length) return <p className="muted">—</p>;
  const max = Math.max(5, ...points.map((p) => p.mm));
  return (
    <div className="bars" role="img" aria-label="rain forecast">
      {points.map((p) => (
        <div key={p.time} className="bar-col" title={`${hhmm(p.time)}: ${p.mm} mm`}>
          <div className="bar" style={{ height: `${(p.mm / max) * 100}%` }} />
          <span className="bar-label">{hhmm(p.time).slice(0, 2)}</span>
        </div>
      ))}
    </div>
  );
}

export function TideLine({ points }: { points: { time: string; height_m: number }[] }) {
  if (points.length < 2) return <p className="muted">—</p>;
  const w = 300, h = 60;
  const ys = points.map((p) => p.height_m);
  const lo = Math.min(...ys), hi = Math.max(...ys), span = hi - lo || 1;
  const path = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${(i / (points.length - 1)) * w},${h - ((p.height_m - lo) / span) * (h - 8) - 4}`)
    .join(' ');
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="tide" role="img" aria-label="tide">
      <path d={path} fill="none" stroke="currentColor" strokeWidth="2" />
      <text x="0" y="12" fontSize="10">{hi.toFixed(1)} m</text>
      <text x="0" y={h - 2} fontSize="10">{lo.toFixed(1)} m</text>
      <text x={w - 30} y={h - 2} fontSize="10">{hhmm(points[points.length - 1].time)}</text>
    </svg>
  );
}
