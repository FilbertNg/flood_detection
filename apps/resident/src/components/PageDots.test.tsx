import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PageDots } from './PageDots';

afterEach(cleanup);

const dots = [
  { id: 'a', name: 'Jalan Makyong', level: 'warning' as const },
  { id: 'b', name: 'Persiaran Batu Belah', level: 'watch' as const },
  { id: 'c', name: 'Jalan Mock', level: 'normal' as const },
];

function renderBar(props: Partial<Parameters<typeof PageDots>[0]> = {}) {
  const onDot = vi.fn();
  render(<MemoryRouter><PageDots lang="en" dots={dots} active={1} onDot={onDot} {...props} /></MemoryRouter>);
  return onDot;
}

describe('PageDots', () => {
  it('has one labelled dot per saved street and marks the active one', () => {
    renderBar();
    const buttons = screen.getAllByRole('button', { name: /^Street \d of 3/ });
    expect(buttons).toHaveLength(3);
    expect(buttons[0]).toHaveAccessibleName('Street 1 of 3: Jalan Makyong, Warning');
    expect(buttons[1]).toHaveAttribute('aria-current', 'true');
    expect(buttons[0]).not.toHaveAttribute('aria-current');
  });

  it('colours the dot of a street at Warning or Danger', () => {
    renderBar();
    const [warn, watch] = screen.getAllByRole('button', { name: /^Street/ });
    expect(warn).toHaveAttribute('data-alert', 'warning');
    expect(watch).not.toHaveAttribute('data-alert');
  });

  it('jumps to a street when its dot is tapped', () => {
    const onDot = renderBar();
    fireEvent.click(screen.getByRole('button', { name: /Street 3 of 3/ }));
    expect(onDot).toHaveBeenCalledWith(2);
  });

  it('names the dots in Malay', () => {
    render(<MemoryRouter><PageDots lang="ms" dots={dots} active={0} onDot={() => {}} /></MemoryRouter>);
    expect(screen.getByRole('button', { name: 'Jalan 1 daripada 3: Jalan Makyong, Amaran' })).toBeInTheDocument();
  });
});

describe('PageDots with a single street', () => {
  it('draws nothing for one street, since there is nowhere to swipe', () => {
    const { container } = render(<MemoryRouter><PageDots lang="en" dots={[dots[0]]} active={0} onDot={() => {}} /></MemoryRouter>);
    expect(container).toBeEmptyDOMElement();
  });
});
