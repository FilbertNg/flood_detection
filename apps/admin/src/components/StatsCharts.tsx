import type { Kpis, StationHealth, StreetStat } from '@floodready/shared';
import { pct } from '../lib/format';

/** Shared colours: green = confirmed flood, slate = residents said no, ochre = no answer yet. */
const OUTCOME = [
  { key: 'confirmed', label: 'confirmed', color: '#2e7d32' },
  { key: 'not_confirmed', label: 'not confirmed', color: '#546e7a' },
  { key: 'unverified', label: 'unverified', color: '#9a7b2f' },
] as const;

/** One stacked bar: how every alert in the period ended. Unverified is no answer, not a false alarm. */
export function OutcomeChart({ kpis }: { kpis: Kpis }) {
  if (kpis.alerts === 0) return <p className="muted">No alerts to break down in this period.</p>;
  const total = kpis.confirmed + kpis.not_confirmed + kpis.unverified || 1;
  let x = 0;
  const label = `${kpis.alerts} alerts: ${kpis.confirmed} confirmed, ${kpis.not_confirmed} not confirmed, ${kpis.unverified} unverified`;
  return (
    <figure className="chart">
      <svg viewBox="0 0 100 10" preserveAspectRatio="none" role="img" aria-label={label} className="stack">
        {OUTCOME.map((o) => {
          const w = (kpis[o.key] / total) * 100;
          const rect = <rect key={o.key} data-seg={o.key} x={x} y={0} width={w} height={10} fill={o.color} />;
          x += w;
          return rect;
        })}
      </svg>
      <ul className="chart-key">
        {OUTCOME.map((o) => (
          <li key={o.key}>
            <span className="key" style={{ background: o.color }} />
            {o.label} <strong>{kpis[o.key]}</strong> <span className="muted">({pct(kpis[o.key] / total)})</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}

/** Horizontal bars, label on the left, value at the end; used by the two ranked charts below. */
function RankBars({ items, label, max, unit }: {
  items: { id: string; name: string; value: number; color: string; extra?: string; offline?: boolean }[];
  label: string;
  max: number;
  unit: (v: number) => string;
}) {
  return (
    <div className="rank" role="img" aria-label={label}>
      {items.map((it) => (
        <div key={it.id} className="rank-row" data-offline={it.offline ? it.id : undefined}>
          <span className="rank-name" data-name>{it.name}</span>
          <span className="rank-track">
            <span className="rank-bar" style={{ width: `${Math.max(1, (it.value / (max || 1)) * 100)}%`, background: it.color }} />
          </span>
          <span className="rank-value">{unit(it.value)}{it.extra ? <span className="muted"> {it.extra}</span> : null}</span>
        </div>
      ))}
    </div>
  );
}

/** The ten streets with the most alerts; confirmed count shown beside each bar. */
export function TopStreetsChart({ rows }: { rows: StreetStat[] }) {
  const top = rows.filter((r) => r.alerts > 0).sort((a, b) => b.alerts - a.alerts).slice(0, 10);
  if (top.length === 0) return <p className="muted">No streets with alerts in this period.</p>;
  const label = `Top ${top.length} streets by alerts, highest ${top[0].name} with ${top[0].alerts}`;
  return (
    <RankBars
      label={label}
      max={top[0].alerts}
      unit={String}
      items={top.map((r) => ({ id: r.street_id, name: r.name, value: r.alerts, color: '#121212', extra: `· ${r.confirmed} confirmed` }))}
    />
  );
}

/** Share of the period each station reported stale data; half or more is mostly offline. */
export function StationHealthChart({ rows }: { rows: StationHealth[] }) {
  if (rows.length === 0) return <p className="muted">No station health data for this period.</p>;
  const sorted = [...rows].sort((a, b) => b.stale_pct - a.stale_pct);
  const offline = sorted.filter((r) => r.stale_pct >= 0.5).length;
  return (
    <RankBars
      label={`Station health: ${sorted.length} stations, ${offline} mostly offline`}
      max={1}
      unit={pct}
      items={sorted.map((r) => ({
        id: r.graph_id,
        name: r.name,
        value: r.stale_pct,
        color: r.stale_pct >= 0.5 ? '#b71c1c' : '#546e7a',
        offline: r.stale_pct >= 0.5,
      }))}
    />
  );
}
