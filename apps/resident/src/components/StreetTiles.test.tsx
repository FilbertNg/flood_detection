import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { RainCurve, RiverMeter, TideChart } from './StreetTiles';

afterEach(cleanup);

const T = (hm: string) => `2024-11-12T${hm}:00+08:00`;

describe('RainCurve', () => {
  const rain = [{ time: T('10:00'), mm: 2.1 }, { time: T('11:00'), mm: 0 }, { time: T('12:00'), mm: 0 }];
  const weather = [
    { hour: '2024-11-12T10', code: 63, isDay: true, rainChance: 80 },
    { hour: '2024-11-12T11', code: 3, isDay: true, rainChance: 30 },
  ];

  it('labels the first hour "Now" with its chance in the bubble, then time, icon and our mm per hour', () => {
    const { container } = render(<RainCurve lang="en" rain={rain} weather={weather} />);
    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent('Now');
    expect(items[0]).toHaveTextContent('2.1 mm');
    expect(items[0].querySelector('[data-icon="rain"]')).not.toBeNull();
    expect(items[1]).toHaveTextContent('11:00');
    expect(container.querySelector('[data-now]')).toHaveTextContent('80%');
    expect(container.querySelector('[data-guide]')).not.toBeNull();
  });

  it('breaks the line where Open-Meteo has no chance for an hour', () => {
    const { container } = render(<RainCurve lang="en" rain={rain} weather={weather} />);
    // 12:00 has no weather hour, so only the 10:00 to 11:00 stretch is drawn and no % label for 12:00.
    expect(container.querySelectorAll('[data-line]')).toHaveLength(1);
    expect(container.querySelectorAll('[data-pct]')).toHaveLength(1);
  });

  it('keeps the empty state when there is no forecast', () => {
    render(<RainCurve lang="ms" rain={[]} weather={null} />);
    expect(screen.getByText('Tiada ramalan hujan.')).toBeInTheDocument();
  });
});

describe('RiverMeter', () => {
  it('places the marker for the level between the JPS marks', () => {
    const { container } = render(<RiverMeter wl={3.8} th={{ alert: 3.8, warning: 4.0, danger: 4.2 }} />);
    const now = container.querySelector('.river-now') as HTMLElement;
    expect(parseFloat(now.style.left)).toBeCloseTo((1.2 / 1.9) * 100);
  });
});

describe('TideChart', () => {
  const tide = [
    { time: T('08:00'), height_m: 0.4, filled: false },
    { time: T('09:00'), height_m: 0.2, filled: false },
    { time: T('10:00'), height_m: 0.9, filled: false },
    { time: T('11:00'), height_m: 1.3, filled: false },
    { time: T('12:00'), height_m: 1.1, filled: false },
  ];

  it('names the next high tide after the data time and whether the water is rising', () => {
    render(<TideChart lang="en" tide={tide} dataTime={T('09:30')} />);
    expect(screen.getByText('High tide 11:00 · 1.3 m')).toBeInTheDocument();
    expect(screen.getByText('Rising')).toBeInTheDocument();
  });

  it('marks now inside the chart (never clipped at the edge) with a visible ring', () => {
    const { container } = render(<TideChart lang="en" tide={tide} dataTime={T('08:00')} />);
    const now = container.querySelector('[data-now] circle') as SVGCircleElement;
    const x = Number(now.getAttribute('cx')), r = Number(now.getAttribute('r'));
    expect(x - r).toBeGreaterThanOrEqual(0);
    expect(now.getAttribute('fill')).not.toBe(now.getAttribute('stroke'));
    expect(container.querySelector('[data-now]')).toHaveTextContent('Now');
  });

  it('labels the hours along the bottom', () => {
    const { container } = render(<TideChart lang="en" tide={tide} dataTime={T('09:00')} />);
    const labels = [...container.querySelectorAll('[data-hour]')].map((n) => n.textContent);
    expect(labels).toContain('08:00');
    expect(labels).toContain('12:00');
  });

  it('shows a readout for the pin, at now by default', () => {
    render(<TideChart lang="en" tide={tide} dataTime={T('09:00')} />);
    // The one red pin starts on now.
    expect(document.querySelectorAll('[data-pin]')).toHaveLength(1);
    expect(document.querySelector('[data-pin]')).toHaveAttribute('data-now');
    const readout = document.querySelector('.tide-readout')!;
    expect(readout).toHaveTextContent('Now');
    expect(readout).toHaveTextContent('0.2 m');
    expect(readout).toHaveTextContent('Rising');
    expect(screen.queryByRole('button', { name: 'Back to now' })).toBeNull();
  });

  it('moves the pin with the arrow keys and updates the readout and the next high tide', () => {
    render(<TideChart lang="en" tide={tide} dataTime={T('09:00')} />);
    const slider = screen.getByRole('slider', { name: /Tide time/ });
    fireEvent.keyDown(slider, { key: 'ArrowRight' });
    fireEvent.keyDown(slider, { key: 'ArrowRight' });
    const readout = document.querySelector('.tide-readout')!;
    expect(readout).toHaveTextContent('10:00');
    expect(readout).toHaveTextContent('0.9 m');
    expect(slider).toHaveAttribute('aria-valuetext', '10:00 · 0.9 m · Rising');
    // One red pin only: it left now, and its tag shows the time it reads.
    expect(document.querySelectorAll('[data-pin]')).toHaveLength(1);
    expect(document.querySelector('[data-now]')).toBeNull();
    expect(document.querySelector('[data-pin]')).toHaveTextContent('10:00');
    fireEvent.keyDown(slider, { key: 'End' });
    expect(readout).toHaveTextContent('12:00');
    expect(readout).toHaveTextContent('Falling');
    fireEvent.click(screen.getByRole('button', { name: 'Back to now' }));
    expect(readout).toHaveTextContent('Now');
  });

  it('follows a drag along the curve', () => {
    render(<TideChart lang="en" tide={tide} dataTime={T('09:00')} />);
    const slider = screen.getByRole('slider', { name: /Tide time/ });
    // jsdom has no layout: give the chart a 320 px box at the page's left edge (the viewBox width).
    slider.getBoundingClientRect = () => ({ left: 0, width: 320, top: 0, height: 168, right: 320, bottom: 168, x: 0, y: 0, toJSON: () => ({}) });
    // Plot area 14 to 306 px: 3 of 4 steps across is 11:00.
    // jsdom drops clientX from pointer events; a mouse event of type pointerdown keeps it.
    fireEvent(slider, new MouseEvent('pointerdown', { bubbles: true, clientX: 14 + 0.75 * 292 }));
    expect(document.querySelector('.tide-readout')).toHaveTextContent('11:00');
    expect(document.querySelector('.tide-readout')).toHaveTextContent('1.3 m');
  });

  it('switches between the next 6 hours and all 12, starting the pin on now again', () => {
    const long = Array.from({ length: 13 }, (_, i) => ({ time: T(`${String(8 + i).padStart(2, '0')}:00`), height_m: Math.sin(i / 2), filled: false }));
    render(<TideChart lang="en" tide={long} dataTime={T('09:00')} />);
    const range = screen.getByRole('group', { name: 'Tide range' });
    const hours = () => [...document.querySelectorAll('[data-hour]')].map((n) => n.textContent);
    expect(within(range).getByRole('button', { name: '12 h' })).toHaveAttribute('aria-pressed', 'true');
    expect(hours()[0]).toBe('08:00');
    expect(hours().at(-1)).toBe('20:00');
    fireEvent.keyDown(screen.getByRole('slider', { name: /Tide time/ }), { key: 'End' });
    fireEvent.click(within(range).getByRole('button', { name: '6 h' }));
    expect(within(range).getByRole('button', { name: '6 h' })).toHaveAttribute('aria-pressed', 'true');
    // From the current hour (09:00) to six hours on.
    expect(hours()[0]).toBe('09:00');
    expect(hours().at(-1)).toBe('15:00');
    expect(document.querySelector('.tide-readout')).toHaveTextContent('Now');
  });

  it('keeps the empty state with fewer than two points', () => {
    render(<TideChart lang="en" tide={tide.slice(0, 1)} dataTime={T('09:00')} />);
    expect(screen.getByText('No tide data.')).toBeInTheDocument();
  });
});
