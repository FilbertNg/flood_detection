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

  it('says so when there are no readings', () => {
    render(<StationChart station={wl} series={[]} />);
    expect(screen.getByText('No readings in this period.')).toBeInTheDocument();
  });
});
