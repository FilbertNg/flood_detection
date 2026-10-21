import { useId, useRef, useState, type KeyboardEvent } from 'react';
import type { Lang, StreetDetail } from '@floodready/shared';
import { CURVE, chanceColor, curvePoints, curveRuns } from '../lib/curve';
import { hhmm } from '../lib/format';
import { t, tf, type StringKey } from '../lib/i18n';
import { riverScale, type Thresholds } from '../lib/river';
import { tideIndexAt, tideTrend, tideTurns } from '../lib/tide';
import { weatherKind, type WeatherHour } from '../lib/weather';
import { WeatherIcon } from './Icons';

/** SDP card colours for the curve: blue line, grey labels, the Now point ringed in brand red. */
const BLUE = '#3b82c4';
const MUTED = '#666666';
const RED = '#d71920';
const INK = '#121212';

/**
 * "Rain in the next 12 hours": a scrolling curve of Open-Meteo's chance of rain over the hours our
 * API forecasts, with our mm under each hour. An hour with no chance breaks the line (no guessing).
 * `card`: the SDP white card (blue line, grey labels, red-ringed Now). `sky`: white on the full-screen
 * sky (blue to amber to orange line, white Now bubble).
 */
export function RainCurve({ lang, rain, weather, tone = 'card' }: { lang: Lang; rain: StreetDetail['rain_next_12h']; weather: WeatherHour[] | null; tone?: 'card' | 'sky' }) {
  // Gradient ids per curve: the card and the full view can be on the page at once.
  const fillId = useId();
  const strokeId = useId();
  if (rain.length === 0) return <p className="tile-empty">{t(lang, 'noForecast')}</p>;
  const hours = rain.map((p) => weather?.find((h) => h.hour === p.time.slice(0, 13)) ?? null);
  const points = curvePoints(hours.map((h) => h?.rainChance ?? null));
  const runs = curveRuns(points);
  const width = CURVE.col * rain.length, H = CURVE.height;
  const mid = CURVE.top + 0.5 * (H - CURVE.top - CURVE.bottom);
  const now = points[0];
  const sky = tone === 'sky';
  const fill = sky ? '#fff' : BLUE;
  const label = sky ? '#fff' : MUTED;
  let last = chanceColor(0);
  const stops = points.map((p, i) => {
    if (p.chance !== null) last = chanceColor(p.chance);
    return <stop key={i} offset={`${rain.length > 1 ? (i / (rain.length - 1)) * 100 : 0}%`} stopColor={last} />;
  });

  return (
    <div className="curve-scroll">
      <div className="curve-track" style={{ width }}>
        <svg width={width} height={H} viewBox={`0 0 ${width} ${H}`} aria-hidden="true" className="curve-svg">
          <defs>
            <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor={fill} stopOpacity="0.18" />
              <stop offset="1" stopColor={fill} stopOpacity="0" />
            </linearGradient>
            {sky && <linearGradient id={strokeId} x1="0" x2="1">{stops}</linearGradient>}
          </defs>
          <line data-guide x1={0} x2={width} y1={mid} y2={mid} stroke={label} strokeOpacity={sky ? 0.22 : 0.35} strokeDasharray={sky ? '4 5' : '3 5'} />
          {runs.map((run) => (
            <g key={run.d}>
              <path d={`${run.d} L${run.x1},${H} L${run.x0},${H} Z`} fill={`url(#${fillId})`} />
              <path data-line d={run.d} fill="none" stroke={sky ? `url(#${strokeId})` : BLUE} strokeWidth={sky ? 3 : 2.5} strokeLinecap="round" />
            </g>
          ))}
          {points.slice(1).map((p, i) => p.y !== null && (
            <text key={i} data-pct x={p.x} y={p.y - 8} textAnchor="middle" fontSize="11" fontWeight="700" fill={label}>{`${p.chance}%`}</text>
          ))}
          {now.y !== null && (
            <g data-now>
              <circle cx={now.x} cy={now.y} r={15} fill="#fff" stroke={sky ? chanceColor(now.chance!) : RED} strokeWidth={sky ? 3 : 2.5} />
              <text x={now.x} y={now.y + 4.5} textAnchor="middle" fontSize="12" fontWeight="800" fill={INK}>{`${now.chance}%`}</text>
            </g>
          )}
        </svg>
        <ol className="curve-hours">
          {rain.map((p, i) => {
            const w = hours[i];
            return (
              <li key={p.time} className={i === 0 ? 'now' : undefined}>
                <span className="curve-icon">{w ? <WeatherIcon kind={weatherKind(w.code, w.isDay)} tone={sky ? 'sky' : 'card'} /> : null}</span>
                <span>{i === 0 ? t(lang, 'nowLabel') : hhmm(p.time)}</span>
                <span className="curve-mm">{p.mm} mm</span>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

/** River level on a bar with the JPS alert, warning and danger bands. */
export function RiverMeter({ wl, th }: { wl: number; th: Thresholds }) {
  const at = riverScale(th);
  return (
    <div className="river-gauge" aria-hidden="true">
      <span className="river-band band-alert" style={{ left: `${at(th.alert)}%`, width: `${at(th.warning) - at(th.alert)}%` }} />
      <span className="river-band band-warning" style={{ left: `${at(th.warning)}%`, width: `${at(th.danger) - at(th.warning)}%` }} />
      <span className="river-band band-danger" style={{ left: `${at(th.danger)}%`, right: 0 }} />
      <span className="river-now" style={{ left: `${at(wl)}%` }} />
    </div>
  );
}

type Stage = 'safe' | 'alert' | 'danger';
const STAGES: { stage: Stage; key: StringKey }[] = [
  { stage: 'safe', key: 'stageSafe' }, { stage: 'alert', key: 'stageAlert' }, { stage: 'danger', key: 'stageDanger' },
];
const BARS = 4;

/**
 * Signal bars lit towards a mark: none 3 alert-to-danger spans or more below it (the river meter's
 * floor), one more per quarter of that distance, all four once the river reaches the mark.
 */
function barsTowards(wl: number | null, mark: number, th: Thresholds): number {
  if (wl === null) return 0;
  if (wl >= mark) return BARS;
  const near = 1 - (mark - wl) / (3 * (th.danger - th.alert));
  return Math.min(BARS - 1, Math.max(0, Math.floor(near * BARS)));
}

/** All lit bars share one colour, set by how many are lit. */
const barTier = (n: number) => (n === 0 ? 'none' : n === 1 ? 'ok' : n === 2 ? 'watch' : 'danger');

/**
 * Where the water marker sits on the danger gauge (0 to 100): three equal steps, Safe up to the alert
 * mark (from the river meter's floor), Be alert up to danger, Danger up to the meter's top.
 */
function gaugeAt(wl: number, th: Thresholds): number {
  const span = th.danger - th.alert;
  const steps: [number, number][] = [[th.alert - 3 * span, th.alert], [th.alert, th.danger], [th.danger, th.danger + 0.75 * span]];
  const i = wl >= th.danger ? 2 : wl >= th.alert ? 1 : 0;
  const [lo, hi] = steps[i];
  return ((i + Math.min(1, Math.max(0, (wl - lo) / (hi - lo)))) / 3) * 100;
}

const metresTo = (m: number) => `${Math.abs(m).toFixed(2)} m`;

/**
 * The JPS marks for the street's river. Alert and Warning side by side: the mark, signal bars that fill
 * as the river nears it, and how far below it the river is. Danger: one gauge in three steps (Safe,
 * Be alert, Danger) filled up to a water marker, the current step marked "Now".
 * Display only: the street level comes from the engine.
 */
export function JpsMarks({ lang, wl, th }: { lang: Lang; wl: number | null; th: Thresholds }) {
  const stage: Stage | null = wl === null ? null : wl >= th.danger ? 'danger' : wl >= th.alert ? 'alert' : 'safe';
  const signal = (mark: 'alert' | 'warning', key: StringKey) => {
    const n = barsTowards(wl, th[mark], th);
    const name = t(lang, key);
    return (
      <div className="mark-tile" data-mark={mark}>
        <span className="mark-name">{name}</span>
        <span className="signal" data-tier={barTier(n)} role="img" aria-label={tf(lang, 'marksBars', { n, mark: name.toLowerCase() })}>
          {Array.from({ length: BARS }, (_, i) => <i key={i} data-bar data-on={i < n || undefined} />)}
        </span>
        <strong className="mark-m">{`${th[mark].toFixed(2)} m`}</strong>
        <span className="mark-gap" data-tier={barTier(n)}>
          {wl === null ? t(lang, 'rNone') : wl >= th[mark] ? t(lang, 'marksReached') : tf(lang, 'marksBelow', { m: metresTo(th[mark] - wl) })}
        </span>
      </div>
    );
  };
  const at = wl === null ? null : gaugeAt(wl, th);
  return (
    <div className="jps-marks">
      <div className="mark-pair">
        {signal('alert', 'markAlert')}
        {signal('warning', 'markWarning')}
      </div>
      <div className="gauge" data-mark="danger" data-stage-now={stage ?? undefined}>
        <div className="gauge-head">
          <span className="mark-name">{t(lang, 'markDanger')}</span>
          <strong className="mark-m">{`${th.danger.toFixed(2)} m`}</strong>
        </div>
        <div className="gauge-track" aria-hidden="true">
          {at !== null && <span className="gauge-fill" style={{ width: `${at}%` }} />}
          {at !== null && <span className="gauge-marker" style={{ left: `${at}%` }} />}
        </div>
        <div className="gauge-ticks" aria-hidden="true">
          <span style={{ left: `${100 / 3}%` }}>{th.alert.toFixed(2)}</span>
          <span style={{ left: `${200 / 3}%` }}>{th.danger.toFixed(2)}</span>
        </div>
        <ol className="gauge-steps">
          {STAGES.map(({ stage: s, key }) => (
            <li key={s} data-stage={s} aria-current={s === stage ? 'true' : undefined}>
              <span>{t(lang, key)}</span>
              {s === stage && <small>{t(lang, 'nowLabel')}</small>}
            </li>
          ))}
        </ol>
        <p className="gauge-note">
          {wl === null ? t(lang, 'rNone') : tf(lang, wl >= th.danger ? 'dangerAbove' : 'dangerBelow', { m: metresTo(th.danger - wl) })}
        </p>
      </div>
    </div>
  );
}

/**
 * One reading in Technical details: a label, the number large, a meaning line and where it comes from.
 * `meter` (0 to 100) draws a thin bar under the number.
 */
export function Reading({ label, value, meaning, source, meter, meterLabel }: {
  label: string; value: string; meaning?: string; source: string; meter?: number; meterLabel?: string;
}) {
  return (
    <div className="reading">
      <span className="reading-label">{label}</span>
      <strong className="reading-value">{value}</strong>
      {meter !== undefined && (
        <span className="reading-meter" role="meter" aria-label={meterLabel ?? label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(meter)}>
          <i style={{ width: `${Math.min(100, Math.max(0, meter))}%` }} />
        </span>
      )}
      {meaning && <span className="reading-meaning">{meaning}</span>}
      <span className="reading-source">{source}</span>
    </div>
  );
}

/** A clock time n fractional hours after an ISO time, as "14:30" (MYT, the API's offset; wraps past midnight). */
function clockAfter(iso: string, hours: number): string {
  const start = Number(iso.slice(11, 13)) * 60 + Number(iso.slice(14, 16));
  const m = (((start + Math.round(hours * 60)) % 1440) + 1440) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
}

/** Pin steps: a drag snaps to 15 minutes, an arrow key moves 30 minutes. */
const SNAP = 0.25, KEY_STEP = 0.5;

/**
 * Port Klang tide over the hours the API sends: a filled curve with the hours along the bottom and the
 * next high and low water marked with their heights.
 *
 * One red pin starts on now and can be dragged along the curve (or moved with the arrow keys; it is a
 * slider): its tag and the readout above show the time, the height there and whether the water is rising
 * or falling, and "next high tide" is counted from the pin. "Back to now" returns it. Heights between the
 * hourly points are read off the straight line between them, as the curve is drawn.
 */
export function TideChart({ lang, tide: all, dataTime }: { lang: Lang; tide: StreetDetail['tide']; dataTime: string }) {
  const fillId = useId();
  const [pin, setPin] = useState<number | null>(null);
  // 6 h: from the current hour; 12 h: all the API sends (issue time to +12 h).
  const [range, setRange] = useState<6 | 12>(12);
  const dragging = useRef(false);
  const start = Math.floor(tideIndexAt(all, dataTime));
  const tide = range === 6 ? all.slice(start, start + 7) : all;
  if (tide.length < 2) return <p className="tile-empty">{t(lang, 'noTide')}</p>;
  const last = tide.length - 1;
  const now = tideIndexAt(tide, dataTime);
  const at = pin ?? now;
  const { high, low } = tideTurns(tide, now);
  const next = tideTurns(tide, at).high;
  const trend = tideTrend(tide, at);

  // Plot box inside the viewBox; the side padding keeps the Now dot and the end labels inside the card.
  const W = 320, H = 168, L = 14, R = 14, TOP = 44, BOTTOM = 42;
  const ys = tide.map((p) => p.height_m);
  const lo = Math.min(...ys), hi = Math.max(...ys), span = hi - lo || 1;
  const x = (i: number) => L + (i / last) * (W - L - R);
  const y = (v: number) => TOP + (1 - (v - lo) / span) * (H - TOP - BOTTOM);
  const heightAt = (i: number) => {
    const a = Math.floor(i), b = Math.min(a + 1, last);
    return ys[a] + (ys[b] - ys[a]) * (i - a);
  };
  const line = tide.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.height_m).toFixed(1)}`).join(' ');
  const area = `${line} L${x(last).toFixed(1)},${H - BOTTOM} L${x(0).toFixed(1)},${H - BOTTOM} Z`;
  const step = Math.max(1, Math.ceil(last / 4));
  const px = x(at), py = y(heightAt(at));
  const anchor = (i: number) => (i === 0 ? 'start' : i === last ? 'end' : 'middle');
  const metresLabel = (v: number) => `${v.toFixed(1).replace('-', '−')} m`;

  const when = pin === null ? t(lang, 'nowLabel') : clockAfter(tide[0].time, at);
  const trendText = trend ? t(lang, trend === 'rising' ? 'tideRising' : 'tideFalling') : null;
  const valueText = [pin === null ? clockAfter(tide[0].time, now) : when, metresLabel(heightAt(at)), trendText].filter(Boolean).join(' · ');

  const clamp = (i: number) => Math.min(last, Math.max(0, i));
  // Pointer x on the drawn chart to a pin position, snapped to 15 minutes; an unreadable x moves nothing.
  const pinTo = (el: Element, clientX: number) => {
    const box = el.getBoundingClientRect();
    const vx = ((clientX - box.left) / (box.width || 1)) * W;
    const i = Math.round((((vx - L) / (W - L - R)) * last) / SNAP) * SNAP;
    if (Number.isFinite(i)) setPin(clamp(i));
  };
  const onKey = (e: KeyboardEvent<SVGSVGElement>) => {
    const moves: Record<string, number> = { ArrowRight: at + KEY_STEP, ArrowUp: at + KEY_STEP, ArrowLeft: at - KEY_STEP, ArrowDown: at - KEY_STEP, Home: 0, End: last };
    if (!(e.key in moves)) return;
    e.preventDefault();
    setPin(clamp(moves[e.key]));
  };

  return (
    <>
      <div className="tide-range" role="group" aria-label={t(lang, 'tideRange')}>
        {([6, 12] as const).map((h) => (
          <button key={h} type="button" aria-pressed={range === h} onClick={() => { setRange(h); setPin(null); }}>{`${h} ${t(lang, 'tideHours')}`}</button>
        ))}
      </div>
      <p className="tide-readout" aria-hidden="true">
        <strong>{when}</strong>
        <span>{metresLabel(heightAt(at))}</span>
        {trend && <span className="tide-trend" data-trend={trend}>{trendText}</span>}
      </p>
      <svg
        viewBox={`0 0 ${W} ${H}`} className="tide-chart" role="slider" tabIndex={0}
        aria-label={t(lang, 'tideScrub')} aria-valuemin={0} aria-valuemax={last} aria-valuenow={at} aria-valuetext={valueText}
        onKeyDown={onKey}
        // preventDefault: a press drags the pin without taking keyboard focus (no focus ring after a drag).
        onPointerDown={(e) => { e.preventDefault(); dragging.current = true; e.currentTarget.setPointerCapture?.(e.pointerId); pinTo(e.currentTarget, e.clientX); }}
        onPointerMove={(e) => { if (dragging.current) pinTo(e.currentTarget, e.clientX); }}
        onPointerUp={() => { dragging.current = false; }}
        onPointerCancel={() => { dragging.current = false; }}
      >
        <defs>
          <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={BLUE} stopOpacity="0.28" />
            <stop offset="1" stopColor={BLUE} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <line x1={L} x2={W - R} y1={H - BOTTOM} y2={H - BOTTOM} stroke="#e4e4e4" />
        <path d={area} fill={`url(#${fillId})`} />
        <path d={line} fill="none" stroke={BLUE} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {[high, low].map((i, k) => i !== null && (
          <g key={k} data-turn={k ? 'low' : 'high'}>
            <circle cx={x(i)} cy={y(ys[i])} r="3.5" fill={BLUE} />
            <text x={Math.min(Math.max(x(i), L + 14), W - R - 14)} y={k ? y(ys[i]) + 16 : y(ys[i]) - 9} textAnchor="middle" fontSize="11" fontWeight="700" fill={INK}>{metresLabel(ys[i])}</text>
          </g>
        ))}
        {/* The one red pin: on now until dragged; its tag says "Now" or the time it reads. */}
        <g data-pin data-now={pin === null || undefined}>
          <line x1={px} x2={px} y1={20} y2={H - BOTTOM} stroke={RED} strokeWidth="1.5" strokeDasharray={pin === null ? '3 3' : undefined} />
          <rect x={Math.min(Math.max(px - 21, 0), W - 42)} y={2} width={42} height={16} rx={8} fill={RED} />
          <text x={Math.min(Math.max(px, 21), W - 21)} y={13.5} textAnchor="middle" fontSize="10" fontWeight="800" fill="#fff">{when}</text>
          <circle cx={px} cy={py} r="7" fill="#fff" stroke={RED} strokeWidth="3" />
        </g>
        {tide.map((p, i) => (i % step === 0 || i === last) && (i === last || last - i >= step / 2) && (
          <text key={p.time} data-hour x={x(i)} y={H - 6} textAnchor={anchor(i)} fontSize="11" fill={MUTED}>{hhmm(p.time)}</text>
        ))}
      </svg>
      <div className="tide-facts">
        {next !== null && <span className="tile-note">{`${t(lang, 'highTide')} ${hhmm(tide[next].time)} · ${tide[next].height_m.toFixed(1)} m`}</span>}
        {pin === null
          ? <span className="tide-hint">{t(lang, 'tideDragHint')}</span>
          : <button type="button" className="tide-now" onClick={() => setPin(null)}>{t(lang, 'tideBackNow')}</button>}
      </div>
    </>
  );
}
