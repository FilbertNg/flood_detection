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
import { StreetPage } from './routes/Street';

export function App() {
  const [prefs, setPrefs] = useState<Prefs>(loadPrefs);
  const update = (next: Partial<Prefs>) => setPrefs((p) => { const merged = { ...p, ...next }; savePrefs(merged); return merged; });
  const { data: status } = useQuery({ queryKey: ['status'], queryFn: api.status, refetchInterval: 10_000 });
  const lang: Lang = prefs.lang;
  usePushSync({ deviceId: prefs.deviceId, streets: prefs.streets, lang });
  // The street page is full screen (weather sky to the top edge) and draws its own top row.
  const fullScreen = useLocation().pathname.startsWith('/street/');

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
          ) : status ? (
            <div className="ribbon live">● {t(lang, 'live')} · {t(lang, 'dataTime')} {dayTime(status.data_time)}</div>
          ) : null}
        </>
      )}
      <Routes>
        <Route path="/" element={<HomePage lang={lang} mine={prefs.streets} />} />
        <Route path="/street/:id" element={<StreetPage lang={lang} deviceId={prefs.deviceId} onLang={(next) => update({ lang: next })} />} />
        <Route path="/report" element={<ReportPage lang={lang} deviceId={prefs.deviceId} mine={prefs.streets} />} />
        <Route path="/streets" element={<PickStreetsPage lang={lang} mine={prefs.streets} deviceId={prefs.deviceId} onSave={(streets) => update({ streets })} />} />
      </Routes>
    </div>
  );
}
