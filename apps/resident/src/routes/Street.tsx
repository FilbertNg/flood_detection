import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router';
import type { Lang, Level } from '@floodready/shared';
import { AlertHistory } from '../components/AlertHistory';
import { Icon, WeatherIcon } from '../components/Icons';
import { LangSwitch } from '../components/LangSwitch';
import { LevelBadge } from '../components/LevelBadge';
import { SkyBackdrop } from '../components/SkyHero';
import { HourlyStrip, ProneTile, RainNowTile, RiverTile, TideTile } from '../components/StreetTiles';
import { VerifySheet } from '../components/VerifySheet';
import { api } from '../lib/api';
import { dayTime, percent, riverForecastText, windowText } from '../lib/format';
import { t, type StringKey } from '../lib/i18n';
import { gaugeRain, hourAt, parseWeather, skyFor, weatherKind, weatherUrl, type WeatherKind } from '../lib/weather';

const ADVICE: Record<Level, StringKey> = {
  normal: 'adviceNormal', watch: 'adviceWatch', warning: 'adviceWarning', danger: 'adviceDanger',
};

const WX_LABEL: Record<WeatherKind, StringKey> = {
  'clear-day': 'wxClearDay', 'clear-night': 'wxClearNight', 'partly-day': 'wxPartly', 'partly-night': 'wxPartly',
  cloudy: 'wxCloudy', fog: 'wxFog', drizzle: 'wxDrizzle', rain: 'wxRain', storm: 'wxStorm',
};

const FIFTEEN_MIN = 15 * 60_000;

/** Open-Meteo hourly weather for the data day; any failure means "no weather", never an error screen. */
async function fetchWeather(dataTime: string) {
  try {
    const response = await fetch(weatherUrl(dataTime));
    return response.ok ? parseWeather(await response.json()) : null;
  } catch {
    return null;
  }
}

/** Full screen: the app header and live strip are hidden here, so this page carries Back, language and the replay label. */
export function StreetPage({ lang, deviceId, onLang }: { lang: Lang; deviceId: string; onLang?: (lang: Lang) => void }) {
  const { id = '' } = useParams();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['street', id],
    queryFn: () => api.street(id),
    refetchInterval: 10_000,
  });
  const day = data?.data_time.slice(0, 10);
  const weather = useQuery({
    queryKey: ['weather', day],
    queryFn: () => fetchWeather(data!.data_time),
    enabled: !!data,
    staleTime: FIFTEEN_MIN,
    refetchInterval: FIFTEEN_MIN,
  });
  const stations = useQuery({
    queryKey: ['stations'],
    queryFn: () => api.stations().catch(() => null),
    enabled: !!data,
    refetchInterval: 60_000,
  });

  const river = data ? riverForecastText(data.river_forecast, lang) : null;
  const verify = !!data?.active_alert && (data.active_alert.level === 'warning' || data.active_alert.level === 'danger');

  if (isLoading) return <p className="pad">{t(lang, 'loading')}</p>;
  if (isError || !data) return <p className="pad">{t(lang, 'error')}</p>;

  const hours = weather.data ?? null;
  const nowHour = hourAt(hours, data.data_time);
  const kind = nowHour ? weatherKind(nowHour.code, nowHour.isDay) : null;
  const gauge = gaugeRain(stations.data, data.stations);
  const sky = skyFor(data.level, kind, gauge);
  const chance = nowHour?.rainChance;

  return (
    <article className={`street sky-page sky-page-${sky}`}>
      <SkyBackdrop sky={sky} />
      <div className="sky-content">
        <div className="sky-top">
          <Link to="/" className="back">← {t(lang, 'back')}</Link>
          {onLang && <LangSwitch lang={lang} onChange={onLang} />}
        </div>
        {data.is_replay && <p className="sky-replay"><span aria-hidden="true">▶ </span>{t(lang, 'replayChip')}</p>}

        <header className="sky-hero">
          <h1>{data.name}</h1>
          <div className="sky-level"><LevelBadge level={data.level} lang={lang} large /></div>
          {kind && (
            <p className="sky-weather">
              <WeatherIcon kind={kind} />
              <span>{`${t(lang, WX_LABEL[kind])}${chance != null ? ` · ${chance}% ${t(lang, 'wxChance')}` : ''}`}</span>
            </p>
          )}
          {gauge && <p className="sky-line">{`${t(lang, 'rainAt')} ${gauge.station}: ${gauge.mm} mm ${t(lang, 'inLastHour')}`}</p>}
          {data.window && <p className="window">{t(lang, 'expected')} {windowText(data.window, lang)}</p>}
          {data.flood_probability !== null && (
            <p className="ml">
              <strong>{percent(data.flood_probability)}</strong> {t(lang, 'chance')}
              <br />
              <span className="sky-small">{t(lang, 'mlNote')}</span>
            </p>
          )}
          <p className="sky-small">
            {t(lang, 'dataTime')} {dayTime(data.data_time)}
            {kind && <> · <span>{t(lang, 'wxCredit')}</span></>}
          </p>
        </header>

        <section className="tile" aria-labelledby="rain-next">
          <h2 className="tile-title" id="rain-next"><Icon name="clock" />{t(lang, 'rainNext')}</h2>
          <HourlyStrip lang={lang} rain={data.rain_next_12h} weather={hours} />
        </section>

        <div className="tile-grid">
          <RainNowTile lang={lang} gauge={gauge} />
          <RiverTile lang={lang} stations={stations.data} ids={data.stations} />
          <TideTile lang={lang} tide={data.tide} dataTime={data.data_time} />
          <ProneTile lang={lang} rating={data.susceptibility} />
        </div>

        <section className="tile">
          <h2 className="tile-title"><Icon name="why" />{t(lang, 'why')}</h2>
          {data.reasons.length ? (
            <ul className="reasons">
              {data.reasons.map((r) => (
                <li key={r.code + r.station}>{r.text[lang]}</li>
              ))}
            </ul>
          ) : (
            <p className="tile-empty">{t(lang, 'noReasons')}</p>
          )}
        </section>

        <section className="tile">
          <h2 className="tile-title"><Icon name="todo" />{t(lang, 'whatToDo')}</h2>
          <p className="tile-text">{t(lang, ADVICE[data.level])}</p>
        </section>

        {river && (
          <section className="tile" aria-labelledby="river-forecast">
            <h2 className="tile-title" id="river-forecast"><Icon name="river" />{t(lang, 'riverForecast')}</h2>
            <p className="tile-text">{river.now}</p>
            <ul className="reasons">
              {river.points.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            {river.warning && <p className="tile-note">{river.warning}</p>}
            {river.mayReachWarning && <p className="tile-text"><strong>{t(lang, 'riverMayReach')}</strong></p>}
            <p className="tile-note">{t(lang, 'riverNote')}</p>
          </section>
        )}

        {verify ? (
          <VerifySheet key={data.active_alert!.alert_id} lang={lang} deviceId={deviceId} streetId={data.street_id} alertId={data.active_alert!.alert_id} mode="verify" />
        ) : (
          <Link to={`/report?street=${encodeURIComponent(data.street_id)}`} className="tile report-card" aria-label={t(lang, 'reportLink')}>
            <span className="report-icon"><Icon name="report" /></span>
            <span>
              <strong>{t(lang, 'reportLink')}</strong>
              <span className="tile-note">{t(lang, 'reportIntro')}</span>
            </span>
          </Link>
        )}

        <AlertHistory history={data.history} lang={lang} />

        <footer className="footer sky-footer">{t(lang, 'footer')}</footer>
      </div>
    </article>
  );
}
