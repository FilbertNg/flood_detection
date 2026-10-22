import { useSyncExternalStore } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router';
import { auth } from './auth';
import { LoginPage } from './routes/Login';
import { OpsMapPage } from './routes/OpsMap';
import { ReportPage } from './routes/Report';
import { ReviewPage } from './routes/Review';
import { StatisticsPage } from './routes/Statistics';
import { StreetDetailPage } from './routes/StreetDetail';
import { SuggestionsPage } from './routes/Suggestions';
import { LogoMark } from './components/Logo';

/** Grouped by the job the officer is doing: watch now, look back, act on findings. */
const NAV: { group: string; links: { to: string; label: string; end?: boolean }[] }[] = [
  { group: 'Monitor', links: [{ to: '/', label: 'Map', end: true }] },
  { group: 'Analyse', links: [{ to: '/statistics', label: 'Statistics' }, { to: '/reports', label: 'Reports' }] },
  { group: 'Follow up', links: [{ to: '/suggestions', label: 'Suggestions' }, { to: '/review', label: 'Review' }] },
];

export function App() {
  const token = useSyncExternalStore(auth.subscribe, auth.getToken);
  const preview = useSyncExternalStore(auth.subscribe, auth.isPreview);
  if (!token) return <LoginPage />;
  // The preview never shows residents' answers, so the Review page is left out of it.
  const nav = preview ? NAV.map((g) => ({ ...g, links: g.links.filter((l) => l.to !== '/review') })) : NAV;

  return (
    <div className="shell">
      <aside className="side">
        <span className="brand">
          <LogoMark size={34} />
          <span className="brand-text">
            <span className="brand-name">Flood-Ready</span>
            <span className="brand-tag">Admin</span>
          </span>
        </span>
        <nav aria-label="Main">
          {nav.map((g) => {
            const id = `nav-${g.group.toLowerCase().replace(' ', '-')}`;
            return (
              <div key={g.group} className="nav-group">
                <span id={id} className="nav-heading">{g.group}</span>
                <ul aria-labelledby={id}>
                  {g.links.map((n) => (
                    <li key={n.to}>
                      <NavLink to={n.to} end={n.end} className={({ isActive }) => (isActive ? 'active' : undefined)}>
                        {n.label}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </nav>
        <button type="button" className="signout" onClick={() => auth.logout()}>{preview ? 'Leave preview' : 'Sign out'}</button>
      </aside>
      <div className="main">
        {preview && (
          <p className="preview-banner" role="status" aria-label="Read-only preview">
            Read-only preview: changes are switched off and residents' answers are hidden.
          </p>
        )}
        <Routes>
          <Route path="/" element={<OpsMapPage />} />
          <Route path="/street/:id" element={<StreetDetailPage />} />
          <Route path="/statistics" element={<StatisticsPage />} />
          <Route path="/reports" element={<ReportPage />} />
          <Route path="/suggestions" element={<SuggestionsPage />} />
          <Route path="/review" element={preview ? <Navigate to="/" replace /> : <ReviewPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  );
}
