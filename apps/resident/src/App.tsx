import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, Route, Routes, useLocation } from 'react-router';
import type { Lang } from '@floodready/shared';
import { LangSwitch } from './components/LangSwitch';
import { api } from './lib/api';
import { dayTime } from './lib/format';
import { t } from './lib/i18n';
import { loadPrefs, savePrefs, type Prefs } from './lib/prefs';
import { usePushSync } from './push/usePushSync';
import { HomePage } from './routes/Home';
import { PickStreetsPage } from './routes/PickStreets';
import { ReportPage } from './routes/Report';
import { SwipeShell } from './routes/SwipeHome';

export function App() {
  const [prefs, setPrefs] = useState<Prefs>(loadPrefs);
  const update = (next: Partial<Prefs>) => setPrefs((p) => { const merged = { ...p, ...next }; savePrefs(merged); return merged; });
  const { data: status } = useQuery({ queryKey: ['status'], queryFn: api.status, refetchInterval: 10_000 });
  const lang: Lang = prefs.lang;
  usePushSync({ deviceId: prefs.deviceId, streets: prefs.streets, lang });
  const path = useLocation().pathname;
  // The swipe home (start screen, pager, single street) is full screen: the sky reaches the top edge and
  // the street view carries its own top row; navigation is its bottom bar.
  const fullScreen = path === '/' || path.startsWith('/street/');
  // The report form and the street picker need no live strip; a replay is still labelled there
  // (replayed data must be shown as such).
  const showLive = !path.startsWith('/report') && !path.startsWith('/streets');

  return (
    <div className="app">
      {!fullScreen && (
        <>
          <header className="top">
            <Link to="/" className="brand">{t(lang, 'appName')} · {t(lang, 'township')}</Link>
            <LangSwitch lang={lang} onChange={(next) => update({ lang: next })} />
          </header>
          {status?.mode === 'replay' ? (
            <div className="ribbon replay">▶ {t(lang, 'replay')}: {dayTime(status.data_time)}</div>
          ) : status && showLive ? (
            <div className="ribbon live">● {t(lang, 'live')} · {t(lang, 'dataTime')} {dayTime(status.data_time)}</div>
          ) : null}
        </>
      )}
      <Routes>
        {/* One layout route for both paths, so a swipe can change the URL without remounting the pager. */}
        <Route element={<SwipeShell lang={lang} deviceId={prefs.deviceId} saved={prefs.streets} onSave={(streets) => update({ streets })} onLang={(next) => update({ lang: next })} />}>
          <Route index element={null} />
          <Route path="street/:id" element={null} />
        </Route>
        <Route path="/map" element={<HomePage lang={lang} mine={prefs.streets} />} />
        <Route path="/report" element={<ReportPage lang={lang} deviceId={prefs.deviceId} mine={prefs.streets} />} />
        <Route path="/streets" element={<PickStreetsPage lang={lang} mine={prefs.streets} deviceId={prefs.deviceId} onSave={(streets) => update({ streets })} />} />
      </Routes>
    </div>
  );
}
