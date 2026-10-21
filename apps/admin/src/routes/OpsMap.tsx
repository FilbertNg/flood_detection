import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router';
import { LEVEL_LABEL, LEVEL_ORDER, LEVEL_STYLE } from '@floodready/shared';
import { Credits } from '../components/Credits';
import { OpsMapView } from '../components/OpsMapView';
import { ModeChip, ReplayControl } from '../components/ReplayControl';
import { api } from '../lib/api';
import { hhmm } from '../lib/chart';
import { STALE_GREY } from '../lib/colours';

export function OpsMapPage() {
  const [focused, setFocused] = useState<string | null>(null);
  // Which count panels have their street list dropped down (each on its own).
  const [open, setOpen] = useState({ risk: false, watch: false });
  const streets = useQuery({ queryKey: ['streets'], queryFn: () => api.streets(), refetchInterval: 10_000 });
  const stations = useQuery({ queryKey: ['stations'], queryFn: () => api.stations(), refetchInterval: 30_000 });

  const props = streets.data?.features.map((f) => f.properties) ?? [];
  const atRisk = props.filter((p) => p.level === 'warning' || p.level === 'danger').length;
  const atWatch = props.filter((p) => p.level === 'watch').length;
  const alerting = props.filter((p) => p.level === 'warning' || p.level === 'danger');
  const watching = props.filter((p) => p.level === 'watch');
  const lists = {
    risk: { title: 'Streets at Warning or Danger', streets: alerting },
    watch: { title: 'Streets at Watch', streets: watching },
  } as const;
  const toggle = (kind: 'risk' | 'watch') => setOpen((o) => ({ ...o, [kind]: !o[kind] }));
  const stale = (stations.data ?? []).filter((s) => s.is_stale);
  const focus = focused ? props.find((p) => p.street_id === focused) ?? null : null;

  return (
    <>
      <div className="ops">
        <div className="ops-map">
          {/* Live or replay, floating on the map it describes. */}
          <div className="map-chip"><ModeChip /></div>
          {streets.data ? (
            <OpsMapView streets={streets.data} stations={stations.data ?? []} focused={focused} onFocus={setFocused}>
              {focus && (
                <section className="focus-card" aria-label={focus.name}>
                  <strong className="focus-name">{focus.name}</strong>
                  <div className="focus-row">
                    <span className="level-pill"><i aria-hidden="true" style={{ background: LEVEL_STYLE[focus.level].line }} />{LEVEL_LABEL.en[focus.level]}</span>
                    <Link to={`/street/${encodeURIComponent(focus.street_id)}`} className="primary focus-view">View<span aria-hidden="true"> ›</span></Link>
                  </div>
                </section>
              )}
            </OpsMapView>
          ) : (
            <p className="pad muted">{streets.isError ? 'Could not load streets.' : 'Loading…'}</p>
          )}
          <Credits />
        </div>
        <aside className="ops-side">
          <section className="card">
            <h2>Streets</h2>
            {/* Each count is a full-width button with its own drop-down list right under it. */}
            <div className="count-stack">
              {(['risk', 'watch'] as const).map((kind) => (
                <div key={kind} className="count-item">
                  <button type="button" className="count-box" data-kind={kind} aria-expanded={open[kind]} aria-controls={`count-list-${kind}`} onClick={() => toggle(kind)}>
                    <strong>{kind === 'risk' ? atRisk : atWatch}</strong><span>{kind === 'risk' ? 'at Warning or Danger' : 'at Watch'}</span>
                  </button>
                  {open[kind] && (
                    <div id={`count-list-${kind}`} className="count-list" data-kind={kind}>
                      {lists[kind].streets.length === 0 ? (
                        <p className="muted small">None.</p>
                      ) : (
                        <ul className="street-list" aria-label={lists[kind].title}>
                          {lists[kind].streets.map((p) => (
                            <li key={p.street_id}>
                              <Link to={`/street/${p.street_id}`} className="link">{p.name}</Link>
                              <span className="level-pill"><i aria-hidden="true" style={{ background: LEVEL_STYLE[p.level].line }} />{LEVEL_LABEL.en[p.level]}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
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
