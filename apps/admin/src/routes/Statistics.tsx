import { useQuery } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';
import { ByStreetTable } from '../components/ByStreetTable';
import { ByWeekChart } from '../components/ByWeekChart';
import { Insights } from '../components/Insights';
import { KpiTiles } from '../components/KpiTiles';
import { OutcomeChart, StationHealthChart, TopStreetsChart } from '../components/StatsCharts';
import { GUIDE_MM, RainAtOnsetChart } from '../components/RainAtOnsetChart';
import { StationHealthTable } from '../components/StationHealthTable';
import { StatIcon, type StatIconName } from '../components/StatIcons';
import { api } from '../lib/api';
import { daysInclusive, shiftDays, todayIso } from '../lib/format';
import { useStreetNames } from '../lib/useStreetNames';
import { InlineLoading } from '../components/LogoFill';

/** Start of the backfilled JPS history. */
const DEFAULT_FROM = '2024-01-01';

/** A chart card: icon, title, and a one-line takeaway read from the data. */
function ChartCard({ icon, title, note, children }: { icon: StatIconName; title: string; note?: string; children: ReactNode }) {
  return (
    <section className="card chart-card">
      <header className="chart-head">
        <span className="chart-icon"><StatIcon name={icon} /></span>
        <div>
          <h2>{title}</h2>
          {note && <p className="chart-note">{note}</p>}
        </div>
      </header>
      {children}
    </section>
  );
}

/** Quick periods for the picker; the flood month is the demo period (the 12 Nov 2024 flash flood). */
function presets(today: string) {
  return [
    { label: 'All', from: DEFAULT_FROM, to: today },
    { label: 'This year', from: `${today.slice(0, 4)}-01-01`, to: today },
    { label: '90 days', from: shiftDays(today, -89), to: today },
    { label: '30 days', from: shiftDays(today, -29), to: today },
    { label: 'Nov 2024 flood', from: '2024-11-01', to: '2024-11-30' },
  ];
}

export function StatisticsPage() {
  const [from, setFrom] = useState(DEFAULT_FROM);
  const [to, setTo] = useState(todayIso());
  // Clicking a date field means a custom range: no quick period stays selected until one is picked again.
  const [custom, setCustom] = useState(false);
  const quick = presets(todayIso());
  const active = custom ? null : quick.find((p) => p.from === from && p.to === to)?.label ?? null;
  const valid = from !== '' && to !== '' && from <= to;
  const q = useQuery({ queryKey: ['stats', from, to], queryFn: () => api.stats(from, to), enabled: valid });
  const s = q.data;
  const streetName = useStreetNames();
  const nameOf = (id: string) => s?.by_street.find((b) => b.street_id === id)?.name ?? streetName(id);

  return (
    <main className="page">
      <h1>Statistics</h1>
      {/* Period on one line: quick periods, then the exact From → To range and its length. */}
      <div className="period-bar">
        <div className="period-quick" role="group" aria-label="Period">
          {quick.map((p) => (
            <button key={p.label} type="button" aria-pressed={active === p.label} onClick={() => { setFrom(p.from); setTo(p.to); setCustom(false); }}>{p.label}</button>
          ))}
        </div>
        <div className="period-range">
          <StatIcon name="calendar" />
          <label>
            <span className="sr-only">From</span>
            <input type="date" value={from} max={to} onFocus={() => setCustom(true)} onChange={(e) => { setFrom(e.target.value); setCustom(true); }} />
          </label>
          <span className="period-arrow" aria-hidden="true">→</span>
          <label>
            <span className="sr-only">To</span>
            <input type="date" value={to} min={from} onFocus={() => setCustom(true)} onChange={(e) => { setTo(e.target.value); setCustom(true); }} />
          </label>
          {valid && <span className="period-days">{`${daysInclusive(from, to)} days`}</span>}
        </div>
      </div>
      {!valid && <p role="alert" className="error">Choose a start date on or before the end date.</p>}
      {valid && q.isLoading && <InlineLoading text="Loading statistics…" />}
      {q.isError && <p role="alert" className="error">Could not load statistics.</p>}
      {s && (
        <>
          <KpiTiles kpis={s.kpis} />
          <p className="muted small">
            Outcomes from news: {s.sources.outcomes_from_news} · from residents: {s.sources.outcomes_from_residents}.
            {' '}Replay and demo data are excluded.
          </p>
          <Insights stats={s} />
          <ChartCard icon="check" title="How alerts ended" note={s.kpis.alerts > 0 ? `${s.kpis.confirmed} of ${s.kpis.alerts} alerts confirmed as floods` : undefined}>
            <OutcomeChart kpis={s.kpis} />
          </ChartCard>
          <ChartCard icon="bars" title="Alerts by week" note={s.by_week.length > 0 ? `${s.by_week.reduce((n, w) => n + w.alerts, 0)} alerts over ${s.by_week.length} weeks` : undefined}>
            <ByWeekChart weeks={s.by_week} />
          </ChartCard>
          <div className="stats-grid">
            <ChartCard icon="pin" title="Streets with the most alerts" note={s.by_street.some((r) => r.alerts > 0) ? 'Top 10, with confirmed floods beside each' : undefined}>
              <TopStreetsChart rows={s.by_street} />
            </ChartCard>
            <ChartCard icon="gauge" title="Station health" note={s.station_health.length > 0 ? `${s.station_health.filter((r) => r.stale_pct >= 0.5).length} of ${s.station_health.length} stations mostly offline (red)` : undefined}>
              <StationHealthChart rows={s.station_health} />
            </ChartCard>
          </div>
          <ChartCard icon="drop" title="Rain at flood onset" note={s.rain_at_onset.length > 0 ? `${s.rain_at_onset.filter((r) => r.rain_2to4h_mm < GUIDE_MM).length} of ${s.rain_at_onset.length} floods began below the JPS ${GUIDE_MM} mm guide` : undefined}>
            <RainAtOnsetChart rows={s.rain_at_onset} nameOf={nameOf} />
          </ChartCard>
          <ChartCard icon="table" title="By street">
            <ByStreetTable rows={s.by_street} />
          </ChartCard>
          <section className="card">
            <details>
              <summary className="small">Station health as table</summary>
              <StationHealthTable rows={s.station_health} />
            </details>
          </section>
        </>
      )}
    </main>
  );
}
