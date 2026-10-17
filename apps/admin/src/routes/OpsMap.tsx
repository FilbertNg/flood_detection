import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { LEVEL_LABEL, LEVEL_ORDER, LEVEL_STYLE } from '@floodready/shared';
import { Credits } from '../components/Credits';
import { OpsMapView } from '../components/OpsMapView';
import { ModeRibbon, ReplayControl } from '../components/ReplayControl';
import { api } from '../lib/api';
import { hhmm } from '../lib/chart';
import { STALE_GREY } from '../lib/colours';

export function OpsMapPage() {
  const navigate = useNavigate();
  const streets = useQuery({ queryKey: ['streets'], queryFn: () => api.streets(), refetchInterval: 10_000 });
  const stations = useQuery({ queryKey: ['stations'], queryFn: () => api.stations(), refetchInterval: 30_000 });

  const props = streets.data?.features.map((f) => f.properties) ?? [];
  const atRisk = props.filter((p) => p.level === 'warning' || p.level === 'danger').length;
  const atWatch = props.filter((p) => p.level === 'watch').length;
  const stale = (stations.data ?? []).filter((s) => s.is_stale);

  return (
    <>
      <ModeRibbon />
      <div className="ops">
        <div className="ops-map">
          {streets.data ? (
            <OpsMapView streets={streets.data} stations={stations.data ?? []} onSelect={(id) => navigate(`/street/${id}`)} />
          ) : (
            <p className="pad muted">{streets.isError ? 'Could not load streets.' : 'Loading…'}</p>
          )}
          <Credits />
        </div>
        <aside className="ops-side">
          <section className="card">
            <h2>Streets</h2>
            <p className="count">{`${atRisk} at Warning or Danger`}</p>
            <p className="count">{`${atWatch} at Watch`}</p>
          </section>
          <section className="card" aria-label="Legend">
            <h2>Legend</h2>
            <ul className="legend">
              {LEVEL_ORDER.map((l) => (
                <li key={l}><span className="swatch" style={{ background: LEVEL_STYLE[l].line }} />{LEVEL_LABEL.en[l]}</li>
              ))}
              <li><span className="dot" style={{ background: '#1e88e5' }} />Rain gauge</li>
              <li><span className="dot big" style={{ background: '#0b3d91' }} />River gauge</li>
              <li><span className="dot" style={{ background: STALE_GREY }} />Stale (no recent reading)</li>
            </ul>
          </section>
          <section className="card">
            <h2>Stale stations</h2>
            {stations.data && stale.length === 0 && <p className="muted small">All stations are reporting.</p>}
            <ul className="stale-list">
              {stale.map((s) => (
                <li key={s.graph_id}>{s.name} · stale{s.latest ? ` (last reading ${hhmm(s.latest.time)})` : ''}</li>
              ))}
            </ul>
          </section>
          <section className="card">
            <h2>Demo replay</h2>
            <p className="muted small">Replays the real 12 Nov 2024 flash flood from JPS data. Everything it creates is labelled Replay.</p>
            <ReplayControl />
          </section>
        </aside>
      </div>
    </>
  );
}
