import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { stations } from '@floodready/shared/mocks';
import { HourlyStrip, ProneTile, RiverTile, TideTile } from './StreetTiles';

afterEach(cleanup);

const T = (hm: string) => `2024-11-12T${hm}:00+08:00`;

describe('HourlyStrip', () => {
  it('shows each hour with our rain forecast, the weather icon and chance of rain when known', () => {
    render(
      <HourlyStrip
        lang="en"
        rain={[{ time: T('10:00'), mm: 2.1 }, { time: T('11:00'), mm: 0 }]}
        weather={[{ hour: '2024-11-12T10', code: 63, isDay: true, rainChance: 80 }]}
      />,
    );
    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent('10:00');
    expect(items[0]).toHaveTextContent('2.1 mm');
    expect(items[0]).toHaveTextContent('80%');
    expect(items[0].querySelector('[data-icon="rain"]')).not.toBeNull();
    expect(items[1]).toHaveTextContent('0 mm');
    expect(items[1].querySelector('[data-icon]')).toBeNull();
  });

  it('says so when there is no forecast', () => {
    render(<HourlyStrip lang="ms" rain={[]} weather={null} />);
    expect(screen.getByText('Tiada ramalan hujan.')).toBeInTheDocument();
  });
});

describe('RiverTile', () => {
  it('shows the street’s river station level against its JPS marks', () => {
    render(<RiverTile lang="en" stations={stations} ids={['26558', 'PEKANMERU']} />);
    expect(screen.getByText('3.52 m')).toBeInTheDocument();
    expect(screen.getByText('Sg. Binjai di Pekan Meru')).toBeInTheDocument();
    expect(screen.getByText('Alert 3.80 · Warning 4.00 · Danger 4.20 m')).toBeInTheDocument();
  });

  it('shows an honest empty state when no river reading is available', () => {
    render(<RiverTile lang="en" stations={{ bad: true }} ids={['PEKANMERU']} />);
    expect(screen.getByText('No river reading right now.')).toBeInTheDocument();
  });
});

describe('TideTile', () => {
  it('names the next high tide after the data time', () => {
    const tide = [
      { time: T('08:00'), height_m: 0.4, filled: false },
      { time: T('09:00'), height_m: 0.2, filled: false },
      { time: T('10:00'), height_m: 0.9, filled: false },
      { time: T('11:00'), height_m: 1.3, filled: false },
      { time: T('12:00'), height_m: 1.1, filled: false },
    ];
    render(<TideTile lang="en" tide={tide} dataTime={T('09:00')} />);
    expect(screen.getByText('High tide 11:00 · 1.3 m')).toBeInTheDocument();
  });
});

describe('ProneTile', () => {
  it('fills the meter to the rating', () => {
    const { container } = render(<ProneTile lang="en" rating={4} />);
    expect(screen.getByText('4 of 5')).toBeInTheDocument();
    expect(container.querySelectorAll('[data-on="true"]')).toHaveLength(4);
  });
});
