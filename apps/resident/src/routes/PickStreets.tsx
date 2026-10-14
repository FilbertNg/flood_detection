import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import type { Lang } from '@floodready/shared';
import { api } from '../lib/api';
import { t } from '../lib/i18n';

/** Choose the streets to follow (stored on this device only). */
export function PickStreetsPage({ lang, mine, onSave }: { lang: Lang; mine: string[]; onSave: (ids: string[]) => void }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [chosen, setChosen] = useState<string[]>(mine);
  const { data } = useQuery({ queryKey: ['streets'], queryFn: () => api.streets() });

  const streets = useMemo(() => {
    const all = (data?.features ?? []).map((f) => f.properties).sort((a, b) => a.name.localeCompare(b.name));
    const q = query.trim().toLowerCase();
    return (q ? all.filter((s) => s.name.toLowerCase().includes(q)) : all).slice(0, 60);
  }, [data, query]);

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
      <button className="primary" onClick={() => { onSave(chosen); navigate('/'); }}>{t(lang, 'save')}</button>
    </div>
  );
}
