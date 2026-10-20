import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { stats } from '@floodready/shared/mocks';
import type { Stats } from '@floodready/shared';
import { renderApp, stubApi } from '../test-utils';
import { StatisticsPage } from './Statistics';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const data: Stats = {
  ...stats,
  by_street: [
    { street_id: 'a', name: 'Alpha', alerts: 4, confirmed: 2, floods: 3 },
    { street_id: 'b', name: 'Bravo', alerts: 9, confirmed: 1, floods: 1 },
  ],
  station_health: [
    { graph_id: '1', name: 'Fine station', stale_pct: 0.04 },
    { graph_id: '26558', name: 'Dead gauge', stale_pct: 0.93 },
  ],
  sources: { outcomes_from_news: 5, outcomes_from_residents: 2 },
};

describe('StatisticsPage', () => {
  it('shows KPI tiles, the unverified explanation, source note and replay note', async () => {
    stubApi({ 'GET /admin/stats': data });
    renderApp(<StatisticsPage />);
    const tiles = await screen.findByLabelText('Key figures');
    expect(within(tiles).getByText('Alerts').nextSibling).toHaveTextContent('12');
    expect(within(tiles).getByText('Confirmation rate').nextSibling).toHaveTextContent('42%');
    expect(within(tiles).getByText('Missed floods').nextSibling).toHaveTextContent('2');
    expect(within(tiles).getByText('Median lead time').nextSibling).toHaveTextContent('55 min');
    expect(within(tiles).getByText(/no answers yet/i)).toBeInTheDocument();
    expect(within(tiles).getByText(/not a false alarm/i)).toBeInTheDocument();
    expect(screen.getByText(/outcomes from news: 5 · from residents: 2/i)).toBeInTheDocument();
    expect(screen.getByText(/replay and demo data are excluded/i)).toBeInTheDocument();
  });

  it('leads with four headline figures with icons, and highlights missed floods when there are any', async () => {
    stubApi({ 'GET /admin/stats': data });
    renderApp(<StatisticsPage />);
    const tiles = await screen.findByLabelText('Key figures');
    const headline = [...tiles.querySelectorAll('.kpi-hero')].map((n) => n.querySelector('.kpi-label')!.textContent);
    expect(headline).toEqual(['Alerts', 'Confirmation rate', 'Median lead time', 'Missed floods']);
    for (const tile of tiles.querySelectorAll('.kpi')) expect(tile.querySelector('svg.kpi-icon')).not.toBeNull();
    expect(within(tiles).getByText('Missed floods').closest('.kpi')).toHaveAttribute('data-tone', 'alert');
  });

  it('does not highlight missed floods when there are none', async () => {
    stubApi({ 'GET /admin/stats': { ...data, kpis: { ...data.kpis, missed_floods: 0 } } });
    renderApp(<StatisticsPage />);
    const tiles = await screen.findByLabelText('Key figures');
    expect(within(tiles).getByText('Missed floods').closest('.kpi')).not.toHaveAttribute('data-tone', 'alert');
  });

  it('sums up what needs attention from the data: missed floods, offline stations, busiest street and week', async () => {
    stubApi({ 'GET /admin/stats': data });
    renderApp(<StatisticsPage />);
    const panel = await screen.findByRole('region', { name: 'Needs attention' });
    const items = within(panel).getAllByRole('listitem').map((li) => li.textContent);
    expect(items).toEqual([
      '2 floods were reported without an alert.',
      '1 station was offline more than half the time: Dead gauge.',
      'Most alerts: Bravo, 9 alerts (1 confirmed).',
      'Busiest week: 2024-W46, 3 alerts.',
    ]);
    expect(within(panel).getAllByRole('listitem')[0]).toHaveAttribute('data-tone', 'alert');
  });

  it('says all is clear when nothing needs attention', async () => {
    stubApi({ 'GET /admin/stats': { ...data, kpis: { ...data.kpis, missed_floods: 0 }, station_health: [], by_street: [], by_week: [] } });
    renderApp(<StatisticsPage />);
    const panel = await screen.findByRole('region', { name: 'Needs attention' });
    expect(panel).toHaveTextContent('Nothing needs attention in this period.');
  });

  it('shows n/a for the rate when no alert has an answer, and labels it', async () => {
    stubApi({ 'GET /admin/stats': { ...data, kpis: { ...data.kpis, confirmed: 0, not_confirmed: 0, confirmation_rate: 0 } } });
    renderApp(<StatisticsPage />);
    const tiles = await screen.findByLabelText('Key figures');
    const tile = within(tiles).getByText('Confirmation rate').parentElement!;
    expect(tile).toHaveTextContent('n/a');
    expect(tile).toHaveTextContent('no answered alerts yet');
    expect(tile).not.toHaveTextContent('0%');
  });

  it('labels the rate "of answered alerts" when there are answers', async () => {
    stubApi({ 'GET /admin/stats': data });
    renderApp(<StatisticsPage />);
    const tiles = await screen.findByLabelText('Key figures');
    expect(within(tiles).getByText('Confirmation rate').parentElement).toHaveTextContent('of answered alerts');
  });

  it('names streets in the rain chart table and keeps x labels unique', async () => {
    const two: Stats = {
      ...data,
      rain_at_onset: [
        { street_id: 'a', event_date: '2024-11-12', rain_2to4h_mm: 61.5 },
        { street_id: 'b', event_date: '2024-11-12', rain_2to4h_mm: 40 },
      ],
    };
    stubApi({ 'GET /admin/stats': two });
    renderApp(<StatisticsPage />);
    const chart = await screen.findByRole('img', { name: /rain at flood onset/i });
    const labels = Array.from(chart.querySelectorAll('text[data-xlabel]')).map((t) => t.textContent);
    expect(new Set(labels).size).toBe(2);
    expect(await screen.findAllByText('Alpha')).not.toHaveLength(0);
  });

  it('refetches when the period changes', async () => {
    const fn = stubApi({ 'GET /admin/stats': data });
    renderApp(<StatisticsPage />);
    await screen.findByLabelText('Key figures');
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2024-11-01' } });
    await waitFor(() => expect(fn.mock.calls.some((c) => String(c[0]).includes('from=2024-11-01'))).toBe(true));
  });

  it('picks the period from quick buttons, and clears the selection as soon as a date is clicked', async () => {
    const fn = stubApi({ 'GET /admin/stats': data });
    renderApp(<StatisticsPage />);
    await screen.findByLabelText('Key figures');
    const period = screen.getByRole('group', { name: 'Period' });
    expect(within(period).getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(within(period).getByRole('button', { name: 'Nov 2024 flood' }));
    expect(within(period).getByRole('button', { name: 'Nov 2024 flood' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByLabelText('From')).toHaveValue('2024-11-01');
    expect(screen.getByLabelText('To')).toHaveValue('2024-11-30');
    // The dates are in the fields, so the summary is just the length; quick periods and dates share one line.
    expect(screen.getByText('30 days', { selector: '.period-days' })).toBeInTheDocument();
    expect(screen.getByLabelText('From').closest('.period-bar')).toContainElement(period);
    await waitFor(() => expect(fn.mock.calls.some((c) => String(c[0]).includes('from=2024-11-01') && String(c[0]).includes('to=2024-11-30'))).toBe(true));
    expect(within(period).queryByRole('button', { name: 'Custom' })).toBeNull();
    // Clicking a date is choosing a custom range: no quick period stays selected, even before a change.
    fireEvent.focus(screen.getByLabelText('From'));
    expect(within(period).queryAllByRole('button', { pressed: true })).toHaveLength(0);
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2024-11-05' } });
    expect(within(period).queryAllByRole('button', { pressed: true })).toHaveLength(0);
    fireEvent.click(within(period).getByRole('button', { name: '30 days' }));
    expect(within(period).getByRole('button', { name: '30 days' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('sorts the street table by a clicked column', async () => {
    stubApi({ 'GET /admin/stats': data });
    renderApp(<StatisticsPage />);
    const table = await screen.findByRole('table', { name: 'Alerts by street' });
    const firstRow = () => within(table).getAllByRole('row')[1];
    fireEvent.click(within(table).getByRole('button', { name: /^Alerts/ }));
    expect(firstRow()).toHaveTextContent('Bravo');
    fireEvent.click(within(table).getByRole('button', { name: /^Street/ }));
    expect(firstRow()).toHaveTextContent('Alpha');
  });

  it('lists the dead gauge first with a high stale percentage', async () => {
    stubApi({ 'GET /admin/stats': data });
    renderApp(<StatisticsPage />);
    const table = await screen.findByRole('table', { name: 'Station health' });
    const rows = within(table).getAllByRole('row');
    expect(rows[1]).toHaveTextContent('Dead gauge');
    expect(rows[1]).toHaveTextContent('93%');
  });

  it('draws charts with an accessible summary', async () => {
    stubApi({ 'GET /admin/stats': data });
    renderApp(<StatisticsPage />);
    expect(await screen.findByRole('img', { name: /alerts per week/i })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /rain at flood onset/i })).toBeInTheDocument();
  });

  it('shows empty states instead of numbers when there is nothing', async () => {
    const empty: Stats = {
      ...data,
      kpis: { alerts: 0, confirmed: 0, not_confirmed: 0, unverified: 0, confirmation_rate: 0, missed_floods: 0, median_lead_min: null },
      by_week: [], by_street: [], rain_at_onset: [], station_health: [],
      sources: { outcomes_from_news: 0, outcomes_from_residents: 0 },
    };
    stubApi({ 'GET /admin/stats': empty });
    renderApp(<StatisticsPage />);
    expect(await screen.findByText(/no alerts in this period/i)).toBeInTheDocument();
    expect(screen.getByText(/no floods with rain readings/i)).toBeInTheDocument();
    expect(screen.queryByRole('table', { name: 'Alerts by street' })).toBeNull();
  });

  it('shows an error state', async () => {
    stubApi({ 'GET /admin/stats': () => ({ status: 500, body: {} }) });
    renderApp(<StatisticsPage />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load/i);
  });
});
