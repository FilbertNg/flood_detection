import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useId, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { LEVEL_LABEL, type Lang, type StreetProperties } from '@floodready/shared';
import { Credits } from '../components/Credits';
import { Icon } from '../components/Icons';
import { LangSwitch } from '../components/LangSwitch';
import { LevelBadge } from '../components/LevelBadge';
import { StatusLine } from '../components/StatusLine';
import { StreetMap } from '../components/StreetMap';
import { api } from '../lib/api';
import { currentPosition, nearestStreet } from '../lib/geo';
import { t } from '../lib/i18n';
import { PickStreetsPage } from './PickStreets';

/** Further than this from every BBR street means the phone is outside the township. */
const OUTSIDE_M = 1000;

const SOLID = { normal: '#2e7d32', watch: '#b26a00', warning: '#e65100', danger: '#c62828' } as const;

interface Props {
  lang: Lang;
  mine: string[];
  deviceId: string;
  onSave: (ids: string[]) => void;
  onLang?: (lang: Lang) => void;
}

/**
 * Flood map (/map): the township map with a floating "My location" card. The card shows my street;
 * "Use my location" finds the nearest street on the phone; "Choose another" opens the street picker as
 * a sheet; tapping a street line puts it in the card. "Set as my street" replaces my street (the app
 * keeps one) and opens it.
 */
export function HomePage({ lang, mine, deviceId, onSave, onLang }: Props) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const cardTitle = useId();
  const { data, isLoading, isError } = useQuery({ queryKey: ['streets'], queryFn: () => api.streets(), refetchInterval: 10_000 });
  const [picked, setPicked] = useState<string | null>(null);
  const [locate, setLocate] = useState<'idle' | 'busy' | 'outside' | 'failed'>('idle');
  const [sheet, setSheet] = useState(false);

  useEffect(() => {
    if (!sheet) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setSheet(false); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [sheet]);

  const header = (
    <>
      <header className="top map-head">
        <Link to="/" className="map-back">← {t(lang, 'back')}</Link>
        <h1>{t(lang, 'navMap')}</h1>
        {onLang && <LangSwitch lang={lang} onChange={onLang} />}
      </header>
      <StatusLine lang={lang} />
    </>
  );

  if (isLoading) return <>{header}<p className="pad">{t(lang, 'loading')}</p></>;
  if (isError || !data) return <>{header}<p className="pad">{t(lang, 'error')}</p></>;

  const props = data.features.map((f) => f.properties);
  const byId = (id: string | null) => (id ? props.find((p) => p.street_id === id) ?? null : null);
  const atRisk = props.filter((p) => p.level === 'warning' || p.level === 'danger').length;
  const atWatch = props.filter((p) => p.level === 'watch').length;
  const followed = mine.map((id) => byId(id)).filter((p): p is StreetProperties => !!p);
  const alerting = followed.filter((p) => p.level === 'warning' || p.level === 'danger');
  const watching = followed.filter((p) => p.level === 'watch');

  const current = byId(picked) ?? followed[0] ?? null;
  const isMine = !!current && current.street_id === mine[0];

  const choose = (street: StreetProperties) => {
    if (street.street_id !== mine[0]) onSave([street.street_id]);
    navigate(`/street/${encodeURIComponent(street.street_id)}`);
  };

  const locateMe = async () => {
    setLocate('busy');
    try {
      const [place, col] = await Promise.all([currentPosition(), client.fetchQuery({ queryKey: ['streets'], queryFn: () => api.streets() })]);
      const hit = nearestStreet(place, col.features);
      if (!hit) setLocate('failed');
      else if (hit.distanceM > OUTSIDE_M) setLocate('outside');
      else {
        setPicked(hit.street.street_id);
        setLocate('idle');
      }
    } catch {
      setLocate('failed');
    }
  };

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

      <div className="map-wrap">
        <StreetMap data={data} mine={mine} onSelect={(id) => { setPicked(id); setLocate('idle'); }} />

        <section className="loc-card" aria-labelledby={cardTitle}>
          <small id={cardTitle}>{t(lang, 'myLocation')}</small>
          <div className="loc-row">
            <span className="loc-pin" aria-hidden="true"><Icon name="pin" /></span>
            <strong>{current ? current.name : t(lang, 'noStreetYet')}</strong>
            {current && (
              <span className="level-pill loc-level" style={{ ['--lvl' as string]: SOLID[current.level] }}>
                <i aria-hidden="true" />{LEVEL_LABEL[lang][current.level]}
              </span>
            )}
          </div>
          {locate === 'busy' && <p role="status" className="loc-note">{t(lang, 'findLocating')}</p>}
          {locate === 'outside' && <p role="status" className="loc-note">{t(lang, 'findOutside')}</p>}
          {locate === 'failed' && <p role="alert" className="loc-note">{t(lang, 'findFailed')}</p>}
          {current && !isMine && (
            <button type="button" className="primary" onClick={() => choose(current)}>{t(lang, 'setStreet')}</button>
          )}
          {current && isMine && picked && (
            <button type="button" className="primary" onClick={() => choose(current)}>{t(lang, 'showStreet')}</button>
          )}
          <div className="loc-btns">
            <button type="button" className="secondary" onClick={locateMe} disabled={locate === 'busy'}>{t(lang, 'findUseLocation')}</button>
            <button type="button" className="primary" onClick={() => setSheet(true)}>{t(lang, 'findAnother')}</button>
          </div>
        </section>
      </div>

      <section className="pad">
        <p className="summary"><strong>{atRisk}</strong> {t(lang, 'streetsAtRisk')} · {atWatch} {t(lang, 'streetsAtWatch')}</p>
        <div className="row">
          <h2>{t(lang, 'myStreets')}</h2>
          <button type="button" className="link" onClick={() => setSheet(true)}>{t(lang, 'edit')}</button>
        </div>
        {followed.length === 0 && <p className="muted">{t(lang, 'noStreets')}</p>}
        <ul className="my-streets">
          {followed.map((p) => (
            <li key={p.street_id}>
              <Link to={`/street/${p.street_id}`}>
                <span>{p.name}</span>
                <LevelBadge level={p.level} lang={lang} />
              </Link>
            </li>
          ))}
        </ul>
        {alerting.length === 0 && <Link to="/report" className="secondary report-link">{t(lang, 'reportLink')}</Link>}
        <Credits lang={lang} />
      </section>

      {sheet && (
        <div className="sheet-backdrop" onClick={(e) => { if (e.target === e.currentTarget) setSheet(false); }}>
          <div className="pick-sheet" role="dialog" aria-modal="true" aria-label={t(lang, 'pickStreets')}>
            <PickStreetsPage lang={lang} mine={mine} deviceId={deviceId} onSave={onSave} onClose={() => setSheet(false)} />
          </div>
        </div>
      )}
    </div>
  );
}

