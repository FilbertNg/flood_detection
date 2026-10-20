import type { ReactElement } from 'react';
import type { WeatherKind } from '../lib/weather';

/**
 * A small hand-drawn icon set for the street page: weather, rain gauge, river, tide, flood-prone,
 * reasons, advice and report. Filled, slightly chunky shapes so they read at a glance outdoors.
 * Every icon is decorative (aria-hidden); the text next to it carries the meaning.
 */
const box = { width: 28, height: 28, viewBox: '0 0 32 32', 'aria-hidden': true } as const;

const cloud = 'M9 25h14.5a5.5 5.5 0 0 0 .6-10.97A8 8 0 0 0 8.6 15.1 5 5 0 0 0 9 25z';
const sun = (cx: number, cy: number, r: number, fill: string) => (
  <g fill={fill}>
    <circle cx={cx} cy={cy} r={r} />
    {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
      <rect key={a} x={cx - 1.2} y={cy - r - 5} width={2.4} height={3.4} rx={1.2} transform={`rotate(${a} ${cx} ${cy})`} />
    ))}
  </g>
);
const moon = (cx: number, cy: number, fill: string) => (
  <path fill={fill} d={`M${cx + 3} ${cy - 7}a8 8 0 1 0 6 11.5 6.5 6.5 0 0 1-6-11.5z`} />
);
const drops = (n: number, fill: string) => (
  <g fill={fill}>
    {Array.from({ length: n }, (_, i) => (
      <path key={i} d={`M${10 + i * 5} 27.5l-1.6 3.2a1.8 1.8 0 1 0 3.2 0z`} />
    ))}
  </g>
);

/** Colours per surface: white shapes on the dark hero sky, greys on the white cards (SDP style). */
const TONE = {
  sky: { cloud: '#fff', moon: '#f1f3f8', drop: '#7cc4ff', sun: '#ffcf3f' },
  card: { cloud: '#b8bec8', moon: '#8a94a6', drop: '#3b82c4', sun: '#f5b400' },
};

export function WeatherIcon({ kind, tone = 'sky' }: { kind: WeatherKind; tone?: keyof typeof TONE }) {
  const c = TONE[tone];
  return (
    <svg {...box} data-icon={kind} className="icon">
      {kind === 'clear-day' && sun(16, 16, 6.5, c.sun)}
      {kind === 'clear-night' && moon(14, 16, c.moon)}
      {kind === 'partly-day' && <>{sun(12, 11, 5, c.sun)}<path fill={c.cloud} d={cloud} /></>}
      {kind === 'partly-night' && <>{moon(10, 11, c.moon)}<path fill={c.cloud} d={cloud} /></>}
      {kind === 'cloudy' && <path fill={c.cloud} d={cloud} transform="translate(0 -2)" />}
      {kind === 'fog' && (
        <g fill={c.cloud}><path d={cloud} transform="translate(0 -5)" opacity={0.9} /><rect x="5" y="23" width="22" height="2.4" rx="1.2" /><rect x="8" y="27" width="16" height="2.4" rx="1.2" /></g>
      )}
      {(kind === 'drizzle' || kind === 'rain' || kind === 'storm') && (
        <>
          <path fill={c.cloud} d={cloud} transform="translate(0 -5)" />
          {kind === 'storm' ? <path fill={c.sun} d="M17 19l-4.5 6.5h3.5L14 31l6-8h-3.6l2-4z" /> : drops(kind === 'rain' ? 3 : 2, c.drop)}
        </>
      )}
    </svg>
  );
}

type Glyph = 'drop' | 'river' | 'tide' | 'home' | 'why' | 'todo' | 'report' | 'clock' | 'map' | 'list' | 'check';

const GLYPHS: Record<Glyph, ReactElement> = {
  drop: <path d="M16 4c4.5 6 8 10.4 8 14.5a8 8 0 0 1-16 0C8 14.4 11.5 10 16 4z" />,
  river: <path d="M3 12c3 0 3-2 6.5-2S13 12 16 12s3-2 6.5-2S26 12 29 12v3c-3 0-3.5-2-6.5-2S19 15 16 15s-3.5-2-6.5-2S6 15 3 15zm0 7c3 0 3-2 6.5-2S13 19 16 19s3-2 6.5-2S26 19 29 19v3c-3 0-3.5-2-6.5-2S19 22 16 22s-3.5-2-6.5-2S6 22 3 22z" />,
  tide: <path d="M4 20c4 0 5-9 12-9s8 9 12 9v4c-5 0-6.5-9-12-9S9 24 4 24zM15 4h2v5h-2z" />,
  home: <path d="M16 5l12 10h-3.5v12h-6v-7h-5v7h-6V15H4z" />,
  why: <path d="M16 4a12 12 0 1 1 0 24 12 12 0 0 1 0-24zm-1.6 15.5h3.2v3.2h-3.2zM16 9c2.9 0 5 1.8 5 4.3 0 2.2-1.5 3.1-2.7 3.9-.7.5-.8.8-.8 1.5h-3c0-1.8.7-2.7 2-3.5 1-.7 1.5-1 1.5-1.8 0-.9-.8-1.5-2-1.5s-2 .7-2.2 1.8l-3-.5C11.3 10.6 13.3 9 16 9z" />,
  todo: <path d="M16 3l11 4v8c0 7-4.6 12.2-11 14-6.4-1.8-11-7-11-14V7zm-1.5 16.5l-4-4-2.1 2.1 6.1 6.1 9-9-2.1-2.1z" />,
  report: <path d="M6 4h20a3 3 0 0 1 3 3v14a3 3 0 0 1-3 3H13l-6 5v-5H6a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3zm8.4 4v8h3.2V8zm0 10v3.2h3.2V18z" />,
  clock: <path d="M16 3a13 13 0 1 1 0 26 13 13 0 0 1 0-26zm-1.5 6v8.2l6.4 3.8 1.5-2.5-4.9-2.9V9z" />,
  map: <path d="M3 7l8-3 10 3 8-3v21l-8 3-10-3-8 3zm8 .2v17.2l10 3V10.2z" />,
  check: <path d="M16 3a13 13 0 1 1 0 26 13 13 0 0 1 0-26zm0 2.6a10.4 10.4 0 1 0 0 20.8 10.4 10.4 0 0 0 0-20.8zm5.2 5.6l1.9 1.8-8.5 8.8-5-5 1.9-1.9 3.1 3.1z" />,
  list: <path d="M5 7h3v3H5zm6 .2h16v2.6H11zM5 14.5h3v3H5zm6 .2h16v2.6H11zM5 22h3v3H5zm6 .2h16v2.6H11z" />,
};

export type GlyphName = Glyph;

export function Icon({ name }: { name: Glyph }) {
  return (
    <svg {...box} width={20} height={20} className="glyph" fill="currentColor" fillRule="evenodd">
      {GLYPHS[name]}
    </svg>
  );
}
