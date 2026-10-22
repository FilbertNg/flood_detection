import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router';
import type { Lang, StreetProperties } from '@floodready/shared';
import { LogoMark } from '../components/Logo';
import { OnboardingMap } from '../components/OnboardingMap';
import { api } from '../lib/api';
import { currentPosition, nearestStreet } from '../lib/geo';
import { t, tf } from '../lib/i18n';

/** Further than this from every BBR street means the phone is outside the township. */
const OUTSIDE_M = 1000;

type State =
  | { k: 'idle' }
  | { k: 'busy' }
  | { k: 'found'; street: StreetProperties }
  | { k: 'outside' }
  | { k: 'failed' };

/** Locate icon for "Find my street": a crosshair round a dot. */
function LocateIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="3" /><circle cx="12" cy="12" r="8" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2" />
    </svg>
  );
}

/**
 * Onboarding (docs/design/onboarding-proposal.html), the first screen of every visit: one screen with no
 * scrolling, no app header and no language switch. The red illustration and the logo fill the top; a
 * white card holds the line and the two actions. The location is asked for only after "Find my street"
 * is tapped, and the nearest street is found on the phone from the street map: the position is not sent.
 */
export function FindStreetPage({ lang, onSave, mine, onOpen }: { lang: Lang; onSave: (ids: string[]) => void; mine?: string; onOpen?: () => void }) {
  const client = useQueryClient();
  const [state, setState] = useState<State>({ k: 'idle' });
  // Replayed data must be labelled; this screen has no live line, so it never says "Live".
  const { data: status } = useQuery({ queryKey: ['status'], queryFn: api.status, refetchInterval: 10_000 });
  // A returning resident (a street saved): the card opens their street instead of finding one.
  const streets = useQuery({ queryKey: ['streets'], queryFn: () => api.streets(), enabled: !!mine });
  const mineName = mine && streets.data?.features.find((f) => f.properties.street_id === mine)?.properties.name;

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

  const list = <Link to="/streets" className="onb-link">{t(lang, 'findList')}</Link>;

  return (
    <div className="onb">
      {status?.mode === 'replay' && <p className="onb-replay"><span aria-hidden="true">▶ </span>{t(lang, 'replayChip')}</p>}
      <div className="onb-art">
        <OnboardingMap />
        {/* Who the app is built for: Sime Darby Property's own logo file (public/sdp-logo.png), cropped, not redrawn. */}
        <p className="onb-builtfor"><span>{t(lang, 'onbBuiltFor')}</span><img src="/sdp-logo.png" alt="Sime Darby Property" width="40" height="30" /></p>
        <div className="onb-brand" role="img" aria-label={t(lang, 'appName')}>
          <span className="onb-glow" aria-hidden="true" />
          <LogoMark tone="white" size={92} />
          <span className="onb-name" aria-hidden="true">{t(lang, 'appName')}</span>
        </div>
      </div>

      <section className="onb-card" aria-labelledby="onb-title">
        <h1 id="onb-title">{t(lang, 'onbTitle')} <em>{t(lang, 'onbTitleEm')}</em></h1>
        {state.k === 'idle' && mine && (
          <>
            <button type="button" className="onb-find" onClick={onOpen}>{mineName ? tf(lang, 'onbOpen', { street: mineName }) : t(lang, 'onbOpenMine')}</button>
            <Link to="/streets" className="onb-link">{t(lang, 'onbAnother')}</Link>
          </>
        )}
        {state.k === 'idle' && !mine && (
          <>
            <button type="button" className="onb-find" onClick={locate}><LocateIcon />{t(lang, 'onbFind')}</button>
            {list}
          </>
        )}
        {state.k === 'busy' && (
          <div role="status" className="onb-status">
            <p>{t(lang, 'findLocating')}</p>
            <p className="onb-fine">{t(lang, 'findPrivacy')}</p>
          </div>
        )}
        {state.k === 'found' && (
          <div className="onb-confirm">
            <p>{t(lang, 'findConfirm')}</p>
            <strong className="onb-street">{state.street.name}</strong>
            <button type="button" className="onb-find" onClick={() => onSave([state.street.street_id])}>{t(lang, 'ansYes')}</button>
            <Link to="/streets" className="onb-link">{t(lang, 'findAnother')}</Link>
          </div>
        )}
        {state.k === 'outside' && (
          <>
            <p role="status" className="onb-msg">{t(lang, 'findOutside')}</p>
            {list}
          </>
        )}
        {state.k === 'failed' && (
          <>
            <p role="alert" className="onb-msg">{t(lang, 'findFailed')}</p>
            {list}
          </>
        )}
      </section>
    </div>
  );
}
