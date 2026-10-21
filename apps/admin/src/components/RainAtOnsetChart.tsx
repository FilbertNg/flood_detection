import type { Stats } from '@floodready/shared';
import { linearScale } from '../lib/chart';
import { dateLabel } from '../lib/format';

const W = 620;
const H = 230;
const PAD = { l: 40, r: 150, t: 16, b: 70 };
/** The JPS rain guide the chart is drawn against (mm in 2 to 4 h). */
export const GUIDE_MM = 60;

/** Station rain over 2 to 4 h at each confirmed flood's onset, against the JPS 60 mm guide. */
export function RainAtOnsetChart({ rows, nameOf = (id) => id }: { rows: Stats['rain_at_onset']; nameOf?: (id: string) => string }) {
  if (rows.length === 0) return <p className="muted">No floods with rain readings in this period.</p>;
  const max = Math.max(GUIDE_MM, ...rows.map((r) => r.rain_2to4h_mm)) + 5;
  const y = linearScale([0, max], [H - PAD.b, PAD.t]);
  const slot = (W - PAD.l - PAD.r) / rows.length;
  const bar = Math.max(4, Math.min(28, slot * 0.6));
  const below = rows.filter((r) => r.rain_2to4h_mm < GUIDE_MM).length;
  const label = `Rain at flood onset: ${rows.length} floods, ${below} below the JPS ${GUIDE_MM} mm guide, highest ${Math.max(...rows.map((r) => r.rain_2to4h_mm)).toFixed(1)} mm`;

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} className="chart-svg">
        <line x1={PAD.l} x2={W - PAD.r} y1={y(0)} y2={y(0)} stroke="var(--line)" />
        <text x={PAD.l - 6} y={y(0) + 4} textAnchor="end" className="axis">0</text>
        <text x={PAD.l - 6} y={12} textAnchor="end" className="axis">mm</text>
        <line data-guide x1={PAD.l} x2={W - PAD.r} y1={y(GUIDE_MM)} y2={y(GUIDE_MM)} stroke="#607d8b" strokeDasharray="5 3" strokeWidth={1.5} />
        <text x={W - PAD.r + 4} y={y(GUIDE_MM) + 4} className="axis">JPS guide 60 mm / 2–4 h</text>
        {rows.map((r, i) => {
          const cx = PAD.l + slot * (i + 0.5);
          return (
            <g key={`${r.street_id}-${r.event_date}`}>
              <rect data-bar x={cx - bar / 2} y={y(r.rain_2to4h_mm)} width={bar} height={y(0) - y(r.rain_2to4h_mm)} fill="#0b3d91" opacity={0.75} />
              <text data-xlabel x={cx} y={H - PAD.b + 12} textAnchor="end" transform={`rotate(-30 ${cx} ${H - PAD.b + 12})`} className="axis">{`${r.event_date.slice(5)} ${nameOf(r.street_id)}`}</text>
            </g>
          );
        })}
      </svg>
      <details>
        <summary className="small">Show as table</summary>
        <table className="data">
          <caption className="sr-only">Rain at flood onset</caption>
          <thead><tr><th>Date</th><th>Street</th><th>Rain 2–4 h (mm)</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={`${r.street_id}-${r.event_date}`}><td>{dateLabel(r.event_date)}</td><td>{nameOf(r.street_id)}</td><td>{r.rain_2to4h_mm.toFixed(1)}</td></tr>)}</tbody>
        </table>
      </details>
    </figure>
  );
}
