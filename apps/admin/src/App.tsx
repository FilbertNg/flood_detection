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
  if (!token) return <LoginPage />;

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
          {NAV.map((g) => {
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
        <button type="button" className="signout" onClick={() => auth.logout()}>Sign out</button>
      </aside>
      <div className="main">
        <Routes>
          <Route path="/" element={<OpsMapPage />} />
          <Route path="/street/:id" element={<StreetDetailPage />} />
          <Route path="/statistics" element={<StatisticsPage />} />
          <Route path="/reports" element={<ReportPage />} />
          <Route path="/suggestions" element={<SuggestionsPage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  );
}
