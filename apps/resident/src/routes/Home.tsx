import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { LEVEL_LABEL, type Lang, type StreetProperties } from '@floodready/shared';
import { BackButton } from '../components/BackButton';
import { Credits } from '../components/Credits';
import { Icon } from '../components/Icons';
import { LangSwitch } from '../components/LangSwitch';
import { StatusLine } from '../components/StatusLine';
import { StreetMap } from '../components/StreetMap';
import { api } from '../lib/api';
import { t, tf } from '../lib/i18n';

const SOLID = { normal: '#2e7d32', watch: '#b26a00', warning: '#e65100', danger: '#c62828' } as const;

/** "1 street", "2 streets" (Malay has one form). */
const streetCount = (lang: Lang, n: number) => tf(lang, n === 1 ? 'streetsOne' : 'streetsMany', { n });

interface Props {
  lang: Lang;
  mine: string[];
  onLang?: (lang: Lang) => void;
}

/**
 * Flood map (/map): for looking at other streets (my own street is the home page). A phone has no
 * hover, so zooming in on a street (or tapping one, which zooms in) shows it in a popup pointing at the
 * street, with its level and "View", which opens that street's page.
 */
export function HomePage({ lang, mine, onLang }: Props) {
  const { data, isLoading, isError } = useQuery({ queryKey: ['streets'], queryFn: () => api.streets(), refetchInterval: 10_000 });
  const [focused, setFocused] = useState<string | null>(null);
  // Full-screen map: the map covers the whole screen (CSS, so it also works on iPhone, which has no
  // fullscreen API for pages); the same button or Escape closes it.
  const [full, setFull] = useState(false);
  // A count panel's street list, opened as a sheet over the darkened page.
  const [list, setList] = useState<'risk' | 'watch' | null>(null);
  // Escape closes the sheet first, then the full-screen map.
  useEffect(() => {
    if (!full && !list) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (list) setList(null);
      else setFull(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [full, list]);

  const header = (
    <>
      <header className="top map-head">
        <BackButton lang={lang} />
        <h1>{t(lang, 'navMap')}</h1>
        {onLang && <LangSwitch lang={lang} onChange={onLang} />}
      </header>
    </>
  );

  if (isLoading) return <>{header}<p className="pad">{t(lang, 'loading')}</p></>;
  if (isError || !data) return <>{header}<p className="pad">{t(lang, 'error')}</p></>;

  const props = data.features.map((f) => f.properties);
  const byId = (id: string | null) => (id ? props.find((p) => p.street_id === id) ?? null : null);
  const risky = props.filter((p) => p.level === 'warning' || p.level === 'danger');
  const watched = props.filter((p) => p.level === 'watch');
  const lists = {
    risk: { title: t(lang, 'listRiskTitle'), streets: risky },
    watch: { title: t(lang, 'listWatchTitle'), streets: watched },
  };
  const followed = mine.map((id) => byId(id)).filter((p): p is StreetProperties => !!p);
  const alerting = followed.filter((p) => p.level === 'warning' || p.level === 'danger');
  const watching = followed.filter((p) => p.level === 'watch');

  const focus = byId(focused);

  return (
    <div className="home">
      {header}
      {alerting.length > 0 && (
        <Link to={`/street/${alerting[0].street_id}`} className="alert-banner">
          ⚠ {t(lang, 'activeAlert')}: {alerting[0].name}
        </Link>
      )}
      {alerting.length === 0 && watching.length > 0 && (
        <Link to={`/street/${watching[0].street_id}`} className="alert-banner watch">
          {t(lang, 'watchAlert')}: {watching[0].name}
        </Link>
      )}

      <div className={full ? 'map-wrap is-full' : 'map-wrap'}>
        {/* Live or replay, floating on the map it describes (also in full screen). */}
        <div className="map-chip"><StatusLine lang={lang} /></div>
        <StreetMap data={data} mine={mine} focused={focused} onFocus={setFocused}>
          {focus && (
            <section className="focus-card" aria-label={focus.name}>
              <strong className="focus-name">{focus.name}</strong>
              <div className="focus-row">
                <span className="level-pill" style={{ ['--lvl' as string]: SOLID[focus.level] }}>
                  <i aria-hidden="true" />{LEVEL_LABEL[lang][focus.level]}
                </span>
                <Link to={`/street/${encodeURIComponent(focus.street_id)}`} className="primary focus-view">{t(lang, 'mapView')}<span aria-hidden="true"> ›</span></Link>
              </div>
            </section>
          )}
        </StreetMap>
        {!focus && <p className="map-hint">{t(lang, 'mapZoomHint')}</p>}
        <button type="button" className="map-full-btn" onClick={() => setFull((f) => !f)} aria-label={t(lang, full ? 'mapExitFull' : 'mapFull')}>
          <Icon name={full ? 'collapse' : 'expand'} />
        </button>
      </div>

      <section className="map-foot">
        <div className="summary-pair">
          <button type="button" className="summary-box" data-kind="risk" aria-haspopup="dialog" aria-label={`${risky.length} ${t(lang, 'streetsAtRisk')}`} onClick={() => setList('risk')}>
            <span>{t(lang, 'boxRisk')}</span><strong>{streetCount(lang, risky.length)}</strong>
          </button>
          <button type="button" className="summary-box" data-kind="watch" aria-haspopup="dialog" aria-label={`${watched.length} ${t(lang, 'streetsWatchBox')}`} onClick={() => setList('watch')}>
            <span>{t(lang, 'boxWatch')}</span><strong>{streetCount(lang, watched.length)}</strong>
          </button>
        </div>
        {alerting.length === 0 && <Link to="/report" className="primary report-link">{t(lang, 'reportLink')}</Link>}
        <Credits lang={lang} />
      </section>

      {list && (
        <div className="sheet-backdrop" onClick={(e) => { if (e.target === e.currentTarget) setList(null); }}>
          <div className="pick-sheet list-sheet" role="dialog" aria-modal="true" aria-label={lists[list].title} data-kind={list}>
            <div className="pad">
              <div className="row">
                <h1>{lists[list].title}</h1>
                <button type="button" className="sheet-close" onClick={() => setList(null)}>{t(lang, 'close')}</button>
              </div>
              {lists[list].streets.length === 0 ? (
                <p className="muted">{t(lang, 'listEmpty')}</p>
              ) : (
                <ul className="level-list">
                  {lists[list].streets.map((p) => (
                    <li key={p.street_id}>
                      <Link to={`/street/${encodeURIComponent(p.street_id)}`}>
                        <span>{p.name}</span>
                        <span className="level-pill" style={{ ['--lvl' as string]: SOLID[p.level] }}><i aria-hidden="true" />{LEVEL_LABEL[lang][p.level]}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

