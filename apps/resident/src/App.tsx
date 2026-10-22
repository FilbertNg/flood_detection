import { useQuery } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { Link, Route, Routes, useLocation } from 'react-router';
import type { Lang } from '@floodready/shared';
import { LangSwitch } from './components/LangSwitch';
import { LogoMark } from './components/Logo';
import { LogoFill } from './components/LogoFill';
import { api } from './lib/api';
import { t } from './lib/i18n';
import { loadPrefs, savePrefs, type Prefs } from './lib/prefs';
import { useDelayed } from './lib/useDelayed';
import { introSeen, markIntroSeen } from './lib/visit';
import { usePushSync } from './push/usePushSync';
import { HomePage } from './routes/Home';
import { PickStreetsPage } from './routes/PickStreets';
import { ReportPage } from './routes/Report';
import { StreetHome } from './routes/StreetHome';

export function App() {
  const [prefs, setPrefs] = useState<Prefs>(loadPrefs);
  // Each visit opens on the onboarding screen; after it, the home page for the rest of the visit.
  const [introDone, setIntroDone] = useState(introSeen);
  const finishIntro = () => { markIntroSeen(); setIntroDone(true); };
  // Saving a street (onboarding, the picker) also ends the onboarding for this visit.
  const saveStreets = (streets: string[]) => { update({ streets }); finishIntro(); };
  const update = (next: Partial<Prefs>) => setPrefs((p) => { const merged = { ...p, ...next }; savePrefs(merged); return merged; });
  const lang: Lang = prefs.lang;
  usePushSync({ deviceId: prefs.deviceId, streets: prefs.streets, lang });
  const path = useLocation().pathname;
  // Under the logo: my chosen street (picked from the list or found from my location); the township
  // until one is chosen. The street list is the same cached query the other screens use.
  const mine = prefs.streets[0];
  const streets = useQuery({ queryKey: ['streets'], queryFn: () => api.streets(), enabled: !!mine });
  const place = (mine && streets.data?.features.find((f) => f.properties.street_id === mine)?.properties.name) || t(lang, 'township');
  // First open: wait for the first status answer (live or replay) behind a splash, shown only if it takes
  // over 300 ms. One retry, then the screens take over and show their own errors.
  const boot = useQuery({ queryKey: ['status'], queryFn: api.status, retry: 1 });
  // A one-time gate: once the first answer (or error) is in, later refetches never bring the splash back.
  const booted = useRef(false);
  if (!boot.isPending) booted.current = true;
  const splash = useDelayed(!booted.current, 300);

  // The street picker needs no live line, and the report form shows no data at all, so it gets no line;
  // every screen that shows data labels a replay (replayed data must be shown as such).
  const map = path.startsWith('/map');
  // The onboarding screen (/ before the visit has been through it, or with no street saved) has no header.
  const onboarding = path === '/' && (!mine || !introDone);

  if (!booted.current) {
    return splash ? (
      <div className="splash" role="status" aria-label={`${t(lang, 'appName')}: ${t(lang, 'splashChecking')}`}>
        <LogoFill size={104} />
        <b>{t(lang, 'appName')}</b>
        <small>{t(lang, 'splashChecking')}</small>
      </div>
    ) : null;
  }

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
        <Route path="/" element={<StreetHome lang={lang} deviceId={prefs.deviceId} saved={prefs.streets} onSave={saveStreets} introDone={introDone} onIntroDone={finishIntro} />} />
        <Route path="/street/:id" element={<StreetHome lang={lang} deviceId={prefs.deviceId} saved={prefs.streets} onSave={saveStreets} introDone={introDone} onIntroDone={finishIntro} />} />
        <Route path="/map" element={<HomePage lang={lang} mine={prefs.streets} onLang={(next) => update({ lang: next })} />} />
        <Route path="/report" element={<ReportPage lang={lang} deviceId={prefs.deviceId} mine={prefs.streets} />} />
        <Route path="/streets" element={<PickStreetsPage lang={lang} mine={prefs.streets} deviceId={prefs.deviceId} onSave={saveStreets} />} />
      </Routes>
    </div>
  );
}
