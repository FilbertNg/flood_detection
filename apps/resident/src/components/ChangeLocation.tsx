import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import type { Lang, StreetProperties } from '@floodready/shared';
import { api } from '../lib/api';
import { currentPosition, nearestStreet } from '../lib/geo';
import { t } from '../lib/i18n';
import { PickStreetsPage } from '../routes/PickStreets';
import { Icon } from './Icons';

/** Further than this from every BBR street means the phone is outside the township. */
const OUTSIDE_M = 1000;

type State =
  | { k: 'idle' }
  | { k: 'busy' }
  | { k: 'found'; street: StreetProperties }
  | { k: 'outside' }
  | { k: 'failed' }
  | { k: 'list' };

/**
 * "Change location" on the home page: a bottom sheet with the same two ways in as the start screen,
 * the phone location (nearest street found on the phone, then a confirm) or the street list.
 */
export function ChangeLocation({ lang, mine, deviceId, onSave }: { lang: Lang; mine: string[]; deviceId: string; onSave: (ids: string[]) => void }) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<State>({ k: 'idle' });
  const close = () => { setOpen(false); setState({ k: 'idle' }); };

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') close(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  const locate = async () => {
    setState({ k: 'busy' });
    try {
      const [place, col] = await Promise.all([currentPosition(), client.fetchQuery({ queryKey: ['streets'], queryFn: () => api.streets() })]);
      const hit = nearestStreet(place, col.features);
      if (!hit) setState({ k: 'failed' });
      else if (hit.distanceM > OUTSIDE_M) setState({ k: 'outside' });
      else setState({ k: 'found', street: hit.street });
    } catch {
      setState({ k: 'failed' });
    }
  };

  return (
    <>
      <button type="button" className="change-loc" onClick={() => setOpen(true)}>
        <Icon name="pin" />{t(lang, 'changeLocation')}
      </button>
      {open && (
        <div className="sheet-backdrop" onClick={(e) => { if (e.target === e.currentTarget) close(); }}>
          <div className="pick-sheet" role="dialog" aria-modal="true" aria-label={t(lang, 'changeTitle')}>
            {state.k === 'list' ? (
              <PickStreetsPage lang={lang} mine={mine} deviceId={deviceId} onSave={onSave} onClose={close} />
            ) : (
              <div className="pad change-sheet">
                <button type="button" className="sheet-close" onClick={close}>{t(lang, 'close')}</button>
                <h1>{t(lang, 'changeTitle')}</h1>
                {state.k === 'found' ? (
                  <div className="find-confirm">
                    <p>{t(lang, 'findConfirm')}</p>
                    <strong className="find-street">{state.street.name}</strong>
                    <div className="find-actions">
                      <button type="button" className="primary" onClick={() => { onSave([state.street.street_id]); close(); }}>{t(lang, 'ansYes')}</button>
                      <button type="button" className="secondary" onClick={() => setState({ k: 'list' })}>{t(lang, 'findAnother')}</button>
                    </div>
                  </div>
                ) : (
                  <div className="find-actions">
                    {state.k === 'busy' && <p role="status" className="find-note">{t(lang, 'findLocating')}</p>}
                    {state.k === 'outside' && <p role="status">{t(lang, 'findOutside')}</p>}
                    {state.k === 'failed' && <p role="alert" className="form-error">{t(lang, 'findFailed')}</p>}
                    <button type="button" className="primary" onClick={locate} disabled={state.k === 'busy'}>{t(lang, 'findUseLocation')}</button>
                    <button type="button" className="secondary" onClick={() => setState({ k: 'list' })}>{t(lang, 'findList')}</button>
                    <p className="find-note">{t(lang, 'findPrivacy')}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
