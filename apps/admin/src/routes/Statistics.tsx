import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { ByStreetTable } from '../components/ByStreetTable';
import { ByWeekChart } from '../components/ByWeekChart';
import { KpiTiles } from '../components/KpiTiles';
import { RainAtOnsetChart } from '../components/RainAtOnsetChart';
import { StationHealthTable } from '../components/StationHealthTable';
import { api } from '../lib/api';
import { todayIso } from '../lib/format';

/** Start of the backfilled JPS history. */
const DEFAULT_FROM = '2024-01-01';

export function StatisticsPage() {
  const [from, setFrom] = useState(DEFAULT_FROM);
  const [to, setTo] = useState(todayIso());
  const valid = from !== '' && to !== '' && from <= to;
  const q = useQuery({ queryKey: ['stats', from, to], queryFn: () => api.stats(from, to), enabled: valid });
  const s = q.data;

  return (
    <main className="page">
      <h1>Statistics</h1>
      <div className="filters">
        <label>From <input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} /></label>
        <label>To <input type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} /></label>
      </div>
      {!valid && <p role="alert" className="error">Choose a start date on or before the end date.</p>}
      {valid && q.isLoading && <p className="muted">Loading…</p>}
      {q.isError && <p role="alert" className="error">Could not load statistics.</p>}
      {s && (
        <>
          <KpiTiles kpis={s.kpis} />
          <p className="muted small">
            Outcomes from news: {s.sources.outcomes_from_news} · from residents: {s.sources.outcomes_from_residents}.
            {' '}Replay and demo data are excluded.
          </p>
          <section className="card"><h2>Alerts by week</h2><ByWeekChart weeks={s.by_week} /></section>
          <section className="card"><h2>By street</h2><ByStreetTable rows={s.by_street} /></section>
          <section className="card"><h2>Rain at flood onset</h2><RainAtOnsetChart rows={s.rain_at_onset} /></section>
          <section className="card"><h2>Station health</h2><StationHealthTable rows={s.station_health} /></section>
        </>
      )}
    </main>
  );
}
