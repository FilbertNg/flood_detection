import { useQuery } from '@tanstack/react-query';
import { useEffect, useId, useRef, type CSSProperties, type KeyboardEvent, type ReactNode } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { LEVEL_LABEL, type Lang, type Level, type Susceptibility } from '@floodready/shared';
import { AlertHistory } from './AlertHistory';
import { Icon, WeatherIcon } from './Icons';
import { SkyBackdrop } from './SkyHero';
import { SkyView } from './SkyView';
import { RainCurve, RiverMeter, TideMini } from './StreetTiles';
import { VerifySheet } from './VerifySheet';
import { adviceSteps } from '../lib/advice';
import { api } from '../lib/api';
import { dayTime, metres, percent, riverForecastText } from '../lib/format';
import { t, type StringKey } from '../lib/i18n';
import { bigWord, headline, keyPoints, keyTones, rainStrength, riverStatus, weatherPhrase, type RiverStatus } from '../lib/plain';
import { streetRiver } from '../lib/river';
import { gaugeRain, hourAt, parseWeather, skyFor, weatherKind, weatherUrl, type WeatherKind } from '../lib/weather';

const WX_LABEL: Record<WeatherKind, StringKey> = {
  'clear-day': 'wxClearDay', 'clear-night': 'wxClearNight', 'partly-day': 'wxPartly', 'partly-night': 'wxPartly',
  cloudy: 'wxCloudy', fog: 'wxFog', drizzle: 'wxDrizzle', rain: 'wxRain', storm: 'wxStorm',
};

/** Solid level colours for shapes on white (dot, stripe); never used as text (Watch and Warning are under 4.5:1). */
const SOLID: Record<Level, string> = { normal: '#2e7d32', watch: '#b26a00', warning: '#e65100', danger: '#c62828' };
/** Light tints for the big word on the dark hero sky at Warning and Danger (>= 4.5:1 there). */
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
  /** False for pager panels off screen: the sky stops moving and the 10 s refresh pauses, to save battery. */
  active?: boolean;
  /** Back link in the top row; the swipe home has the red map button instead. */
  showBack?: boolean;
  /** Extra control at the top left, e.g. "+ Add to my streets". */
  topLeft?: ReactNode;
  /** Shown just under the hero card: the pager's page dots. */
  belowHero?: ReactNode;
}

/**
 * One street, laid out like a phone weather app: the plain answer first (what it means, what to do,
 * when the rain comes), the numbers last in "Technical details", and the report question at the end.
 * The app header (with the language switch) and the live line sit above it; the replay label is
 * repeated inside the hero card so a replayed street is labelled even on its own.
 */
export function StreetView({ id, lang, deviceId, active = true, showBack = true, topLeft, belowHero }: StreetViewProps) {
  // Element ids are prefixed per view: up to three pager panels are on the page at once.
  const uid = useId();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  // The full-screen sky lives in the URL (?view=sky, a history entry), so Back closes it. Only the
  // visible street opens it.
  const open = active && params.get('view') === 'sky';
  const pushed = useRef(false);
  const opener = useRef<HTMLDivElement>(null);
  const openFull = () => {
    pushed.current = true;
    setParams((p) => { p.set('view', 'sky'); return p; });
  };
  const closeFull = () => {
    if (pushed.current) {
      pushed.current = false;
      navigate(-1);
    } else {
      setParams((p) => { p.delete('view'); return p; }, { replace: true });
    }
  };
  const onOpenerKey = (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openFull(); }
  };
  // Escape closes the full view.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: globalThis.KeyboardEvent) => { if (e.key === 'Escape') closeFull(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  });
  // Focus goes back to the hero card when the full view closes (by ×, Escape or Back).
  const wasOpen = useRef(false);
  useEffect(() => {
    if (wasOpen.current && !open) {
      pushed.current = false;
      opener.current?.focus();
    }
    wasOpen.current = open;
  }, [open]);
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
  const tones = keyTones({ level: data.level, gauge, hours, dataTime: data.data_time, river });
  const steps = adviceSteps(data.level, data.susceptibility, data.window, lang);
  const forecast = riverForecastText(data.river_forecast, lang);
  const verify = !!data.active_alert && (data.active_alert.level === 'warning' || data.active_alert.level === 'danger');
  const alerting = data.level === 'warning' || data.level === 'danger';
  const word = bigWord(data.level, lang);
  // 64 px like the proposal, smaller for long words ("Berwaspada") so one word never overflows the card.
  const longest = Math.max(...word.split(' ').map((w) => w.length));
  const wordSize = Math.min(64, Math.floor(300 / (longest * 0.55)));
  const vars = { '--lvl': SOLID[data.level], '--word': alerting ? TINT[data.level] : '#fff', '--word-size': `${wordSize}px` } as CSSProperties;

  const weatherLine = kind
    ? [t(lang, WX_LABEL[kind]), chance != null ? `${chance}% ${t(lang, 'wxChance')}` : null, phrase].filter(Boolean).join(' · ')
    : null;

  return (
    <article className="street" style={vars}>
      {showBack && <Link to="/" className="back">← {t(lang, 'back')}</Link>}
      {topLeft && <div className="street-top">{topLeft}</div>}

      <section className={`hero hero-${sky}`} aria-labelledby={`${uid}-name`}>
        {/* While the full view is open its sky moves instead: only one canvas animates at a time. */}
        <SkyBackdrop sky={sky} active={active && !open} />
        <div className="hero-top">
          <span className="hero-label">{t(lang, 'yourStreet')}</span>
          <span className="level-pill"><i aria-hidden="true" />{LEVEL_LABEL[lang][data.level]}</span>
        </div>
        {data.is_replay && <p className="hero-replay"><span aria-hidden="true">▶ </span>{t(lang, 'replayChip')}</p>}
        <h1 className="hero-name" id={`${uid}-name`}>{data.name}</h1>
        <p className="hero-word">{word}</p>
        <p className="hero-headline">{headline(data.level, data.window, lang)}</p>
        {kind && weatherLine && (
          <p className="hero-weather">
            <WeatherIcon kind={kind} />
            <span>{weatherLine}</span>
          </p>
        )}
        <span className="hero-more" aria-hidden="true">{t(lang, 'detailsChip')}</span>
        {/* A layer over the whole card opens the full view. It is not the card itself, so the street
            name stays a real heading for screen readers. */}
        <div ref={opener} className="hero-open" role="button" tabIndex={0} aria-label={t(lang, 'heroOpen')} onClick={openFull} onKeyDown={onOpenerKey} />
      </section>
      {belowHero}

      <div className="keys">
        {([['keyRain', keys.rain, tones.rain, 'drop'], ['keyRiver', keys.river, tones.river, 'river'], ['keyFlood', keys.flood, tones.flood, 'home']] as const).map(([label, value, tone, icon]) => (
          <div key={label} className="key" data-tone={tone}>
            <Icon name={icon} />
            <b>{t(lang, label)}</b>
            <span>{value}</span>
          </div>
        ))}
      </div>

      <section className="card do" aria-labelledby={`${uid}-do`}>
        <h2 id={`${uid}-do`}>{t(lang, 'doTitle')}</h2>
        <ul className="steps">
          {steps.map((s) => (
            <li key={s.title}><Icon name="check" /><span>{s.title}{s.note && <small>{s.note}</small>}</span></li>
          ))}
        </ul>
      </section>

      <section className="card" aria-labelledby={`${uid}-rain`}>
        <h2 id={`${uid}-rain`}>{t(lang, 'curveTitle')}</h2>
        <RainCurve lang={lang} rain={data.rain_next_12h} weather={hours} />
      </section>

      <section className="card" aria-labelledby={`${uid}-now`}>
        <h2 id={`${uid}-now`}>{t(lang, 'streetNow')}</h2>
        <ul className="rows">
          <li><b>{t(lang, 'rowRain')}</b><span>{t(lang, GAUGE_TEXT[gauge ? rainStrength(gauge.mm) : 'none'])}</span></li>
          <li><b>{t(lang, 'rowRiver')}</b><span>{river ? t(lang, RIVER_TEXT[riverStatus(river.wl, river.th)]) : t(lang, 'rNone')}</span></li>
          <li><b>{t(lang, 'rowStreet')}</b><span>{t(lang, proneText(data.susceptibility))}</span><em>{data.susceptibility} / 5</em></li>
        </ul>
      </section>

      <details className="card tech">
        <summary>
          <span>{t(lang, 'techTitle')}</span>
          <span className="tech-toggle" aria-hidden="true" />
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
          <section aria-labelledby={`${uid}-river`}>
            <h3 id={`${uid}-river`}>{t(lang, 'riverForecast')}</h3>
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
        <Link to={`/report?street=${encodeURIComponent(data.street_id)}`} className="card report-card" aria-label={t(lang, 'reportLink')}>
          <span className="report-icon"><Icon name="report" /></span>
          <span>
            <strong>{t(lang, 'reportLink')}</strong>
            <span className="tile-note">{t(lang, 'reportIntro')}</span>
          </span>
        </Link>
      )}

      <footer className="footer">{t(lang, 'footer')}</footer>

      {open && (
        <SkyView
          lang={lang}
          sky={sky}
          name={data.name}
          level={data.level}
          word={word}
          headline={headline(data.level, data.window, lang)}
          kind={kind}
          weatherLine={weatherLine}
          keys={keys}
          rain={data.rain_next_12h}
          hours={hours}
          vars={vars}
          onClose={closeFull}
        />
      )}
    </article>
  );
}
