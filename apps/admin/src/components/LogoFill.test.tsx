import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { InlineLoading, LogoFill } from './LogoFill';

afterEach(cleanup);

describe('LogoFill (admin)', () => {
  it('is decorative and gives each instance its own clip path', () => {
    const { container } = render(<><LogoFill /><LogoFill size={32} /></>);
    const svgs = [...container.querySelectorAll('svg.logo-fill')];
    expect(svgs).toHaveLength(2);
    for (const s of svgs) expect(s).toHaveAttribute('aria-hidden', 'true');
    const ids = svgs.map((s) => s.querySelector('clipPath')!.id);
    expect(new Set(ids).size).toBe(2);
  });

  it('puts the 32 px loader beside the text in a status', () => {
    const { getByRole } = render(<InlineLoading text="Loading statistics…" />);
    const status = getByRole('status');
    expect(status).toHaveTextContent('Loading statistics…');
    expect(status.querySelector('svg.logo-fill')).toHaveAttribute('width', '32');
  });
});
