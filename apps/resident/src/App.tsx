import { useState } from 'react';
import { Link, Route, Routes, useLocation } from 'react-router';
import type { Lang } from '@floodready/shared';
import { LangSwitch } from './components/LangSwitch';
import { StatusLine } from './components/StatusLine';
import { t } from './lib/i18n';
import { loadPrefs, savePrefs, type Prefs } from './lib/prefs';
import { usePushSync } from './push/usePushSync';
import { HomePage } from './routes/Home';
import { PickStreetsPage } from './routes/PickStreets';
import { ReportPage } from './routes/Report';
import { StreetHome } from './routes/StreetHome';

export function App() {
  const [prefs, setPrefs] = useState<Prefs>(loadPrefs);
  const update = (next: Partial<Prefs>) => setPrefs((p) => { const merged = { ...p, ...next }; savePrefs(merged); return merged; });
  const lang: Lang = prefs.lang;
  usePushSync({ deviceId: prefs.deviceId, streets: prefs.streets, lang });
  const path = useLocation().pathname;

  // The report form and the street picker need no live line; a replay is labelled on every screen
  // (replayed data must be shown as such).
  const showLive = !path.startsWith('/report') && !path.startsWith('/streets');
  const map = path.startsWith('/map');

  return (
    <div className="app">
      {/* The map draws its own red header (Back, title, language) above the map. */}
      {!map && (
        <>
          <header className="top">
            <Link to="/" className="brand">{t(lang, 'appName')}<small>{t(lang, 'township')}</small></Link>
            <LangSwitch lang={lang} onChange={(next) => update({ lang: next })} />
          </header>
          <StatusLine lang={lang} live={showLive} />
        </>
      )}
      <Routes>
        <Route path="/" element={<StreetHome lang={lang} deviceId={prefs.deviceId} saved={prefs.streets} onSave={(streets) => update({ streets })} />} />
        <Route path="/street/:id" element={<StreetHome lang={lang} deviceId={prefs.deviceId} saved={prefs.streets} onSave={(streets) => update({ streets })} />} />
        <Route path="/map" element={<HomePage lang={lang} mine={prefs.streets} deviceId={prefs.deviceId} onSave={(streets) => update({ streets })} onLang={(next) => update({ lang: next })} />} />
        <Route path="/report" element={<ReportPage lang={lang} deviceId={prefs.deviceId} mine={prefs.streets} />} />
        <Route path="/streets" element={<PickStreetsPage lang={lang} mine={prefs.streets} deviceId={prefs.deviceId} onSave={(streets) => update({ streets })} />} />
      </Routes>
    </div>
  );
}
