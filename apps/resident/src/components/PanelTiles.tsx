import { useId, type ReactNode } from 'react';
import type { Lang, StreetDetail, Susceptibility } from '@floodready/shared';
import { hhmm, metres, percent } from '../lib/format';
import { t, tf, type StringKey } from '../lib/i18n';
import { rainStrength, riverGap, riverStatus, type Mark, type RiverStatus } from '../lib/plain';
import type { Thresholds } from '../lib/river';
import { tideIndexAt, tideTrend, type TidePoint } from '../lib/tide';
import {
  BARS, DROP_PATH, PILL, WAVE, clockHands, dropFillTop, heaviestHour, nextHighWater, pillTicks, pillY, proneTone, rainBars, ringDash,
  ringTone, scallopPath, tideWave,
} from '../lib/tiles';
import type { GaugeRain } from '../lib/weather';
import { Icon, type GlyphName } from './Icons';

/**
 * Picture tiles for the white street page (below the hero card): each reading is drawn as an object, a
 * drop that fills, rain bars, a river gauge pill, a scalloped badge, a tide wave, a ring, a clock. The
 * pictures are aria-hidden; the tile text carries every value and its meaning. Geometry is in lib/tiles.ts.
 * The full-screen sky view keeps its own panels (StreetView `skyPanels`).
 */

const RAIN_WORD = { none: 'rainNone', light: 'rainLight', moderate: 'rainModerate', heavy: 'rainHeavy' } as const satisfies Record<string, StringKey>;
const RIVER_CHIP: Record<RiverStatus, StringKey> = { low: 'riverLow', near: 'riverNear', alert: 'riverAlert', warning: 'riverWarning', danger: 'riverDanger' };
const RIVER_TONE: Record<RiverStatus, 'ok' | 'watch' | 'warn' | 'danger'> = { low: 'ok', near: 'watch', alert: 'watch', warning: 'warn', danger: 'danger' };
const MARK_TEXT: Record<Mark, StringKey> = { alert: 'markAlert', warning: 'markWarning', danger: 'markDanger' };
const TICK_LETTER: Record<Mark, string> = { alert: 'A', warning: 'W', danger: 'D' };

function Tile({ icon, title, wide, children }: { icon: GlyphName; title: string; wide?: boolean; children: ReactNode }) {
  const id = useId();
  return (
    <section className="ptile" data-wide={wide || undefined} aria-labelledby={id}>
      <h3 className="ptile-head" id={id}><Icon name={icon} />{title}</h3>
      {children}
    </section>
  );
}

const Value = ({ n, unit }: { n: string; unit?: string }) => <p className="ptile-val">{n}{unit && <small>{unit}</small>}</p>;

/** Rain in the last hour at the wettest nearby gauge, in a drop that fills to 30 mm. */
export function RainNowTile({ lang, gauge }: { lang: Lang; gauge: GaugeRain | null }) {
  const clip = useId();
  const mm = gauge?.mm ?? 0;
  const top = dropFillTop(mm);
  return (
    <Tile icon="drop" title={t(lang, 'rainNow')}>
      <div className="ptile-body">
        <div>
          <Value n={String(mm)} unit="mm" />
          <p className="ptile-mean">{t(lang, RAIN_WORD[rainStrength(mm)])}</p>
          <p className="ptile-note">{t(lang, 'tileRainNote')}</p>
        </div>
        <svg className="pic" width="58" height="76" viewBox="0 0 80 104" aria-hidden="true">
          <defs><clipPath id={clip}><path d={DROP_PATH} /></clipPath></defs>
          <path d={DROP_PATH} className="w3" />
          <rect className="w1 rise" x="0" y={top} width="80" height={104 - top} clipPath={`url(#${clip})`} />
          <path d={DROP_PATH} className="w-edge" fill="none" strokeWidth="2" />
          <text x="78" y="12" textAnchor="end">30+</text>
          <text x="78" y="100" textAnchor="end">0</text>
        </svg>
      </div>
    </Tile>
  );
}

/** Forecast rain over the next 12 hours: the total, the wettest hour, one bar per hour. */
export function RainNextTile({ lang, rain }: { lang: Lang; rain: StreetDetail['rain_next_12h'] }) {
  const total = rain.reduce((sum, p) => sum + p.mm, 0);
  const peak = heaviestHour(rain);
  const W = Math.max(BARS.width, (rain.length - 1) * BARS.step + BARS.bar);
  return (
    <Tile icon="drop" title={t(lang, 'tileNext12')}>
      <Value n={total.toFixed(1)} unit="mm" />
      <p className="ptile-note">{peak ? tf(lang, 'tileHeaviest', { time: hhmm(peak) }) : t(lang, 'tileNoRain')}</p>
      {rain.length > 0 && (
        <>
          <svg className="pic pic-stretch" viewBox={`0 0 ${W} ${BARS.height}`} aria-hidden="true">
            {rainBars(rain).map((b, i) => (
              <rect key={rain[i].time} data-hour-bar className={b.wet ? 'w1' : 'w3'} x={b.x} y={b.y} width={BARS.bar} height={b.h} rx="3" />
            ))}
          </svg>
          <p className="pic-axis" aria-hidden="true"><span>{hhmm(rain[0].time)}</span><span>{hhmm(rain[rain.length - 1].time)}</span></p>
        </>
      )}
    </Tile>
  );
}

export interface RiverReading { wl: number; th: Thresholds; name: string }

/** The street's river: level, status chip, gap to the next JPS mark, and a gauge pill with A / W / D ticks. */
export function RiverTile({ lang, river, reachBy }: { lang: Lang; river: RiverReading | null; reachBy: string | null }) {
  const clip = useId();
  if (!river) {
    return (
      <Tile icon="river" title={t(lang, 'panelRiver')}>
        <p className="ptile-mean">{t(lang, 'rNone')}</p>
      </Tile>
    );
  }
  const { wl, th } = river;
  const status = riverStatus(wl, th);
  const gap = riverGap(wl, th);
  const y = pillY(wl, th);
  const H = PILL.height;
  return (
    <Tile icon="river" title={t(lang, 'panelRiver')}>
      <span className="ptile-chip" data-tone={RIVER_TONE[status]}>{t(lang, RIVER_CHIP[status])}</span>
      <div className="ptile-body">
        <div>
          <Value n={wl.toFixed(2).replace('-', '−')} unit="m" />
          <p className="ptile-note ptile-gap">{tf(lang, gap.above ? 'riverAboveMark' : 'riverBelowMark', { m: metres(gap.m), mark: t(lang, MARK_TEXT[gap.mark]).toLowerCase() })}</p>
        </div>
        <svg className="pic" width="74" height={H} viewBox={`0 0 74 ${H}`} aria-hidden="true">
          <defs><clipPath id={clip}><rect x="16" y="4" width="24" height={H - 8} rx="12" /></clipPath></defs>
          <rect className="w3" x="16" y="4" width="24" height={H - 8} rx="12" />
          <rect className="w2 rise" x="16" y={y} width="24" height={H - y} clipPath={`url(#${clip})`} />
          <path className="ink" d={`M4 ${y - 5} L12 ${y} L4 ${y + 5}z`} />
          {pillTicks(th).map((k) => (
            <g key={k.mark} data-tick={k.mark} className={`tick-${k.mark}`}>
              <line x1="44" x2="52" y1={k.y} y2={k.y} strokeWidth="3" strokeLinecap="round" />
              <text x="56" y={k.y + 3.5}>{TICK_LETTER[k.mark]}</text>
            </g>
          ))}
        </svg>
      </div>
      <p className="ptile-note">{tf(lang, 'riverAt', { station: river.name })}</p>
      {reachBy && <p className="ptile-flag">{tf(lang, 'riverMayReachBy', { time: hhmm(reachBy) })}</p>}
    </Tile>
  );
}

const PRONE_WORD = (s: Susceptibility): StringKey => (s >= 4 ? 'tileLowLying' : s === 3 ? 'streetMid' : 'streetLow');

/** How flood-prone the street is (1 to 5) in a scalloped badge, with five dots. */
export function StreetTile({ lang, score }: { lang: Lang; score: Susceptibility }) {
  return (
    <Tile icon="home" title={t(lang, 'panelStreet')}>
      <div className="ptile-center">
        <svg className="pic" width="92" height="112" viewBox="0 0 92 112" aria-hidden="true" data-tone={proneTone(score)}>
          <path className="badge" d={scallopPath()} />
          <text className="pic-big" x="46" y="58" textAnchor="middle">{score}</text>
          <text x="46" y="72" textAnchor="middle">{t(lang, 'tileOf5')}</text>
          {[1, 2, 3, 4, 5].map((i) => (
            <circle key={i} data-dot data-on={i <= score || undefined} cx={46 + (i - 3) * 13} cy="104" r="4" />
          ))}
        </svg>
        <p className="ptile-mean">{t(lang, PRONE_WORD(score))}</p>
        <p className="ptile-note">{t(lang, 'tileStreetNote')}</p>
      </div>
    </Tile>
  );
}

/** Port Klang tide over the hours the API sends: the next high water and the wave with now marked. */
export function TideTile({ lang, tide, dataTime }: { lang: Lang; tide: TidePoint[]; dataTime: string }) {
  const title = `${t(lang, 'panelTide')} · ${t(lang, 'tidePlace')}`;
  if (tide.length < 2) {
    return <Tile icon="tide" title={title} wide><p className="ptile-note">{t(lang, 'noTide')}</p></Tile>;
  }
  const high = nextHighWater(tide, dataTime);
  const trend = tideTrend(tide, tideIndexAt(tide, dataTime));
  const wave = tideWave(tide, dataTime);
  const { width: W, height: H } = WAVE;
  return (
    <Tile icon="tide" title={title} wide>
      <div className="ptile-tide">
        <div>
          <p className="ptile-note">{t(lang, 'tileNextHigh')}</p>
          {high ? (
            <>
              <p className="ptile-val ptile-val-m">{hhmm(high.time)}</p>
              <p className="ptile-note">{[`${high.height_m.toFixed(1)} m`, trend && t(lang, trend === 'rising' ? 'tideRising' : 'tideFalling')].filter(Boolean).join(' · ')}</p>
            </>
          ) : (
            <p className="ptile-mean">{t(lang, 'tileNoHigh')}</p>
          )}
        </div>
        <div>
          <svg className="pic pic-stretch" viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
            <path className="w3" d={wave.area} />
            <path className="w2 past" d={wave.past} />
            <path className="w-edge" d={wave.line} fill="none" strokeWidth="2" />
            <line className="baseline" x1="0" x2={W} y1={H} y2={H} strokeWidth="1.5" />
            <circle className="now-dot" cx={wave.now.x} cy={wave.now.y} r="6" strokeWidth="3" />
          </svg>
          <p className="pic-axis" aria-hidden="true">{wave.labels.map((l) => <span key={l.time}>{hhmm(l.time)}</span>)}</p>
        </div>
      </div>
      <p className="ptile-note">{t(lang, 'tileTideNote')}</p>
    </Tile>
  );
}

/** The ML chance as a ring; hidden when the model has no value. Display only: alerts follow JPS. */
export function ModelTile({ lang, p }: { lang: Lang; p: number | null }) {
  if (p === null) return null;
  const { len, C } = ringDash(p);
  return (
    <Tile icon="why" title={t(lang, 'techModel')}>
      <div className="ptile-center">
        <svg className="pic" width="96" height="96" viewBox="0 0 96 96" aria-hidden="true" data-tone={ringTone(p)}>
          <circle className="ring-track" cx="48" cy="48" r="34" fill="none" strokeWidth="9" />
          {len > 0 && <circle className="ring" cx="48" cy="48" r="34" fill="none" strokeWidth="9" strokeLinecap="round" strokeDasharray={`${len} ${C}`} transform="rotate(-90 48 48)" />}
        </svg>
        <p className="ptile-val ptile-ring-val">{percent(p)}</p>
        <p className="ptile-note">{t(lang, 'chance')}. {t(lang, 'tileModelNote')}</p>
      </div>
    </Tile>
  );
}

/** When the readings were taken, on a clock face, with how often they refresh and their sources. */
export function UpdatedTile({ lang, dataTime }: { lang: Lang; dataTime: string }) {
  const { hour, minute } = clockHands(dataTime);
  return (
    <Tile icon="clock" title={t(lang, 'tileUpdated')}>
      <div className="ptile-center">
        <svg className="pic" width="96" height="96" viewBox="0 0 96 96" aria-hidden="true">
          <circle className="clock-face" cx="48" cy="48" r="38" />
          {Array.from({ length: 12 }, (_, i) => {
            const a = (i * 30 * Math.PI) / 180;
            return <circle key={i} className="clock-tick" cx={48 + 31 * Math.sin(a)} cy={48 - 31 * Math.cos(a)} r="2" />;
          })}
          <line className="clock-hand" x1="48" y1="48" x2="48" y2="28" strokeWidth="4" strokeLinecap="round" transform={`rotate(${hour} 48 48)`} />
          <line className="clock-hand" x1="48" y1="48" x2="48" y2="20" strokeWidth="3" strokeLinecap="round" transform={`rotate(${minute} 48 48)`} />
          <circle className="now-pin" cx="48" cy="48" r="4" />
        </svg>
        <p className="ptile-note"><b>{hhmm(dataTime)}</b> · {t(lang, 'tileEvery15')}</p>
        <p className="ptile-note">{t(lang, 'tileSources')}</p>
      </div>
    </Tile>
  );
}

/** The engine's reasons for this street's level. */
export function WhyTile({ lang, reasons }: { lang: Lang; reasons: StreetDetail['reasons'] }) {
  return (
    <Tile icon="why" title={t(lang, 'tileWhy')} wide>
      {reasons.length ? (
        <ul className="ptile-why">{reasons.map((r) => <li key={r.code + r.station}>{r.text[lang]}</li>)}</ul>
      ) : (
        <p className="ptile-mean">{t(lang, 'noReasons')}</p>
      )}
    </Tile>
  );
}

/** A grid of tiles under a section label ("Right now", "Technical details"). */
export function TileGrid({ title, id, className, children }: { title: string; id: string; className?: string; children: ReactNode }) {
  return (
    <section className={['ptiles', className].filter(Boolean).join(' ')} aria-labelledby={id}>
      <h2 className="ptiles-sec" id={id}>{title}</h2>
      {children}
    </section>
  );
}

/** A wide white tile for blocks without a picture (JPS marks, river forecast). */
export function PlainTile({ icon, title, children }: { icon: GlyphName; title: string; children: ReactNode }) {
  return <Tile icon={icon} title={title} wide>{children}</Tile>;
}
