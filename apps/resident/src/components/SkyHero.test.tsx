import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { SkyBackdrop } from './SkyHero';

afterEach(cleanup);

describe('SkyBackdrop', () => {
  // About half the drops of the old full-screen sky, now that it lives inside the hero card.
  it.each([['drizzle', '22'], ['rain', '45'], ['storm', '85'], ['cloudy', '0']] as const)('%s draws %s rain drops on the canvas', (sky, drops) => {
    const { container } = render(<SkyBackdrop sky={sky} />);
    expect(container.querySelector('canvas')).toHaveAttribute('data-drops', drops);
  });

  it('sets the three gradient stops for the sky', () => {
    const { container } = render(<SkyBackdrop sky="rain" />);
    const style = (container.firstElementChild as HTMLElement).style;
    expect(style.getPropertyValue('--sky-top')).not.toBe('');
    expect(style.getPropertyValue('--sky-mid')).not.toBe('');
    expect(style.getPropertyValue('--sky-bottom')).not.toBe('');
  });

  it('allows the soft flash only for a storm', () => {
    const { container, rerender } = render(<SkyBackdrop sky="storm" />);
    expect(container.querySelector('canvas')).toHaveAttribute('data-flash', 'true');
    rerender(<SkyBackdrop sky="rain" />);
    expect(container.querySelector('canvas')).toHaveAttribute('data-flash', 'false');
  });

  it('does not animate an off-screen pager panel', () => {
    const { container, rerender } = render(<SkyBackdrop sky="rain" active={false} />);
    expect(container.querySelector('canvas')).toHaveAttribute('data-still', 'true');
    rerender(<SkyBackdrop sky="rain" />);
    expect(container.querySelector('canvas')).toHaveAttribute('data-still', 'false');
  });

  it('keeps the alert sky still: no canvas, no rain, no motion', () => {
    const { container } = render(<SkyBackdrop sky="alert" />);
    expect(container.querySelector('.sky-alert')).not.toBeNull();
    expect(container.querySelector('canvas')).toBeNull();
  });

  it('is decoration only, hidden from screen readers', () => {
    const { container } = render(<SkyBackdrop sky="cloudy" />);
    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true');
    expect(screen.queryByRole('img')).toBeNull();
  });
});
