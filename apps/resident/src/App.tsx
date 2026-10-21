import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, Route, Routes, useLocation } from 'react-router';
import type { Lang } from '@floodready/shared';
import { LangSwitch } from './components/LangSwitch';
import { LogoMark } from './components/Logo';
import { api } from './lib/api';
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
  // Under the logo: my chosen street (picked from the list or found from my location); the township
  // until one is chosen. The street list is the same cached query the other screens use.
  const mine = prefs.streets[0];
  const streets = useQuery({ queryKey: ['streets'], queryFn: () => api.streets(), enabled: !!mine });
  const place = (mine && streets.data?.features.find((f) => f.properties.street_id === mine)?.properties.name) || t(lang, 'township');

  // The street picker needs no live line, and the report form shows no data at all, so it gets no line;
  // every screen that shows data labels a replay (replayed data must be shown as such).
  const map = path.startsWith('/map');
  // The first-visit onboarding (/ with no street saved) is one full screen with no header.
  const onboarding = path === '/' && !mine;

  return (
    <div className="app">
      {/* The map draws its own red header (Back, title, language) above the map; onboarding has none. */}
      {!map && !onboarding && (
        <>
          <header className="top">
            <Link to="/" className="brand">
              <LogoMark tone="white" size={34} />
              <span>{t(lang, 'appName')}<small>{place}</small></span>
            </Link>
            <LangSwitch lang={lang} onChange={(next) => update({ lang: next })} />
          </header>
        </>
      )}
      <Routes>
        <Route path="/" element={<StreetHome lang={lang} deviceId={prefs.deviceId} saved={prefs.streets} onSave={(streets) => update({ streets })} />} />
        <Route path="/street/:id" element={<StreetHome lang={lang} deviceId={prefs.deviceId} saved={prefs.streets} onSave={(streets) => update({ streets })} />} />
        <Route path="/map" element={<HomePage lang={lang} mine={prefs.streets} onLang={(next) => update({ lang: next })} />} />
        <Route path="/report" element={<ReportPage lang={lang} deviceId={prefs.deviceId} mine={prefs.streets} />} />
        <Route path="/streets" element={<PickStreetsPage lang={lang} mine={prefs.streets} deviceId={prefs.deviceId} onSave={(streets) => update({ streets })} />} />
      </Routes>
    </div>
  );
}
