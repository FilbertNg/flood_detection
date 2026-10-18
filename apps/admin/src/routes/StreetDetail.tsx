import { useQueries, useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router';
import { LEVEL_LABEL, LEVEL_STYLE, type RiverForecast } from '@floodready/shared';
import { Credits } from '../components/Credits';
import { StationChart } from '../components/StationChart';
import { ModeRibbon } from '../components/ReplayControl';
import { api } from '../lib/api';
import { dayTime, hhmm, shiftIso } from '../lib/chart';

const metres = (v: number) => `${v.toFixed(2)} m`;

function forecastLines(rf: RiverForecast): string[] {
  return rf.points.map((p) => `likely ${metres(p.wl_m)} (${p.wl_m_p10.toFixed(2)} to ${metres(p.wl_m_p90)}) by ${hhmm(p.time)}`);
}

export function StreetDetailPage() {
  const { id = '' } = useParams();
  const street = useQuery({ queryKey: ['street', id], queryFn: () => api.street(id), refetchInterval: 10_000 });
  const stations = useQuery({ queryKey: ['stations'], queryFn: () => api.stations(), refetchInterval: 30_000 });

  const detail = street.data;
  // A river and a rain gauge can share one graph_id; one series request per id feeds both charts.
  const ids = [...new Set(detail?.stations ?? [])];
  const to = detail?.data_time;
  const from = to ? shiftIso(to, -24) : undefined;
  const series = useQueries({
    queries: ids.map((gid) => ({
      queryKey: ['series', gid, to],
      queryFn: () => api.series(gid, from, to),
      enabled: !!to,
    })),
  });

  if (street.isLoading) return <p className="pad muted">Loading…</p>;
  if (street.isError || !detail) return <p className="pad">Could not load this street. <Link to="/" className="link">Back to the map</Link></p>;

  const style = LEVEL_STYLE[detail.level];
  const forecast = detail.river_forecast;
  const mayReach = !!forecast && forecast.warning_m !== null && forecast.points.some((p) => p.wl_m_p90 >= forecast.warning_m!);

  return (
    <>
      <ModeRibbon />
      <main className="detail">
        <Link to="/" className="back">← Map</Link>
        <header className="detail-head">
          <h1>{detail.name}</h1>
          <span className="badge badge-large" style={{ background: style.bg, color: style.fg }}>{LEVEL_LABEL.en[detail.level]}</span>
          {detail.is_replay && <span className="tag">Replay</span>}
        </header>
        <p className="muted small">Data time {dayTime(detail.data_time)} · confidence {detail.confidence} · susceptibility {detail.susceptibility}/5</p>

        <div className="detail-grid">
          <section className="card">
            <h2>Why this level</h2>
            {detail.window && <p className="window">Expected flooding window {hhmm(detail.window.start)} to {hhmm(detail.window.end)}</p>}
            {detail.reasons.length === 0 && <p className="muted">No active reasons.</p>}
            <ul className="reasons">
              {detail.reasons.map((r) => <li key={`${r.code}-${r.station}`}>{r.text.en}</li>)}
            </ul>
            {detail.flood_probability !== null && (
              <p className="ml">
                Model probability <strong>{`${Math.round(detail.flood_probability * 100)}%`}</strong>
                <span className="muted small"> (shown for information; it does not set the level)</span>
              </p>
            )}
          </section>

          {forecast && forecast.points.length > 0 && (
            <section className="card">
              <h2>River forecast</h2>
              <p>{forecast.name}: {metres(forecast.wl_now_m)} now ({hhmm(forecast.wl_now_time)})</p>
              <ul className="reasons">{forecastLines(forecast).map((l) => <li key={l}>{l}</li>)}</ul>
              {forecast.warning_m !== null && <p>Warning level: {metres(forecast.warning_m)}</p>}
              {mayReach && <p className="warn-text">The upper estimate reaches the warning level.</p>}
            </section>
          )}
        </div>

        <section className="card">
          <h2>Last 24 h at the stations that decide this street</h2>
          {ids.length === 0 && <p className="muted">No stations are mapped to this street.</p>}
          {ids.map((gid, i) => {
            const matches = (stations.data ?? []).filter((s) => s.graph_id === gid);
            const q = series[i];
            if (matches.length === 0 || !q) return <p key={gid} className="muted small">Loading {gid}…</p>;
            if (q.isError) return <p key={gid} className="muted small">Could not load readings for {matches[0].name}.</p>;
            return matches.map((station) => <StationChart key={`${gid}:${station.kind}`} station={station} series={q.data ?? []} />);
          })}
        </section>
        <p className="footer">Advisory only. JPS, MET and NADMA are the official sources.</p>
        <Credits />
      </main>
    </>
  );
}
