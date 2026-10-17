import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import type { Lang } from '@floodready/shared';
import { api } from '../lib/api';
import { NotificationOffer } from '../components/NotificationOffer';
import { t } from '../lib/i18n';
import { isSubscribed } from '../push/subscribe';

/** Choose the streets to follow (stored on this device only). */
export function PickStreetsPage({ lang, mine, deviceId, onSave }: { lang: Lang; mine: string[]; deviceId: string; onSave: (ids: string[]) => void }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [chosen, setChosen] = useState<string[]>(mine);
  const [saved, setSaved] = useState(false);
  const [subscribed, setSubscribed] = useState(false);
  const { data } = useQuery({ queryKey: ['streets'], queryFn: () => api.streets() });

  const streets = useMemo(() => {
    const all = (data?.features ?? []).map((f) => f.properties).sort((a, b) => a.name.localeCompare(b.name));
    const q = query.trim().toLowerCase();
    return (q ? all.filter((s) => s.name.toLowerCase().includes(q)) : all).slice(0, 60);
  }, [data, query]);

  useEffect(() => {
    void isSubscribed().then(setSubscribed);
  }, []);

  const save = () => {
    onSave(chosen);
    if (chosen.length === 0) navigate('/');
    else setSaved(true);
  };

  const toggle = (id: string) => setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));

  return (
    <div className="pad pick">
      <h1>{t(lang, 'pickStreets')}</h1>
      <input className="search" placeholder={t(lang, 'searchPlaceholder')} value={query} onChange={(e) => setQuery(e.target.value)} />
      <ul className="pick-list">
        {streets.map((s) => (
          <li key={s.street_id}>
            <label>
              <input type="checkbox" checked={chosen.includes(s.street_id)} onChange={() => toggle(s.street_id)} />
              {s.name}
            </label>
          </li>
        ))}
      </ul>
      {saved || subscribed ? (
        <NotificationOffer lang={lang} deviceId={deviceId} streetIds={chosen} onDone={() => navigate('/')} />
      ) : null}
      {!saved && <button className="primary" onClick={save}>{t(lang, 'save')}</button>}
    </div>
  );
}
