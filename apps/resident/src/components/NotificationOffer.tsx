import { useEffect, useRef, useState } from 'react';
import type { Lang } from '@floodready/shared';
import { t } from '../lib/i18n';
import { enablePush, isSubscribed, permissionState, pushSupport, stopPush } from '../push/subscribe';
import { InstallGuide } from './InstallGuide';

type View = 'checking' | 'offer' | 'on' | 'stopped' | 'denied' | 'error' | 'stopError';

interface Props {
  lang: Lang;
  deviceId: string;
  streetIds: string[];
  /** Called when the resident chooses "Not now". Optional: the panel can also stay on screen. */
  onDone?: () => void;
}

/** Offer (or manage) push notifications for the followed streets. */
export function NotificationOffer({ lang, deviceId, streetIds, onDone }: Props) {
  const [support] = useState(pushSupport);
  const [view, setView] = useState<View>('checking');
  const [busy, setBusy] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let live = true;
    if (support !== 'ok') return;
    if (permissionState() === 'denied') {
      setView('denied');
      return;
    }
    isSubscribed().then((on) => live && setView(on ? 'on' : 'offer'));
    return () => {
      live = false;
    };
  }, [support]);

  // After changing the site setting the resident comes back to this tab: leave the denied view.
  useEffect(() => {
    if (view !== 'denied') return;
    const recheck = () => {
      if (permissionState() === 'denied') return;
      void isSubscribed().then((on) => setView(on ? 'on' : 'offer'));
    };
    window.addEventListener('focus', recheck);
    return () => window.removeEventListener('focus', recheck);
  }, [view]);

  useEffect(() => {
    if (view !== 'checking') heading.current?.focus();
  }, [view]);

  if (support === 'needs-install') return <div className="offer"><InstallGuide lang={lang} /></div>;
  if (support === 'unsupported') return <div className="offer"><p>{t(lang, 'notifUnsupported')}</p></div>;
  if (view === 'checking') return null;

  const enable = async () => {
    setBusy(true);
    const result = await enablePush({ deviceId, streetIds, lang });
    setBusy(false);
    setView(result === 'granted' ? 'on' : result === 'denied' ? 'denied' : 'error');
  };

  const stop = async () => {
    setBusy(true);
    try {
      await stopPush(deviceId);
      setView('stopped');
    } catch {
      setView('stopError');
    }
    setBusy(false);
  };

  return (
    <section className="offer" aria-labelledby="offer-title">
      <h2 id="offer-title" ref={heading} tabIndex={-1}>{t(lang, 'notifTitle')}</h2>
      {view === 'on' ? (
        <>
          <p role="status">{t(lang, 'notifOn')}</p>
          <div className="row">
            <button className="secondary" disabled={busy} onClick={stop}>{t(lang, 'notifStop')}</button>
            {onDone && <button className="primary" onClick={onDone}>{t(lang, 'done')}</button>}
          </div>
        </>
      ) : view === 'stopped' ? (
        <>
          <p role="status">{t(lang, 'notifStopped')}</p>
          <div className="row">
            <button className="primary" disabled={busy} onClick={enable}>{t(lang, 'notifEnable')}</button>
            {onDone && <button className="secondary" onClick={onDone}>{t(lang, 'done')}</button>}
          </div>
        </>
      ) : (
        <>
          <p>{t(lang, 'notifWhy')}</p>
          {view === 'denied' && <p role="alert">{t(lang, 'notifDenied')}</p>}
          {view === 'error' && <p role="alert">{t(lang, 'notifError')}</p>}
          {view === 'stopError' && <p role="alert">{t(lang, 'notifStopError')}</p>}
          <div className="row">
            {view !== 'denied' && (
              <button className="primary" disabled={busy} onClick={enable}>
                {busy ? t(lang, 'notifBusy') : t(lang, 'notifEnable')}
              </button>
            )}
            {onDone && <button className="secondary" onClick={onDone}>{view === 'denied' ? t(lang, 'done') : t(lang, 'notifLater')}</button>}
          </div>
        </>
      )}
    </section>
  );
}
