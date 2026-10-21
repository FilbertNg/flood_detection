import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useSearchParams } from 'react-router';
import type { Lang } from '@floodready/shared';
import { BackButton } from '../components/BackButton';
import { VerifySheet } from '../components/VerifySheet';
import { api } from '../lib/api';
import { t } from '../lib/i18n';

/** Report a flood when no alert is active (RES-5). Recorded as a possible missed flood. */
export function ReportPage({ lang, deviceId, mine }: { lang: Lang; deviceId: string; mine: string[] }) {
  const [params] = useSearchParams();
  const { data, isLoading, isError } = useQuery({ queryKey: ['streets'], queryFn: () => api.streets() });
  const [chosen, setChosen] = useState<string | null>(null);

  if (isLoading) return <p className="pad">{t(lang, 'loading')}</p>;
  if (isError || !data) return <p className="pad" role="alert">{t(lang, 'error')}</p>;

  const list = data.features.map((f) => f.properties).sort((a, b) => a.name.localeCompare(b.name));
  const known = (id: string | null | undefined) => (id && list.some((p) => p.street_id === id) ? id : undefined);
  const streetId = known(chosen) ?? known(params.get('street')) ?? known(mine.find((id) => known(id))) ?? list[0]?.street_id ?? '';

  return (
    <article className="pad report">
      <BackButton lang={lang} />
      <label className="field-label" htmlFor="report-street">{t(lang, 'reportStreet')}</label>
      <select id="report-street" className="search" value={streetId} onChange={(e) => setChosen(e.target.value)}>
        {list.map((p) => (
          <option key={p.street_id} value={p.street_id}>{p.name}</option>
        ))}
      </select>
      {streetId && <VerifySheet key={streetId} lang={lang} deviceId={deviceId} streetId={streetId} mode="report" />}
      <footer className="footer">{t(lang, 'footer')}</footer>
    </article>
  );
}
