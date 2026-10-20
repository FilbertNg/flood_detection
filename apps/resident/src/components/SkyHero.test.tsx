import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { SkyBackdrop } from './SkyHero';

afterEach(cleanup);

describe('SkyBackdrop', () => {
  it('draws moving rain for rainy skies', () => {
    const { container } = render(<SkyBackdrop sky="rain" />);
    expect(container.querySelector('.sky-rain')).not.toBeNull();
    expect(container.querySelectorAll('.rain-layer').length).toBeGreaterThan(0);
  });

  it('adds the soft flash only for a storm', () => {
    const { container, rerender } = render(<SkyBackdrop sky="storm" />);
    expect(container.querySelector('.flash')).not.toBeNull();
    rerender(<SkyBackdrop sky="drizzle" />);
    expect(container.querySelector('.flash')).toBeNull();
  });

  it('keeps the alert sky still, with no rain', () => {
    const { container } = render(<SkyBackdrop sky="alert" />);
    expect(container.querySelector('.sky-alert')).not.toBeNull();
    expect(container.querySelector('.rain-layer')).toBeNull();
  });

  it('is decoration only, hidden from screen readers', () => {
    const { container } = render(<SkyBackdrop sky="cloudy" />);
    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true');
    expect(screen.queryByRole('img')).toBeNull();
  });
});
