import type { Sky } from '../lib/weather';

const RAINY: Sky[] = ['drizzle', 'rain', 'storm'];

/**
 * The weather backdrop behind the street page: a sky gradient per condition, CSS rain that
 * falls for drizzle, rain and storm, and a slow soft flash for a storm. Pure decoration:
 * hidden from screen readers, and the CSS stops all motion when the phone asks for less.
 */
export function SkyBackdrop({ sky }: { sky: Sky }) {
  const rainy = RAINY.includes(sky);
  return (
    <div className={`sky sky-${sky}`} aria-hidden="true">
      {rainy && (
        <>
          <div className="rain-layer rain-far" />
          <div className="rain-layer rain-near" />
        </>
      )}
      {sky === 'storm' && <div className="flash" />}
    </div>
  );
}
