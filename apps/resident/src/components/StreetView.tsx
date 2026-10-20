import { useQuery } from '@tanstack/react-query';
import { useEffect, useId, useRef, type CSSProperties, type KeyboardEvent, type ReactNode } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { LEVEL_LABEL, type Lang, type Level, type Susceptibility } from '@floodready/shared';
import { AlertHistory } from './AlertHistory';
import { BackButton } from './BackButton';
import { Icon, WeatherIcon } from './Icons';
import { SkyBackdrop } from './SkyHero';
import { SkyView } from './SkyView';
import { RainCurve, RiverMeter, TideChart } from './StreetTiles';
import { VerifySheet } from './VerifySheet';
import { adviceSteps } from '../lib/advice';
import { api } from '../lib/api';
import { dayTime, hhmm, metres, percent, riverForecastText } from '../lib/format';
import { t, tf, type StringKey } from '../lib/i18n';
import { bigWord, headline, keyPoints, keyTones, rainStrength, riverGap, riverStatus, weatherPhrase, type Mark, type RiverStatus, type Tone } from '../lib/plain';
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
const RIVER_SHORT: Record<RiverStatus, StringKey> = { low: 'riverLow', near: 'riverNear', alert: 'riverAlert', warning: 'riverWarning', danger: 'riverDanger' };
const MARK_TEXT: Record<Mark, StringKey> = { alert: 'markAlert', warning: 'markWarning', danger: 'markDanger' };
const RAIN_WORD = { none: 'rainNone', light: 'rainLight', moderate: 'rainModerate', heavy: 'rainHeavy' } as const satisfies Record<string, StringKey>;
const RAIN_TONE: Record<'none' | 'light' | 'moderate' | 'heavy', Tone> = { none: 'ok', light: 'ok', moderate: 'watch', heavy: 'warn' };
const PRONE_TONE = (s: Susceptibility): Tone => (s >= 4 ? 'warn' : s === 3 ? 'none' : 'ok');

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
  /** Back link in the top row; the home page has the red map button instead. */
  showBack?: boolean;
  /** Extra control at the top left, e.g. "+ Add to my streets". */
  topLeft?: ReactNode;
  /** Full-width control right under the hero card, e.g. "Change location". */
  belowHero?: ReactNode;
}

/**
 * One street, laid out like a phone weather app: the plain answer first (what it means, what to do,
 * when the rain comes), the numbers last in "Technical details", and the report question at the end.
 * The app header (with the language switch) and the live line sit above it; the replay label is
 * repeated inside the hero card so a replayed street is labelled even on its own.
 */
export function StreetView({ id, lang, deviceId, showBack = true, topLeft, belowHero }: StreetViewProps) {
  // Element ids are prefixed per view, in case two views are ever on one page.
  const uid = useId();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  // The full-screen sky lives in the URL (?view=sky, a history entry), so Back closes it.
  const open = params.get('view') === 'sky';
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
  const rf = data.river_forecast;
  // First forecast hour whose upper estimate reaches the warning line (an estimate, shown as such).
  const reachBy = rf && rf.warning_m !== null ? rf.points.find((p) => p.wl_m_p90 >= rf.warning_m!) ?? null : null;
  const strength = gauge ? rainStrength(gauge.mm) : 'none';
  const rain12 = data.rain_next_12h.reduce((sum, p) => sum + p.mm, 0);
  const rStatus = river ? riverStatus(river.wl, river.th) : null;
  const gap = river ? riverGap(river.wl, river.th) : null;
  const markWord = (m: Mark) => t(lang, MARK_TEXT[m]).toLowerCase();
  const verify = !!data.active_alert && (data.active_alert.level === 'warning' || data.active_alert.level === 'danger');
  const alerting = data.level === 'warning' || data.level === 'danger';
  const word = bigWord(data.level, lang);
  // 64 px like the proposal, smaller for long words ("Berwaspada") so one word never overflows the card.
  const longest = Math.max(...word.split(' ').map((w) => w.length));
  // Heavy rounded letters (lock-screen clock style) are about 0.64 em wide on average.
  const wordSize = Math.min(64, Math.floor(300 / (longest * 0.64)));
  const vars = { '--lvl': SOLID[data.level], '--word': alerting ? TINT[data.level] : '#fff', '--word-size': `${wordSize}px` } as CSSProperties;

  const weatherLine = kind
    ? [t(lang, WX_LABEL[kind]), chance != null ? `${chance}% ${t(lang, 'wxChance')}` : null, phrase].filter(Boolean).join(' · ')
    : null;

  // The panels and the technical details appear on the page and again in the full-screen sky view;
  // `p` prefixes their element ids so the two copies never share an id.
  const panels = (p: string) => (
    <>
      <section className="panel" data-tone={RAIN_TONE[strength]} aria-labelledby={`${p}-rain-panel`}>
        <header className="panel-head">
          <span className="panel-icon"><Icon name="drop" /></span>
          <h2 id={`${p}-rain-panel`}>{t(lang, 'panelRain')}</h2>
        </header>
        <p className="panel-big">{t(lang, RAIN_WORD[strength])}</p>
        <p className="panel-line">{gauge ? tf(lang, 'rainLastHour', { mm: gauge.mm }) : t(lang, GAUGE_TEXT.none)}</p>
        <p className="panel-note">{tf(lang, 'rainNext12', { mm: rain12.toFixed(1) })}</p>
      </section>

      <div className="panel-pair">
        <section className="panel" data-tone={rStatus ? tones.river : 'none'} aria-labelledby={`${p}-river-panel`}>
          <header className="panel-head">
            <span className="panel-icon"><Icon name="river" /></span>
            <h2 id={`${p}-river-panel`}>{t(lang, 'panelRiver')}</h2>
            {rStatus && <span className="panel-chip">{t(lang, RIVER_SHORT[rStatus])}</span>}
          </header>
          {river && gap && station ? (
            <>
              <p className="panel-big">{metres(river.wl)}</p>
              <p className="panel-line">{tf(lang, gap.above ? 'riverAboveMark' : 'riverBelowMark', { m: metres(gap.m), mark: markWord(gap.mark) })}</p>
              <RiverMeter wl={river.wl} th={river.th} />
              <div className="river-marks" aria-hidden="true">
                <span>{t(lang, 'markAlert')}</span><span>{t(lang, 'markWarning')}</span><span>{t(lang, 'markDanger')}</span>
              </div>
              <p className="panel-note">{tf(lang, 'riverAt', { station: station.name })}</p>
            </>
          ) : (
            <p className="panel-line">{t(lang, 'rNone')}</p>
          )}
          {reachBy && <p className="panel-flag">{tf(lang, 'riverMayReachBy', { time: hhmm(reachBy.time) })}</p>}
        </section>

        <section className="panel" data-tone={PRONE_TONE(data.susceptibility)} aria-labelledby={`${p}-street-panel`}>
          <header className="panel-head">
            <span className="panel-icon"><Icon name="home" /></span>
            <h2 id={`${p}-street-panel`}>{t(lang, 'panelStreet')}</h2>
          </header>
          <p className="panel-big">{`${data.susceptibility} / 5`}</p>
          <span className="prone-dots" aria-hidden="true">
            {[1, 2, 3, 4, 5].map((i) => <i key={i} data-on={i <= data.susceptibility || undefined} />)}
          </span>
          <p className="panel-line">{t(lang, proneText(data.susceptibility))}</p>
        </section>
      </div>

      <section className="panel" data-tone="info" aria-labelledby={`${p}-tide-panel`}>
        <header className="panel-head">
          <span className="panel-icon"><Icon name="tide" /></span>
          <h2 id={`${p}-tide-panel`}>{t(lang, 'panelTide')}</h2>
          <span className="panel-sub">{t(lang, 'tidePlace')}</span>
        </header>
        <TideChart lang={lang} tide={data.tide} dataTime={data.data_time} />
      </section>
    </>
  );
  const techBody = (p: string) => (
    <>
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
        <section aria-labelledby={`${p}-river`}>
          <h3 id={`${p}-river`}>{t(lang, 'riverForecast')}</h3>
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
    </>
  );

  return (
    <article className="street" style={vars}>
      {showBack && <BackButton lang={lang} />}
      {topLeft && <div className="street-top">{topLeft}</div>}

      <section className={`hero hero-${sky}`} aria-labelledby={`${uid}-name`}>
        {/* While the full view is open its sky moves instead: only one canvas animates at a time. */}
        <SkyBackdrop sky={sky} active={!open} />
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

      {/* Nothing to do on a Safe street: the card only takes room from Watch up. */}
      {data.level !== 'normal' && (
        <section className="card do" aria-labelledby={`${uid}-do`}>
          <h2 id={`${uid}-do`}>{t(lang, 'doTitle')}</h2>
          <ul className="steps">
            {steps.map((s) => (
              <li key={s.title}><Icon name="check" /><span>{s.title}{s.note && <small>{s.note}</small>}</span></li>
            ))}
          </ul>
        </section>
      )}

      {panels(uid)}

      <section className="card" aria-labelledby={`${uid}-rain`}>
        <h2 id={`${uid}-rain`}>{t(lang, 'curveTitle')}</h2>
        <RainCurve lang={lang} rain={data.rain_next_12h} weather={hours} />
      </section>

      <section className="card tech" aria-labelledby={`${uid}-tech`}>
        <h2 id={`${uid}-tech`}>{t(lang, 'techTitle')}</h2>
        {techBody(uid)}
      </section>

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
        >
          {panels(`${uid}-sky`)}
          <section className="card tech" aria-labelledby={`${uid}-sky-tech`}>
            <h2 id={`${uid}-sky-tech`}>{t(lang, 'techTitle')}</h2>
            {techBody(`${uid}-sky`)}
          </section>
        </SkyView>
      )}
    </article>
  );
}
