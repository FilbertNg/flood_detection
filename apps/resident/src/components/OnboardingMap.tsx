import { useId } from 'react';

/** Wavy bands over the base gradient: [path, gradient, opacity]. */
const BANDS: [string, 'g1' | 'g2' | 'g3' | 'g4', number][] = [
  ['M0 90 C 90 50, 170 140, 260 100 S 360 60, 390 80 L390 0 L0 0 Z', 'g1', 1],
  ['M0 200 C 80 160, 180 250, 280 200 S 370 160, 390 180 L390 0 L0 0 Z', 'g2', 0.55],
  ['M0 330 C 100 290, 190 380, 290 330 S 370 300, 390 315 L390 480 L0 480 Z', 'g3', 0.7],
  ['M0 420 C 110 380, 200 460, 300 420 S 370 400, 390 410 L390 480 L0 480 Z', 'g4', 0.8],
];

/** Four winding roads, kept away from the middle where the logo sits. */
const ROADS = [
  'M-10 150 C 60 130, 120 175, 190 160 S 310 120, 400 140',
  'M-10 300 C 70 285, 140 320, 210 300 S 330 260, 400 280',
  'M70 -10 C 90 80, 50 160, 85 250 S 120 400, 95 490',
  'M300 -10 C 280 90, 320 170, 295 260 S 260 400, 290 490',
];
const FOOTPATH = 'M20 40 C 80 70, 140 40, 200 70 S 320 60, 380 30';

/**
 * Onboarding illustration (docs/design/onboarding-proposal.html): an SDP-red diagonal gradient with
 * wavy bands, warm orange at the top and deep red at the bottom, and a faint tone-on-tone hint of
 * roads and a footpath. Decoration only, not real geometry; hidden from screen readers.
 */
export function OnboardingMap() {
  // Gradient ids per instance, so two copies on a page never share one.
  const id = useId();
  const g = (name: string) => `${id}-${name}`;
  return (
    <svg viewBox="0 0 390 480" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={g('bg')} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ff2a2f" /><stop offset=".5" stopColor="#ea0009" /><stop offset="1" stopColor="#b80008" />
        </linearGradient>
        <linearGradient id={g('g1')} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#ff4a3d" /><stop offset="1" stopColor="#df6436" />
        </linearGradient>
        <linearGradient id={g('g2')} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#ff3b3b" stopOpacity="0" /><stop offset="1" stopColor="#ff6a4d" />
        </linearGradient>
        <linearGradient id={g('g3')} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#d0000a" /><stop offset="1" stopColor="#a80007" />
        </linearGradient>
        <linearGradient id={g('g4')} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#b00008" /><stop offset="1" stopColor="#8f0006" />
        </linearGradient>
      </defs>
      <rect width="390" height="480" fill={`url(#${g('bg')})`} />
      {BANDS.map(([d, fill, opacity]) => <path key={d} d={d} fill={`url(#${g(fill)})`} opacity={opacity} />)}
      <g fill="none" strokeLinecap="round">
        {ROADS.map((d) => (
          <g key={d} data-road>
            <path d={d} stroke="#6e0004" strokeWidth="7" opacity=".14" />
            <path d={d} stroke="#ffb3a0" strokeWidth="1" strokeDasharray="6 8" opacity=".16" />
          </g>
        ))}
        <path d={FOOTPATH} stroke="#ffd0c0" strokeWidth="1.2" strokeDasharray="1 6" opacity=".3" />
      </g>
    </svg>
  );
}
