import { LEVEL_STYLE, type SeriesPoint, type Station } from '@floodready/shared';
import { axisTime, linearScale, rollingSum } from '../lib/chart';

const W = 620;
const H = 190;
const PAD = { l: 44, r: 140, t: 22, b: 24 };

const GUIDE_GREY = '#607d8b';

/** JPS one-hour (a guide, not our trigger thresholds) rain categories (config/rules.yaml): heavy 31-60 mm, very heavy > 60 mm. */
const RAIN_LINES = [
  { key: 'heavy', value: 31, label: 'JPS rain guide 31 mm/h', colour: GUIDE_GREY },
  { key: 'very heavy', value: 60, label: '60 mm/h', colour: GUIDE_GREY },
];

interface Line { key: string; value: number; label: string; colour: string }

function riverLines(station: Station): Line[] {
  const t = station.thresholds;
  if (!t) return [];
  return [
    { key: 'alert', value: t.alert, label: `Alert ${t.alert.toFixed(2)} m`, colour: LEVEL_STYLE.watch.line },
    { key: 'warning', value: t.warning, label: `Warning ${t.warning.toFixed(2)} m`, colour: LEVEL_STYLE.warning.line },
    { key: 'danger', value: t.danger, label: `Danger ${t.danger.toFixed(2)} m`, colour: LEVEL_STYLE.danger.line },
  ];
}

/**
 * Inline-SVG chart for one station.
 * Rain gauge: 15-minute bars plus the rolling 1 h total, against the JPS intensity lines.
 * River gauge: water level against the station's own alert / warning / danger levels.
 */
export function StationChart({ station, series }: { station: Station; series: SeriesPoint[] }) {
  const isRain = station.kind === 'rf';
  const points = series.filter((p) => (isRain ? p.rain_15min_mm !== null : p.wl_m !== null));
  const unit = isRain ? 'mm' : 'm';

  return (
    <figure className="chart">
      <figcaption>
        <strong>{station.name}</strong> <span className="muted small">{isRain ? 'rain gauge' : 'river level'}{station.is_stale ? ' · stale' : ''}</span>
      </figcaption>
      {points.length === 0 ? (
        <p className="muted small">No readings in this period.</p>
      ) : (
        <Plot station={station} points={points} isRain={isRain} unit={unit} />
      )}
    </figure>
  );
}

function Plot({ station, points, isRain, unit }: { station: Station; points: SeriesPoint[]; isRain: boolean; unit: string }) {
  const lines = isRain ? RAIN_LINES : riverLines(station);
  const times = points.map((p) => new Date(p.time).getTime());
  const values = points.map((p) => (isRain ? p.rain_15min_mm! : p.wl_m!));
  const rolling = isRain ? rollingSum(values, 4) : [];

  const tMin = Math.min(...times);
  const tMax = Math.max(...times);
  const highs = [...values, ...rolling, ...lines.map((l) => l.value)];
  const lows = isRain ? [0] : [...values, ...lines.map((l) => l.value)];
  const yMin = isRain ? 0 : Math.min(...lows) - 0.2;
  const yMax = Math.max(...highs) + (isRain ? 4 : 0.2);

  const x = linearScale([tMin, tMax], [PAD.l, W - PAD.r]);
  const y = linearScale([yMin, yMax], [H - PAD.b, PAD.t]);
  const slot = (W - PAD.l - PAD.r) / Math.max(points.length, 1);
  const barW = Math.max(2, Math.min(18, slot * 0.7));
  const path = (ys: number[]) => ys.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(times[i]).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const spansDays = points[0].time.slice(0, 10) !== points[points.length - 1].time.slice(0, 10);
  const ticks = [yMin, (yMin + yMax) / 2, yMax];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary(station, values, unit, isRain)} className="chart-svg">
      {ticks.map((v) => (
        <g key={v}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} stroke="var(--line)" />
          <text data-tick x={PAD.l - 6} y={y(v) + 4} textAnchor="end" className="axis">{v.toFixed(isRain ? 0 : 1)}</text>
        </g>
      ))}
      <text data-unit x={PAD.l - 6} y={9} textAnchor="end" className="axis">{unit}</text>
      <text x={PAD.l} y={H - 6} textAnchor="start" className="axis">{axisTime(points[0].time, spansDays)}</text>
      <text x={W - PAD.r} y={H - 6} textAnchor="end" className="axis">{axisTime(points[points.length - 1].time, spansDays)}</text>

      {isRain &&
        points.map((p, i) => (
          <rect key={p.time} data-bar x={x(times[i]) - barW / 2} y={y(values[i])} width={barW} height={Math.max(0, y(0) - y(values[i]))} fill="#1e88e5" opacity={0.55} />
        ))}
      {isRain && <path data-line="rain1h" d={path(rolling)} fill="none" stroke="#0b3d91" strokeWidth={2} />}
      {!isRain && <path data-line="level" d={path(values)} fill="none" stroke="#0b3d91" strokeWidth={2} />}

      {lines.map((l) => (
        <g key={l.key}>
          <line data-threshold={l.key} x1={PAD.l} x2={W - PAD.r} y1={y(l.value)} y2={y(l.value)} stroke={l.colour} strokeWidth={1.5} strokeDasharray="5 3" />
          <text x={W - PAD.r + 4} y={y(l.value) + 4} className="axis">{l.label}</text>
        </g>
      ))}
    </svg>
  );
}

function summary(station: Station, values: number[], unit: string, isRain: boolean): string {
  const f = (v: number) => `${v.toFixed(isRain ? 1 : 2)} ${unit}`;
  const last = values[values.length - 1];
  return `${station.name} readings: ${values.length} points, latest ${f(last)}, lowest ${f(Math.min(...values))}, highest ${f(Math.max(...values))}`;
}
