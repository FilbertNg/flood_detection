import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { levelSeriesPekanMeru, rainSeries26558, stations } from '@floodready/shared/mocks';
import { StationChart } from './StationChart';

afterEach(cleanup);
const rf = stations.find((s) => s.kind === 'rf')!;
const wl = stations.find((s) => s.kind === 'wl')!;

describe('StationChart', () => {
  it('draws one bar per 15-minute rain reading and the JPS intensity lines', () => {
    const { container } = render(<StationChart station={rf} series={rainSeries26558} />);
    expect(container.querySelectorAll('[data-bar]')).toHaveLength(rainSeries26558.length);
    expect(container.querySelector('[data-threshold="heavy"]')).not.toBeNull();
    expect(container.querySelector('[data-threshold="very heavy"]')).not.toBeNull();
    expect(screen.getByText('Kg. Perepat, Kapar')).toBeInTheDocument();
  });

  it('draws the river level with alert, warning and danger lines', () => {
    const { container } = render(<StationChart station={wl} series={levelSeriesPekanMeru} />);
    expect(container.querySelector('[data-line="level"]')).not.toBeNull();
    for (const name of ['alert', 'warning', 'danger']) {
      expect(container.querySelector(`[data-threshold="${name}"]`)).not.toBeNull();
    }
    expect(screen.getByText(/Warning 4\.00 m/)).toBeInTheDocument();
  });

  it('labels the rain lines as a JPS guide, not our trigger', () => {
    render(<StationChart station={rf} series={rainSeries26558} />);
    expect(screen.getByText('JPS rain guide 31 mm/h')).toBeInTheDocument();
    expect(screen.getByText('60 mm/h')).toBeInTheDocument();
  });

  it('shows the date on the x-axis when the range spans midnight', () => {
    const series = [
      { time: '2024-11-11T23:00:00+08:00', rain_15min_mm: 1, wl_m: null },
      { time: '2024-11-12T01:00:00+08:00', rain_15min_mm: 2, wl_m: null },
    ];
    render(<StationChart station={rf} series={series} />);
    expect(screen.getByText('11 Nov 23:00')).toBeInTheDocument();
    expect(screen.getByText('12 Nov 01:00')).toBeInTheDocument();
  });

  it('gives the chart a text summary for screen readers', () => {
    render(<StationChart station={wl} series={levelSeriesPekanMeru} />);
    expect(screen.getByRole('img').getAttribute('aria-label')).toMatch(/latest 4\.21 m.*highest 4\.21 m/);
  });

  it('keeps the unit label clear of the top tick', () => {
    const { container } = render(<StationChart station={wl} series={levelSeriesPekanMeru} />);
    const unit = container.querySelector('[data-unit]')!;
    const ticks = [...container.querySelectorAll('[data-tick]')].map((t) => Number(t.getAttribute('y')));
    expect(Math.min(...ticks) - Number(unit.getAttribute('y'))).toBeGreaterThanOrEqual(10);
  });

  it('says so when there are no readings', () => {
    render(<StationChart station={wl} series={[]} />);
    expect(screen.getByText('No readings in this period.')).toBeInTheDocument();
  });
});
