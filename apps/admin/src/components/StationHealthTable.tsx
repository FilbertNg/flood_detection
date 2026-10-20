import type { StationHealth } from '@floodready/shared';
import { pct } from '../lib/format';

/** Share of the period each JPS station reported stale data, worst first. A dead gauge shows a high figure. */
export function StationHealthTable({ rows }: { rows: StationHealth[] }) {
  if (rows.length === 0) return <p className="muted">No station health data for this period.</p>;
  const sorted = [...rows].sort((a, b) => b.stale_pct - a.stale_pct);
  return (
    <table className="data" aria-label="Station health">
      <thead><tr><th scope="col">Station</th><th scope="col">Stale</th></tr></thead>
      <tbody>
        {sorted.map((r) => (
          <tr key={r.graph_id}>
            <td>{r.name} <span className="muted small">{r.graph_id}</span></td>
            <td>
              {pct(r.stale_pct)}
              {r.stale_pct >= 0.5 && <span className="tag warn"> mostly offline</span>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
