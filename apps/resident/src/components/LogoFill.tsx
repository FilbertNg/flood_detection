import { useId } from 'react';

const PIN = 'M32 4C20.7 4 11.5 13 11.5 24.2 11.5 38.6 32 60 32 60s20.5-21.4 20.5-35.8C52.5 13 43.3 4 32 4z';

/** A wavy water surface at height y, wide enough to slide one 24-unit wavelength without a gap. */
function wave(y: number): string {
  let d = `M-24 ${y}`;
  for (let x = -24; x < 96; x += 24) d += ' q6 -3.2 12 0 t12 0';
  return `${d} V70 H-24 Z`;
}
const BACK = wave(2);
const FRONT = wave(4);

/**
 * The loader (docs/design/loader-proposal.html): water fills the Flood-Ready pin like a cup, holds,
 * drains and fills again, its waves sliding sideways. Decorative; the text beside it says what is loading.
 * Motion is in styles.css (`.logo-fill`), with a still, half-full pulse for reduced motion.
 */
export function LogoFill({ size = 64 }: { size?: number }) {
  // A clip path per instance, so several loaders on one page never share one.
  const clip = useId();
  return (
    <svg className="logo-fill" width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" focusable="false">
      <defs><clipPath id={clip}><path d={PIN} /></clipPath></defs>
      <path className="cup" d={PIN} />
      <g clipPath={`url(#${clip})`}>
        <g className="water">
          <path className="wave back" d={BACK} />
          <path className="wave" d={FRONT} />
        </g>
      </g>
      <path className="rim" d={PIN} />
    </svg>
  );
}

/** The loader centred in the page, 56 px above the line that says what is loading: for whole-page loads. */
export function PageLoading({ text }: { text: string }) {
  return <p className="page-loading" role="status"><LogoFill size={56} />{text}</p>;
}

/** The compact loader, 32 px beside a short line: for a wait inside a card or a sheet. */
export function InlineLoading({ text }: { text: string }) {
  return <p className="inline-loading" role="status"><LogoFill size={32} />{text}</p>;
}
