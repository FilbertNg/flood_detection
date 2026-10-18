import { useMemo, useState } from 'react';
import type { StreetStat } from '@floodready/shared';

type Key = 'name' | 'alerts' | 'confirmed' | 'floods';
const COLS: { key: Key; label: string }[] = [
  { key: 'name', label: 'Street' },
  { key: 'alerts', label: 'Alerts' },
  { key: 'confirmed', label: 'Confirmed' },
  { key: 'floods', label: 'Floods' },
];

/** Per-street counts; click a column header to sort (numbers high first, names A to Z). */
export function ByStreetTable({ rows, label = 'Alerts by street' }: { rows: StreetStat[]; label?: string }) {
  const [sort, setSort] = useState<{ key: Key; dir: 'asc' | 'desc' } | null>(null);
  const sorted = useMemo(() => {
    if (!sort) return rows;
    const sign = sort.dir === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) =>
      sort.key === 'name' ? sign * a.name.localeCompare(b.name) : sign * (a[sort.key] - b[sort.key]),
    );
  }, [rows, sort]);

  if (rows.length === 0) return <p className="muted">No streets with alerts or floods in this period.</p>;

  const toggle = (key: Key) =>
    setSort((s) => (s?.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: key === 'name' ? 'asc' : 'desc' }));

  return (
    <table className="data" aria-label={label}>
      <thead>
        <tr>
          {COLS.map((c) => (
            <th key={c.key} scope="col" aria-sort={sort?.key === c.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
              <button type="button" className="sort" onClick={() => toggle(c.key)}>
                {c.label}{sort?.key === c.key ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : ''}
              </button>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sorted.map((r) => (
          <tr key={r.street_id}>
            <td>{r.name}</td><td>{r.alerts}</td><td>{r.confirmed}</td><td>{r.floods}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
