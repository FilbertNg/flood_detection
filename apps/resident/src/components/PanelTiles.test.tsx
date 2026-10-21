import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { streetDetail } from '@floodready/shared/mocks';
import { ModelTile, RainNextTile, RainNowTile, RiverTile, StreetTile, TideTile, UpdatedTile, WhyTile } from './PanelTiles';

afterEach(cleanup);

const T = (hm: string) => `2024-11-12T${hm}:00+08:00`;
const tile = (title: string) => screen.getByRole('heading', { name: title }).closest('.ptile') as HTMLElement;
const pictures = (el: HTMLElement) => [...el.querySelectorAll('svg.pic')];

describe('RainNowTile', () => {
  it('shows the gauge mm with the plain word and a drop picture hidden from screen readers', () => {
    render(<RainNowTile lang="en" gauge={{ mm: 61.5, station: 'Kg. Perepat, Kapar' }} />);
    const el = tile('Rain now');
    expect(el).toHaveTextContent('61.5mm');
    expect(el).toHaveTextContent('Heavy');
    expect(el).toHaveTextContent('in the last hour, nearest gauge');
    expect(pictures(el)).toHaveLength(1);
    expect(pictures(el)[0]).toHaveAttribute('aria-hidden', 'true');
  });

  it('shows 0 mm and "None now" when no gauge is raining (Malay)', () => {
    render(<RainNowTile lang="ms" gauge={null} />);
    const el = tile('Hujan sekarang');
    expect(el).toHaveTextContent('0mm');
    expect(el).toHaveTextContent('Tiada sekarang');
  });
});

describe('RainNextTile', () => {
  it('totals the next 12 hours and names the heaviest hour, one bar per hour', () => {
    render(<RainNextTile lang="en" rain={streetDetail.rain_next_12h} />);
    const el = tile('Next 12 hours');
    expect(el).toHaveTextContent('2.5mm');
    expect(el).toHaveTextContent('Heaviest around 10:00');
    expect(el.querySelectorAll('[data-hour-bar]')).toHaveLength(3);
  });

  it('says no rain is expected when every hour is dry', () => {
    render(<RainNextTile lang="en" rain={streetDetail.rain_next_12h.map((p) => ({ ...p, mm: 0 }))} />);
    expect(tile('Next 12 hours')).toHaveTextContent('No rain expected');
  });

  it('says there is no forecast, with no total, when the API sends no hours (e.g. a replay)', () => {
    render(<RainNextTile lang="en" rain={[]} />);
    const el = tile('Next 12 hours');
    expect(el).toHaveTextContent('No rain forecast.');
    expect(el).not.toHaveTextContent('mm');
    expect(el).not.toHaveTextContent('No rain expected');
  });
});

describe('RiverTile', () => {
  const river = { wl: 3.52, th: { alert: 3.8, warning: 4.0, danger: 4.2 }, name: 'Sg. Binjai di Pekan Meru' };

  it('shows the level, the status chip, the gap to the next mark, the station and the A W D ticks', () => {
    render(<RiverTile lang="en" river={river} reachBy={T('10:00')} />);
    const el = tile('River level');
    expect(el).toHaveTextContent('3.52m');
    expect(el).toHaveTextContent('Close to alert');
    expect(el).toHaveTextContent('0.28 m below the alert line');
    expect(el).toHaveTextContent('Measured at Sg. Binjai di Pekan Meru');
    expect(el).toHaveTextContent('Estimate: may reach the warning line by 10:00');
    expect([...el.querySelectorAll('[data-tick]')].map((n) => n.getAttribute('data-tick'))).toEqual(['alert', 'warning', 'danger']);
  });

  it('shows the no-reading text and no picture without a fresh river reading', () => {
    render(<RiverTile lang="en" river={null} reachBy={null} />);
    const el = tile('River level');
    expect(el).toHaveTextContent('No reading right now');
    expect(pictures(el)).toHaveLength(0);
  });
});

describe('StreetTile', () => {
  it('shows the score in a badge with the word, five dots and the note', () => {
    render(<StreetTile lang="en" score={5} />);
    const el = tile('This street');
    expect(el).toHaveTextContent('5');
    expect(el).toHaveTextContent('of 5');
    expect(el).toHaveTextContent('Low-lying');
    expect(el).toHaveTextContent('How easily this street floods, from the ground shape');
    expect(el.querySelectorAll('[data-dot][data-on]')).toHaveLength(5);
    expect(el.querySelector('[data-tone]')).toHaveAttribute('data-tone', 'warn');
  });
});

describe('TideTile', () => {
  it('shows the next high water, its height and whether the water is rising, with the wave', () => {
    render(<TideTile lang="en" tide={streetDetail.tide} dataTime={streetDetail.data_time} />);
    const el = tile('Tide · Port Klang');
    expect(el).toHaveTextContent('Next high water');
    expect(el).toHaveTextContent('11:00');
    expect(el).toHaveTextContent('2.2 m');
    expect(el).toHaveTextContent('Rising');
    expect(el).toHaveTextContent('High tide only matters when it meets heavy rain: drains empty slower.');
    expect(pictures(el)).toHaveLength(1);
  });

  it('says there is no tide data with fewer than two hours', () => {
    render(<TideTile lang="en" tide={[]} dataTime={streetDetail.data_time} />);
    expect(tile('Tide · Port Klang')).toHaveTextContent('No tide data.');
  });
});

describe('ModelTile', () => {
  it('shows the chance in a ring with the information note', () => {
    render(<ModelTile lang="en" p={0.62} />);
    const el = tile('Flood model');
    expect(el).toHaveTextContent('62%');
    expect(el).toHaveTextContent('For information; alerts follow JPS.');
    expect(el.querySelector('[data-tone]')).toHaveAttribute('data-tone', 'warn');
  });

  it('is hidden when the model has no value', () => {
    const { container } = render(<ModelTile lang="en" p={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe('UpdatedTile', () => {
  it('shows the data time on a clock, how often it updates and the sources', () => {
    render(<UpdatedTile lang="en" dataTime={T('09:00')} />);
    const el = tile('Updated');
    expect(el).toHaveTextContent('09:00');
    expect(el).toHaveTextContent('every 15 min');
    expect(el).toHaveTextContent('JPS Infobanjir, Open-Meteo');
  });
});

describe('WhyTile', () => {
  it('lists the reasons, or says there are no flood signals', () => {
    render(<WhyTile lang="en" reasons={streetDetail.reasons} />);
    expect(tile('Why this level')).toHaveTextContent('61.5 mm of rain in 1 h at Kg. Perepat, Kapar');
    cleanup();
    render(<WhyTile lang="ms" reasons={[]} />);
    expect(tile('Kenapa tahap ini')).toHaveTextContent('Tiada tanda banjir buat masa ini.');
  });
});
