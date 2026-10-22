import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import css from '../styles.css?raw';
import { LogoFill } from './LogoFill';

afterEach(cleanup);

describe('LogoFill', () => {
  it('is decorative and gives each instance its own clip path', () => {
    const { container } = render(<><LogoFill /><LogoFill size={32} /></>);
    const svgs = [...container.querySelectorAll('svg.logo-fill')];
    expect(svgs).toHaveLength(2);
    for (const s of svgs) expect(s).toHaveAttribute('aria-hidden', 'true');
    expect(svgs[0]).toHaveAttribute('width', '64');
    expect(svgs[1]).toHaveAttribute('width', '32');
    const ids = svgs.map((s) => s.querySelector('clipPath')!.id);
    expect(new Set(ids).size).toBe(2);
    svgs.forEach((s, i) => expect(s.querySelector('[clip-path]')).toHaveAttribute('clip-path', `url(#${ids[i]})`));
  });

  it('draws the cup, a back and a front wave, and the rim', () => {
    const { container } = render(<LogoFill />);
    expect(container.querySelector('.cup')).not.toBeNull();
    expect(container.querySelectorAll('.water .wave')).toHaveLength(2);
    expect(container.querySelector('.wave.back')).not.toBeNull();
    expect(container.querySelector('.rim')).not.toBeNull();
  });
});

describe('loader CSS', () => {
  const reduced = css.slice(css.indexOf('/* Loader: reduced motion'));

  it('rises over a 2.6 s loop and slides the waves (1.1 s front, 1.7 s back)', () => {
    expect(css).toMatch(/\.logo-fill \.water \{[^}]*animation: lf-rise 2\.6s cubic-bezier\(\.45, ?\.05, ?\.35, ?1\) infinite/);
    expect(css).toMatch(/\.logo-fill \.wave \{[^}]*animation: lf-slide 1\.1s linear infinite/);
    expect(css).toMatch(/\.logo-fill \.wave\.back \{[^}]*animation-duration: 1\.7s/);
  });

  it('turns the rise, the slide and the shimmer off with reduced motion, keeping a gentle pulse', () => {
    expect(reduced).toMatch(/@media \(prefers-reduced-motion: reduce\)/);
    expect(reduced).toMatch(/\.logo-fill \.water \{[^}]*animation: none/);
    expect(reduced).toMatch(/\.logo-fill \.wave \{[^}]*animation: none/);
    expect(reduced).toMatch(/\.bone \{[^}]*animation: none/);
    expect(reduced).toMatch(/\.logo-fill \{[^}]*animation: lf-pulse 1\.6s/);
  });
});
