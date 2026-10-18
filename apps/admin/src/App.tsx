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

const NAV = [
  { to: '/', label: 'Map', end: true },
  { to: '/statistics', label: 'Statistics' },
  { to: '/reports', label: 'Reports' },
  { to: '/suggestions', label: 'Suggestions' },
  { to: '/review', label: 'Review' },
];

export function App() {
  const token = useSyncExternalStore(auth.subscribe, auth.getToken);
  if (!token) return <LoginPage />;

  return (
    <div className="shell">
      <header className="top">
        <span className="brand">Flood-Ready Admin</span>
        <nav aria-label="Main">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? 'active' : undefined)}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <button type="button" className="signout" onClick={() => auth.logout()}>Sign out</button>
      </header>
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
  );
}
