import { useQuery } from '@tanstack/react-query';
import type { CSSProperties, ReactNode } from 'react';
import { Link } from 'react-router';
import { LEVEL_LABEL, type Lang, type Level, type Susceptibility } from '@floodready/shared';
import { AlertHistory } from './AlertHistory';
import { Icon, WeatherIcon } from './Icons';
import { LangSwitch } from './LangSwitch';
import { SkyBackdrop } from './SkyHero';
import { RainCurve, RiverMeter, TideMini } from './StreetTiles';
import { VerifySheet } from './VerifySheet';
import { adviceSteps } from '../lib/advice';
import { api } from '../lib/api';
import { dayTime, metres, percent, riverForecastText } from '../lib/format';
import { t, type StringKey } from '../lib/i18n';
import { bigWord, headline, keyPoints, rainStrength, riverStatus, weatherPhrase, type RiverStatus } from '../lib/plain';
import { streetRiver } from '../lib/river';
import { gaugeRain, hourAt, parseWeather, skyFor, weatherKind, weatherUrl, type WeatherKind } from '../lib/weather';

const WX_LABEL: Record<WeatherKind, StringKey> = {
  'clear-day': 'wxClearDay', 'clear-night': 'wxClearNight', 'partly-day': 'wxPartly', 'partly-night': 'wxPartly',
  cloudy: 'wxCloudy', fog: 'wxFog', drizzle: 'wxDrizzle', rain: 'wxRain', storm: 'wxStorm',
};

/** Level tints for the dot and big word on the dark sky (the text label stays the official level). */
const TINT: Record<Level, string> = { normal: '#7ee0a1', watch: '#ffd166', warning: '#ff9f43', danger: '#ff5d5d' };

const GAUGE_TEXT = { none: 'gNone', light: 'gLight', moderate: 'gModerate', heavy: 'gHeavy' } as const satisfies Record<string, StringKey>;
const RIVER_TEXT: Record<RiverStatus, StringKey> = { low: 'rLow', near: 'rNear', alert: 'rAlert', warning: 'rWarning', danger: 'rDanger' };

const proneText = (s: Susceptibility): StringKey => (s >= 4 ? 'streetProne' : s === 3 ? 'streetMid' : 'streetLow');

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

export interface StreetViewProps {
  id: string;
  lang: Lang;
  deviceId: string;
  onLang?: (lang: Lang) => void;
  /** False for pager panels off screen: the sky stops moving and the 10 s refresh pauses, to save battery. */
  active?: boolean;
  /** Back link in the top row; the swipe home navigates with its bottom bar instead. */
  showBack?: boolean;
  /** Extra control at the top left, e.g. "+ Add to my streets". */
  topLeft?: ReactNode;
}

/**
 * One street, laid out like a phone weather app: the plain answer first (what it means, what to do,
 * when the rain comes), the numbers last in "Technical details", and the report question at the end.
 * Full screen: the app header and live strip are hidden, so the view carries its own top row
 * (language, replay label, and Back or a page action).
 */
export function StreetView({ id, lang, deviceId, onLang, active = true, showBack = true, topLeft }: StreetViewProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['street', id],
    queryFn: () => api.street(id),
    refetchInterval: active ? 10_000 : false,
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
    refetchInterval: active ? 60_000 : false,
  });

  if (isLoading) return <p className="pad">{t(lang, 'loading')}</p>;
  if (isError || !data) return <p className="pad">{t(lang, 'error')}</p>;

  const hours = weather.data ?? null;
  const nowHour = hourAt(hours, data.data_time);
  const kind = nowHour ? weatherKind(nowHour.code, nowHour.isDay) : null;
  const gauge = gaugeRain(stations.data, data.stations);
  const sky = skyFor(data.level, kind, gauge);
  const chance = nowHour?.rainChance;
  const phrase = weatherPhrase(hours, data.data_time, lang);
  const station = streetRiver(stations.data, data.stations);
  const wl = station?.latest?.wl_m ?? null;
  const th = station?.thresholds ?? null;
  const river = wl !== null && th ? { wl, th } : null;
  const keys = keyPoints({ lang, level: data.level, window: data.window, gauge, hours, dataTime: data.data_time, river });
  const steps = adviceSteps(data.level, data.susceptibility, data.window, lang);
  const forecast = riverForecastText(data.river_forecast, lang);
  const verify = !!data.active_alert && (data.active_alert.level === 'warning' || data.active_alert.level === 'danger');
  const alerting = data.level === 'warning' || data.level === 'danger';
  const word = bigWord(data.level, lang);
  // 88 px like the prototype, smaller for long words ("Berwaspada") so one word never overflows a phone.
  const longest = Math.max(...word.split(' ').map((w) => w.length));
  const wordSize = Math.min(88, Math.floor(330 / (longest * 0.55)));
  const vars = { '--lvl': TINT[data.level], '--word': alerting ? TINT[data.level] : '#fff', '--word-size': `${wordSize}px` } as CSSProperties;

  const weatherLine = kind
    ? [t(lang, WX_LABEL[kind]), chance != null ? `${chance}% ${t(lang, 'wxChance')}` : null, phrase].filter(Boolean).join(' · ')
    : null;

  return (
    <article className={`street sky-page sky-page-${sky}`} style={vars}>
      <SkyBackdrop sky={sky} active={active} />
      <div className="sky-content">
        <div className="sky-top">
          {showBack ? <Link to="/" className="back">← {t(lang, 'back')}</Link> : (topLeft ?? <span />)}
          {onLang && <LangSwitch lang={lang} onChange={onLang} />}
        </div>
        {data.is_replay && <p className="sky-replay"><span aria-hidden="true">▶ </span>{t(lang, 'replayChip')}</p>}

        <header className="sky-hero">
          <h1>{data.name}</h1>
          <div className="sky-status"><span className="sky-dot" aria-hidden="true" />{LEVEL_LABEL[lang][data.level]}</div>
          <p className="sky-word">{word}</p>
          <p className="sky-headline">{headline(data.level, data.window, lang)}</p>
          {kind && weatherLine && (
            <p className="sky-weather">
              <WeatherIcon kind={kind} />
              <span>{weatherLine}</span>
            </p>
          )}
        </header>

        <div className="sky-keys">
          {([['keyRain', keys.rain], ['keyRiver', keys.river], ['keyFlood', keys.flood]] as const).map(([label, value]) => (
            <div key={label} className="sky-key"><b>{t(lang, label)}</b><span>{value}</span></div>
          ))}
        </div>

        <section className="glass do" aria-labelledby="do-now">
          <h2 id="do-now">{t(lang, 'doTitle')}</h2>
          <ul className="steps">
            {steps.map((s) => (
              <li key={s.title}><span>{s.title}{s.note && <small>{s.note}</small>}</span></li>
            ))}
          </ul>
        </section>

        <section className="sky-curve" aria-labelledby="rain-curve">
          <h2 id="rain-curve">{t(lang, 'curveTitle')}</h2>
          <RainCurve lang={lang} rain={data.rain_next_12h} weather={hours} />
        </section>

        <section className="glass" aria-labelledby="street-now">
          <h2 id="street-now">{t(lang, 'streetNow')}</h2>
          <ul className="rows">
            <li><b>{t(lang, 'rowRain')}</b><span>{t(lang, GAUGE_TEXT[gauge ? rainStrength(gauge.mm) : 'none'])}</span></li>
            <li><b>{t(lang, 'rowRiver')}</b><span>{river ? t(lang, RIVER_TEXT[riverStatus(river.wl, river.th)]) : t(lang, 'rNone')}</span></li>
            <li><b>{t(lang, 'rowStreet')}</b><span>{t(lang, proneText(data.susceptibility))}</span><em>{data.susceptibility} / 5</em></li>
          </ul>
        </section>

        <details className="glass tech">
          <summary>
            <span>{t(lang, 'techTitle')}</span>
            <span className="tech-toggle"><span className="tech-show">{t(lang, 'techShow')}</span><span className="tech-hide">{t(lang, 'techHide')}</span></span>
          </summary>
          {station && wl !== null && (
            <>
              <div className="tech-river"><strong>{metres(wl)}</strong><span>{station.name}</span></div>
              {th && <RiverMeter wl={wl} th={th} />}
            </>
          )}
          <ul className="rows">
            {th && (
              <li><b>{t(lang, 'techMarks')}</b><span>{`${t(lang, 'markAlert')} ${th.alert.toFixed(2)} · ${t(lang, 'markWarning')} ${th.warning.toFixed(2)} · ${t(lang, 'markDanger')} ${th.danger.toFixed(2)} m`}</span></li>
            )}
            <li><b>{t(lang, 'techRainHour')}</b><span>{gauge ? gauge.station : t(lang, 'techGauge')}</span><em>{gauge ? `${gauge.mm} mm` : '0 mm'}</em></li>
            {data.flood_probability !== null && (
              <li><b>{t(lang, 'techModel')}</b><span>{t(lang, 'chance')}</span><em>{percent(data.flood_probability)}</em></li>
            )}
          </ul>
          {data.flood_probability !== null && <p className="fine">{t(lang, 'mlNote')}</p>}

          <h3>{t(lang, 'tide')}</h3>
          <TideMini lang={lang} tide={data.tide} dataTime={data.data_time} />

          <h3>{t(lang, 'why')}</h3>
          {data.reasons.length ? (
            <ul className="reasons">
              {data.reasons.map((r) => (
                <li key={r.code + r.station}>{r.text[lang]}</li>
              ))}
            </ul>
          ) : (
            <p className="fine">{t(lang, 'noReasons')}</p>
          )}

          {forecast && (
            <section aria-labelledby="river-forecast">
              <h3 id="river-forecast">{t(lang, 'riverForecast')}</h3>
              <p className="fine">{forecast.now}</p>
              <ul className="reasons">
                {forecast.points.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              {forecast.warning && <p className="fine">{forecast.warning}</p>}
              {forecast.mayReachWarning && <p className="fine"><strong>{t(lang, 'riverMayReach')}</strong></p>}
              <p className="fine">{t(lang, 'riverNote')}</p>
            </section>
          )}

          <p className="fine">
            {t(lang, 'dataTime')} {dayTime(data.data_time)} · {t(lang, 'techSources')}
            {kind && <> · <span>{t(lang, 'wxCredit')}</span></>}
          </p>
        </details>

        <AlertHistory history={data.history} lang={lang} />

        {verify ? (
          <VerifySheet key={data.active_alert!.alert_id} lang={lang} deviceId={deviceId} streetId={data.street_id} alertId={data.active_alert!.alert_id} mode="verify" />
        ) : (
          <Link to={`/report?street=${encodeURIComponent(data.street_id)}`} className="glass report-card" aria-label={t(lang, 'reportLink')}>
            <span className="report-icon"><Icon name="report" /></span>
            <span>
              <strong>{t(lang, 'reportLink')}</strong>
              <span className="tile-note">{t(lang, 'reportIntro')}</span>
            </span>
          </Link>
        )}

        <footer className="footer sky-footer">{t(lang, 'footer')}</footer>
      </div>
    </article>
  );
}
