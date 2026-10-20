import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router';
import type { Lang, Level } from '@floodready/shared';
import { AlertHistory } from '../components/AlertHistory';
import { RainBars, TideLine } from '../components/Bars';
import { LevelBadge } from '../components/LevelBadge';
import { VerifySheet } from '../components/VerifySheet';
import { api } from '../lib/api';
import { dayTime, percent, riverForecastText, windowText } from '../lib/format';
import { t, type StringKey } from '../lib/i18n';

const ADVICE: Record<Level, StringKey> = {
  normal: 'adviceNormal', watch: 'adviceWatch', warning: 'adviceWarning', danger: 'adviceDanger',
};

export function StreetPage({ lang, deviceId }: { lang: Lang; deviceId: string }) {
  const { id = '' } = useParams();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['street', id],
    queryFn: () => api.street(id),
    refetchInterval: 10_000,
  });

  const river = data ? riverForecastText(data.river_forecast, lang) : null;

  const verify = !!data?.active_alert && (data.active_alert.level === 'warning' || data.active_alert.level === 'danger');

  if (isLoading) return <p className="pad">{t(lang, 'loading')}</p>;
  if (isError || !data) return <p className="pad">{t(lang, 'error')}</p>;

  return (
    <article className="street pad">
      <Link to="/" className="back">← {t(lang, 'back')}</Link>
      <h1>{data.name}</h1>
      <p className="muted">
        {t(lang, 'susceptibility')}: {data.susceptibility} {t(lang, 'of5')} · {t(lang, 'dataTime')} {dayTime(data.data_time)}
      </p>

      <section className="card">
        <h2>{t(lang, 'floodRisk')}</h2>
        <LevelBadge level={data.level} lang={lang} large />
        {data.window && (
          <p className="window">{t(lang, 'expected')} {windowText(data.window, lang)}</p>
        )}
        {data.flood_probability !== null && (
          <p className="ml">
            <strong>{percent(data.flood_probability)}</strong> {t(lang, 'chance')}
            <br />
            <span className="muted small">{t(lang, 'mlNote')}</span>
          </p>
        )}
      </section>

      <section className="card">
        <h2>{t(lang, 'why')}</h2>
        {data.reasons.length ? (
          <ul className="reasons">
            {data.reasons.map((r) => (
              <li key={r.code + r.station}>{r.text[lang]}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">{t(lang, 'noReasons')}</p>
        )}
      </section>

      <section className="card">
        <h2>{t(lang, 'whatToDo')}</h2>
        <p>{t(lang, ADVICE[data.level])}</p>
      </section>

      {river && (
        <section className="card" aria-labelledby="river-forecast">
          <h2 id="river-forecast">{t(lang, 'riverForecast')}</h2>
          <p>{river.now}</p>
          <ul className="reasons">
            {river.points.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          {river.warning && <p className="muted small">{river.warning}</p>}
          {river.mayReachWarning && <p><strong>{t(lang, 'riverMayReach')}</strong></p>}
          <p className="muted small">{t(lang, 'riverNote')}</p>
        </section>
      )}

      {verify ? (
        <VerifySheet key={data.active_alert!.alert_id} lang={lang} deviceId={deviceId} streetId={data.street_id} alertId={data.active_alert!.alert_id} mode="verify" />
      ) : (
        <Link to={`/report?street=${encodeURIComponent(data.street_id)}`} className="secondary report-link">{t(lang, 'reportLink')}</Link>
      )}

      <AlertHistory history={data.history} lang={lang} />

      <section className="card">
        <h2>{t(lang, 'rainNext')}</h2>
        <RainBars points={data.rain_next_12h} />
        <h2>{t(lang, 'tide')}</h2>
        <TideLine points={data.tide} />
      </section>

      <footer className="footer">{t(lang, 'footer')}</footer>
    </article>
  );
}
