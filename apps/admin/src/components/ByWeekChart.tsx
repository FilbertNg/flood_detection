import type { Stats } from '@floodready/shared';
import { linearScale } from '../lib/chart';

const W = 620;
const H = 190;
const PAD = { l: 36, r: 12, t: 16, b: 34 };

/** Alerts and confirmed per week as grouped bars, with a table fallback. */
export function ByWeekChart({ weeks }: { weeks: Stats['by_week'] }) {
  if (weeks.length === 0) return <p className="muted">No alerts in this period.</p>;
  const totalAlerts = weeks.reduce((s, w) => s + w.alerts, 0);
  const totalConfirmed = weeks.reduce((s, w) => s + w.confirmed, 0);
  const max = Math.max(1, ...weeks.map((w) => w.alerts));
  const y = linearScale([0, max], [H - PAD.b, PAD.t]);
  const slot = (W - PAD.l - PAD.r) / weeks.length;
  const bar = Math.max(3, Math.min(20, slot * 0.4));
  const label = `Alerts per week: ${weeks.length} weeks, ${totalAlerts} alerts, ${totalConfirmed} confirmed, busiest week ${max} alerts`;
  const every = Math.ceil(weeks.length / 12);

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} className="chart-svg">
        <line x1={PAD.l} x2={W - PAD.r} y1={y(0)} y2={y(0)} stroke="var(--line)" />
        <text x={PAD.l - 6} y={y(max) + 4} textAnchor="end" className="axis">{max}</text>
        <text x={PAD.l - 6} y={y(0) + 4} textAnchor="end" className="axis">0</text>
        {weeks.map((w, i) => {
          const cx = PAD.l + slot * (i + 0.5);
          return (
            <g key={w.week}>
              <rect data-bar="alerts" x={cx - bar} y={y(w.alerts)} width={bar} height={y(0) - y(w.alerts)} fill="#1e88e5" />
              <rect data-bar="confirmed" x={cx} y={y(w.confirmed)} width={bar} height={y(0) - y(w.confirmed)} fill="#2e7d32" />
              {i % every === 0 && <text x={cx} y={H - 16} textAnchor="middle" className="axis">{w.week}</text>}
            </g>
          );
        })}
      </svg>
      <p className="small muted"><span className="key" style={{ background: '#1e88e5' }} /> alerts <span className="key" style={{ background: '#2e7d32' }} /> confirmed</p>
      <details>
        <summary className="small">Show as table</summary>
        <table className="data">
          <caption className="sr-only">Alerts per week</caption>
          <thead><tr><th>Week</th><th>Alerts</th><th>Confirmed</th></tr></thead>
          <tbody>{weeks.map((w) => <tr key={w.week}><td>{w.week}</td><td>{w.alerts}</td><td>{w.confirmed}</td></tr>)}</tbody>
        </table>
      </details>
    </figure>
  );
}
