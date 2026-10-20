import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router';
import type { Lang, StreetProperties } from '@floodready/shared';
import { BottomBar } from '../components/BottomBar';
import { Credits } from '../components/Credits';
import { LevelBadge } from '../components/LevelBadge';
import { StreetMap } from '../components/StreetMap';
import { api } from '../lib/api';
import { t } from '../lib/i18n';

export function HomePage({ lang, mine }: { lang: Lang; mine: string[] }) {
  const navigate = useNavigate();
  const { data, isLoading, isError } = useQuery({ queryKey: ['streets'], queryFn: () => api.streets(), refetchInterval: 10_000 });

  if (isLoading) return <p className="pad">{t(lang, 'loading')}</p>;
  if (isError || !data) return <p className="pad">{t(lang, 'error')}</p>;

  const props = data.features.map((f) => f.properties);
  const atRisk = props.filter((p) => p.level === 'warning' || p.level === 'danger').length;
  const atWatch = props.filter((p) => p.level === 'watch').length;
  const followed = mine.map((id) => props.find((p) => p.street_id === id)).filter((p): p is StreetProperties => !!p);
  const alerting = followed.filter((p) => p.level === 'warning' || p.level === 'danger');
  const watching = followed.filter((p) => p.level === 'watch');

  return (
    <div className="home">
      <div className="pad"><Link to="/" className="back">← {t(lang, 'back')}</Link></div>
      {alerting.length > 0 && (
        <Link to={`/street/${alerting[0].street_id}`} className="alert-banner">
          ⚠ {t(lang, 'activeAlert')}: {alerting[0].name}
        </Link>
      )}
      {alerting.length === 0 && watching.length > 0 && (
        <Link to={`/street/${watching[0].street_id}`} className="alert-banner watch">
          {t(lang, 'watchAlert')}: {watching[0].name}
        </Link>
      )}
      <StreetMap data={data} mine={mine} onSelect={(id) => navigate(`/street/${id}`)} />
      <section className="pad">
        <p className="summary"><strong>{atRisk}</strong> {t(lang, 'streetsAtRisk')} · {atWatch} {t(lang, 'streetsAtWatch')}</p>
        <div className="row">
          <h2>{t(lang, 'myStreets')}</h2>
          <Link to="/streets" className="link">{t(lang, 'edit')}</Link>
        </div>
        {followed.length === 0 && <p className="muted">{t(lang, 'noStreets')}</p>}
        <ul className="my-streets">
          {followed.map((p) => (
            <li key={p.street_id}>
              <Link to={`/street/${p.street_id}`}>
                <span>{p.name}</span>
                <LevelBadge level={p.level} lang={lang} />
              </Link>
            </li>
          ))}
        </ul>
        {alerting.length === 0 && <Link to="/report" className="secondary report-link">{t(lang, 'reportLink')}</Link>}
        <Credits lang={lang} />
      </section>
      <BottomBar lang={lang} />
    </div>
  );
}
