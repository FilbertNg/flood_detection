import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router';
import type { Lang } from '@floodready/shared';
import { BackButton } from '../components/BackButton';
import { api } from '../lib/api';
import { NotificationOffer } from '../components/NotificationOffer';
import { t } from '../lib/i18n';
import { isSubscribed } from '../push/subscribe';

/**
 * Choose my street (one, stored on this device only). As a page (/streets) it has a Back link;
 * as the map's bottom sheet it gets `onClose` and shows a Close button instead.
 */
export function PickStreetsPage({ lang, mine, deviceId, onSave, onClose }: { lang: Lang; mine: string[]; deviceId: string; onSave: (ids: string[]) => void; onClose?: () => void }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  // One street: an older phone with several saved starts on its first.
  const [chosen, setChosen] = useState<string | null>(mine[0] ?? null);
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
    if (!chosen) return;
    onSave([chosen]);
    setSaved(true);
  };

  return (
    <div className="pad pick">
      {onClose ? (
        <button type="button" className="sheet-close" onClick={onClose}>{t(lang, 'close')}</button>
      ) : (
        <BackButton lang={lang} />
      )}
      <h1>{t(lang, 'pickStreets')}</h1>
      <input className="search" placeholder={t(lang, 'searchPlaceholder')} value={query} onChange={(e) => setQuery(e.target.value)} />
      <ul className="pick-list" role="radiogroup" aria-label={t(lang, 'pickStreets')}>
        {streets.map((s) => (
          <li key={s.street_id}>
            <label>
              <input type="radio" name="my-street" checked={chosen === s.street_id} onChange={() => setChosen(s.street_id)} />
              {s.name}
            </label>
          </li>
        ))}
      </ul>
      {saved || subscribed ? (
        <NotificationOffer lang={lang} deviceId={deviceId} streetIds={chosen ? [chosen] : []} onDone={() => navigate('/')} />
      ) : null}
      {!saved && <button className="primary" onClick={save} disabled={!chosen}>{t(lang, 'save')}</button>}
    </div>
  );
}
