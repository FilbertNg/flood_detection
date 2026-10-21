import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router';
import type { Lang, StreetProperties } from '@floodready/shared';
import { LogoMark } from '../components/Logo';
import { SkyBackdrop } from '../components/SkyHero';
import { api } from '../lib/api';
import { currentPosition, nearestStreet } from '../lib/geo';
import { t } from '../lib/i18n';

/** Further than this from every BBR street means the phone is outside the township. */
const OUTSIDE_M = 1000;

type State =
  | { k: 'idle' }
  | { k: 'busy' }
  | { k: 'found'; street: StreetProperties }
  | { k: 'outside' }
  | { k: 'failed' };

/**
 * Start screen when no street is saved. The location is asked for only after "Use my location" is
 * tapped, and the nearest street is found on the phone from the street map: the position is not sent.
 */
export function FindStreetPage({ lang, onSave }: { lang: Lang; onSave: (ids: string[]) => void }) {
  const client = useQueryClient();
  const [state, setState] = useState<State>({ k: 'idle' });

  const locate = async () => {
    setState({ k: 'busy' });
    try {
      const [place, col] = await Promise.all([
        currentPosition(),
        client.fetchQuery({ queryKey: ['streets'], queryFn: () => api.streets() }),
      ]);
      const hit = nearestStreet(place, col.features);
      if (!hit) setState({ k: 'failed' });
      else if (hit.distanceM > OUTSIDE_M) setState({ k: 'outside' });
      else setState({ k: 'found', street: hit.street });
    } catch {
      setState({ k: 'failed' });
    }
  };

  const list = <Link to="/streets" className="secondary">{t(lang, 'findList')}</Link>;

  return (
    <div className="find">
      <section className="hero hero-none find-hero">
        <SkyBackdrop sky="none" />
        <LogoMark tone="white" size={52} />
        <h1 className="hero-name">{t(lang, 'findTitle')}</h1>
        <p className="hero-headline">{t(lang, 'findWhy')}</p>
      </section>

      {state.k === 'idle' && (
        <div className="find-actions">
          <button type="button" className="primary" onClick={locate}>{t(lang, 'findUseLocation')}</button>
          {list}
          <p className="find-note">{t(lang, 'findPrivacy')}</p>
        </div>
      )}
      {state.k === 'busy' && <p role="status" className="find-note">{t(lang, 'findLocating')}</p>}
      {state.k === 'found' && (
        <div className="card find-confirm">
          <p>{t(lang, 'findConfirm')}</p>
          <strong className="find-street">{state.street.name}</strong>
          <div className="find-actions">
            <button type="button" className="primary" onClick={() => onSave([state.street.street_id])}>{t(lang, 'ansYes')}</button>
            <Link to="/streets" className="secondary">{t(lang, 'findAnother')}</Link>
          </div>
        </div>
      )}
      {state.k === 'outside' && (
        <div className="find-actions">
          <p role="status">{t(lang, 'findOutside')}</p>
          {list}
        </div>
      )}
      {state.k === 'failed' && (
        <div className="find-actions">
          <p role="alert">{t(lang, 'findFailed')}</p>
          {list}
        </div>
      )}
    </div>
  );
}
