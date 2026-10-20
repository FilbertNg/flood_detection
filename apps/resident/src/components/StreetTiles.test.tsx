import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { RainCurve, RiverMeter, TideMini } from './StreetTiles';

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

describe('TideMini', () => {
  it('names the next high tide after the data time', () => {
    const tide = [
      { time: T('08:00'), height_m: 0.4, filled: false },
      { time: T('09:00'), height_m: 0.2, filled: false },
      { time: T('10:00'), height_m: 0.9, filled: false },
      { time: T('11:00'), height_m: 1.3, filled: false },
      { time: T('12:00'), height_m: 1.1, filled: false },
    ];
    render(<TideMini lang="en" tide={tide} dataTime={T('09:00')} />);
    expect(screen.getByText('High tide 11:00 · 1.3 m')).toBeInTheDocument();
  });
});
