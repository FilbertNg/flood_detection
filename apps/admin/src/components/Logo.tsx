import { useId } from 'react';

const PIN = 'M32 4C20.7 4 11.5 13 11.5 24.2 11.5 38.6 32 60 32 60s20.5-21.4 20.5-35.8C52.5 13 43.3 4 32 4z';
const WAVE = 'M6 33c3.2 0 4.8-3.2 8-3.2s4.8 3.2 8 3.2 4.8-3.2 8-3.2 4.8 3.2 8 3.2 4.8-3.2 8-3.2 4.8 3.2 8 3.2 4.8-3.2 8-3.2';

/**
 * The Flood-Ready mark (docs/design/logo): a map pin with a wave across it. `red` is the red pin for
 * white surfaces; `white` is the white pin with a red wave for red surfaces.
 * Decorative: the app name next to it carries the meaning.
 */
export function LogoMark({ tone = 'red', size = 28 }: { tone?: 'red' | 'white'; size?: number }) {
  // The wave is clipped to the pin; the clip id is per instance (the logo can be on a page twice).
  const clip = useId();
  const [pin, wave] = tone === 'white' ? ['#fff', '#ea0009'] : ['#d71920', '#fff'];
  return (
    <svg className="logo" viewBox="0 0 64 64" width={size} height={size} aria-hidden="true">
      <defs><clipPath id={clip}><path d={PIN} /></clipPath></defs>
      <path d={PIN} fill={pin} />
      <path d={WAVE} clipPath={`url(#${clip})`} fill="none" stroke={wave} strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
