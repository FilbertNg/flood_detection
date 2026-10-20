import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { BottomBar } from './BottomBar';

afterEach(cleanup);

const dots = [
  { id: 'a', name: 'Jalan Makyong', level: 'warning' as const },
  { id: 'b', name: 'Persiaran Batu Belah', level: 'watch' as const },
  { id: 'c', name: 'Jalan Mock', level: 'normal' as const },
];

function renderBar(props: Partial<Parameters<typeof BottomBar>[0]> = {}) {
  const onDot = vi.fn();
  render(<MemoryRouter><BottomBar lang="en" dots={dots} active={1} onDot={onDot} {...props} /></MemoryRouter>);
  return onDot;
}

describe('BottomBar', () => {
  it('links to the flood map and the street list', () => {
    renderBar();
    expect(screen.getByRole('link', { name: 'Flood map' })).toHaveAttribute('href', '/map');
    expect(screen.getByRole('link', { name: 'My streets' })).toHaveAttribute('href', '/streets');
  });

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

  it('shows no dots for a single unsaved street', () => {
    renderBar({ dots: undefined });
    expect(screen.queryByRole('button', { name: /^Street/ })).toBeNull();
    expect(screen.getByRole('link', { name: 'Flood map' })).toBeInTheDocument();
  });

  it('names the dots in Malay', () => {
    render(<MemoryRouter><BottomBar lang="ms" dots={dots} active={0} onDot={() => {}} /></MemoryRouter>);
    expect(screen.getByRole('button', { name: 'Jalan 1 daripada 3: Jalan Makyong, Amaran' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Peta banjir' })).toBeInTheDocument();
  });
});
