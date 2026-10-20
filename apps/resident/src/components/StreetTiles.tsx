import { useId } from 'react';
import type { Lang, StreetDetail } from '@floodready/shared';
import { CURVE, chanceColor, curvePoints, curveRuns } from '../lib/curve';
import { hhmm } from '../lib/format';
import { t } from '../lib/i18n';
import { riverScale, type Thresholds } from '../lib/river';
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
  // Gradient ids per curve: several pager panels and the full view can be on the page at once.
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

/** Port Klang tide: a small curve with "now" marked, and the next high water after the data time. */
export function TideMini({ lang, tide, dataTime }: { lang: Lang; tide: StreetDetail['tide']; dataTime: string }) {
  if (tide.length < 2) return <p className="tile-empty">{t(lang, 'noTide')}</p>;
  const now = Math.max(0, tide.findIndex((p) => p.time >= dataTime.slice(0, 13)));
  let high = -1;
  for (let i = Math.max(1, now); i < tide.length - 1; i++) {
    if (tide[i].height_m >= tide[i - 1].height_m && tide[i].height_m >= tide[i + 1].height_m) { high = i; break; }
  }
  const w = 140, h = 44;
  const ys = tide.map((p) => p.height_m);
  const lo = Math.min(...ys), span = Math.max(...ys) - lo || 1;
  const x = (i: number) => (i / (tide.length - 1)) * w;
  const y = (v: number) => h - 4 - ((v - lo) / span) * (h - 8);
  const path = tide.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.height_m).toFixed(1)}`).join(' ');
  return (
    <>
      <svg viewBox={`0 0 ${w} ${h}`} className="tide-mini" aria-hidden="true">
        <path d={path} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
        <circle cx={x(now)} cy={y(tide[now].height_m)} r="4.5" fill="#fff" />
      </svg>
      {high >= 0 && <p className="tile-note">{`${t(lang, 'highTide')} ${hhmm(tide[high].time)} · ${tide[high].height_m.toFixed(1)} m`}</p>}
    </>
  );
}
