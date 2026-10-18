import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { ByStreetTable } from '../components/ByStreetTable';
import { EvidenceList } from '../components/SuggestionCard';
import { KpiTiles } from '../components/KpiTiles';
import { StationHealthTable } from '../components/StationHealthTable';
import { api } from '../lib/api';
import { dateLabel, monthLabel, ensureSuffix, todayIso } from '../lib/format';

export function ReportPage() {
  const [month, setMonth] = useState(todayIso().slice(0, 7));
  const q = useQuery({ queryKey: ['report', month], queryFn: () => api.report(month), enabled: month !== '' });
  const r = q.data;

  return (
    <main className="page report">
      <div className="no-print filters">
        <label>Month <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} /></label>
        <button type="button" className="primary fit" onClick={() => window.print()}>Print / Save as PDF</button>
      </div>
      <h1>Flood-Ready Township report, {monthLabel(month)}</h1>
      {q.isLoading && <p className="muted">Loading…</p>}
      {q.isError && <p role="alert" className="error">Could not load the report.</p>}
      {r && (
        <>
          <section><h2>Summary</h2><KpiTiles kpis={r.summary} /></section>
          <section>
            <h2>Events</h2>
            {r.events.length === 0 ? <p className="muted">No events recorded this month.</p> : (
              <table className="data">
                <thead><tr><th>Date</th><th>Place</th><th>Source</th></tr></thead>
                <tbody>
                  {r.events.map((e) => (
                    <tr key={e.event_id}>
                      <td>{dateLabel(e.date)}</td>
                      <td>{e.place}</td>
                      <td>{e.source_url ? <a href={e.source_url} className="link">{e.source_type}</a> : e.source_type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
          <section><h2>Top streets</h2><ByStreetTable rows={r.top_streets} label="Top streets" /></section>
          <section>
            <h2>Suggestions</h2>
            {r.suggestions.length === 0 ? <p className="muted">No suggestions for this month.</p> : r.suggestions.map((s) => (
              <div key={s.id} className="sug-print">
                <strong>{s.street_name}</strong> <span className="small muted">({s.priority} priority, {s.status})</span>
                <p>{ensureSuffix(s.text)}</p>
                <EvidenceList s={s} />
              </div>
            ))}
          </section>
          <section><h2>Data health</h2><StationHealthTable rows={r.data_health} /></section>
          <p className="small muted">Replay and demo data are excluded. Advisory only. JPS, MET and NADMA are the official sources.</p>
        </>
      )}
    </main>
  );
}
