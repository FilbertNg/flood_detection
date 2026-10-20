import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { stats } from '@floodready/shared/mocks';
import { OutcomeChart, StationHealthChart, TopStreetsChart } from './StatsCharts';

afterEach(cleanup);

describe('OutcomeChart', () => {
  it('splits alerts into confirmed, not confirmed and unverified with a text summary', () => {
    const { container } = render(<OutcomeChart kpis={{ ...stats.kpis, alerts: 10, confirmed: 3, not_confirmed: 2, unverified: 5 }} />);
    expect(screen.getByRole('img', { name: /10 alerts: 3 confirmed, 2 not confirmed, 5 unverified/ })).toBeInTheDocument();
    const widths = ['confirmed', 'not_confirmed', 'unverified'].map((k) => container.querySelector(`[data-seg="${k}"]`)!.getAttribute('width'));
    expect(widths.map(Number)).toEqual([30, 20, 50]);
  });

  it('shows an empty message when there are no alerts', () => {
    render(<OutcomeChart kpis={{ ...stats.kpis, alerts: 0, confirmed: 0, not_confirmed: 0, unverified: 0 }} />);
    expect(screen.getByText('No alerts to break down in this period.')).toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
});

describe('TopStreetsChart', () => {
  const rows = Array.from({ length: 12 }, (_, i) => ({ street_id: `s${i}`, name: `Street ${i}`, alerts: i + 1, confirmed: i % 2, floods: 0 }));

  it('draws the ten streets with the most alerts, busiest first', () => {
    const { container } = render(<TopStreetsChart rows={rows} />);
    const names = [...container.querySelectorAll('[data-name]')].map((n) => n.textContent);
    expect(names).toEqual(['Street 11', 'Street 10', 'Street 9', 'Street 8', 'Street 7', 'Street 6', 'Street 5', 'Street 4', 'Street 3', 'Street 2']);
    expect(screen.getByRole('img', { name: /Top 10 streets by alerts, highest Street 11 with 12/ })).toBeInTheDocument();
  });

  it('shows an empty message when no street has alerts', () => {
    render(<TopStreetsChart rows={[{ street_id: 'a', name: 'A', alerts: 0, confirmed: 0, floods: 1 }]} />);
    expect(screen.getByText('No streets with alerts in this period.')).toBeInTheDocument();
  });
});

describe('StationHealthChart', () => {
  it('draws stale share per station, worst first, and marks mostly offline ones', () => {
    const { container } = render(
      <StationHealthChart rows={[{ graph_id: '1', name: 'Fine', stale_pct: 0.04 }, { graph_id: '2', name: 'Dead', stale_pct: 0.93 }]} />,
    );
    const names = [...container.querySelectorAll('[data-name]')].map((n) => n.textContent);
    expect(names).toEqual(['Dead', 'Fine']);
    expect(container.querySelector('[data-offline="2"]')).not.toBeNull();
    expect(container.querySelector('[data-offline="1"]')).toBeNull();
    expect(screen.getByRole('img', { name: /2 stations, 1 mostly offline/ })).toBeInTheDocument();
  });
});
