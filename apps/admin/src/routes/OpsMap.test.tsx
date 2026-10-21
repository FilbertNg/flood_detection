import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { status, stations, streets } from '@floodready/shared/mocks';
import type { Station, Status } from '@floodready/shared';
import { renderApp, stubApi } from '../test-utils';
import { OpsMapPage } from './OpsMap';

// The real map is Leaflet; the stand-in calls onFocus as zooming in on a street would, and shows
// `children` (the popup content) like the real map does on the focused street.
vi.mock('../components/OpsMapView', () => ({
  OpsMapView: ({ onFocus, children }: { onFocus: (id: string | null) => void; children?: ReactNode }) => (
    <div data-testid="map">
      {children}
      <button type="button" onClick={() => onFocus('BBR-jalan-makyong')}>zoom to Jalan Makyong</button>
      <button type="button" onClick={() => onFocus(null)}>zoom out</button>
    </div>
  ),
}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const live: Status = { ...status, mode: 'live', replay: null };
const staleStations: Station[] = [{ ...stations[0], is_stale: true }, stations[1]];

function methods(fn: ReturnType<typeof stubApi>): string[] {
  return fn.mock.calls.map((c) => (c[1] as RequestInit | undefined)?.method ?? 'GET');
}

describe('OpsMapPage', () => {
  it('shows the legend, level counts, credits with Sources, and stale stations', async () => {
    stubApi({ 'GET /status': live, 'GET /streets': streets, 'GET /stations': staleStations });
    renderApp(<OpsMapPage />);
    // Two panels: red for Warning or Danger, yellow for Watch (the counts fill in once the streets load).
    await waitFor(() => expect(document.querySelector('.count-box[data-kind="risk"]')!.textContent).toBe('2at Warning or Danger'));
    expect(document.querySelector('.count-box[data-kind="watch"]')!.textContent).toBe('1at Watch');
    expect(screen.getByLabelText('Legend')).toHaveTextContent('Danger');
    expect(screen.getByText(/^© OpenStreetMap contributors · JPS Public Infobanjir/)).toBeInTheDocument();
    expect(screen.getByText('Sources')).toBeInTheDocument();
    expect(screen.getByText(/Kg\. Perepat, Kapar.*stale/)).toBeInTheDocument();
  });

  it('cancel leaves replay untouched', async () => {
    const fn = stubApi({ 'GET /status': live, 'GET /streets': streets, 'GET /stations': stations });
    renderApp(<OpsMapPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Start replay: 12 Nov 2024' }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(methods(fn)).not.toContain('POST');
    expect(screen.getByRole('button', { name: 'Start replay: 12 Nov 2024' })).toBeInTheDocument();
  });

  it('drops down the Warning or Danger streets from the red panel, as links to their detail page', async () => {
    stubApi({ 'GET /status': live, 'GET /streets': streets, 'GET /stations': stations });
    renderApp(<OpsMapPage />);
    const risk = await screen.findByRole('button', { name: /at Warning or Danger/ });
    await waitFor(() => expect(risk).toHaveTextContent('2'));
    expect(risk).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('link', { name: /Jalan Makyong/ })).toBeNull();
    fireEvent.click(risk);
    expect(risk).toHaveAttribute('aria-expanded', 'true');
    const list = screen.getByRole('list', { name: 'Streets at Warning or Danger' });
    expect(within(list).getByRole('link', { name: /Jalan Makyong/ })).toHaveAttribute('href', '/street/BBR-jalan-makyong');
    expect(within(list).getAllByRole('listitem')).toHaveLength(2);
    fireEvent.click(risk);
    expect(screen.queryByRole('list', { name: 'Streets at Warning or Danger' })).toBeNull();
  });

  it('drops down the Watch streets under the yellow panel, each panel with its own list', async () => {
    stubApi({ 'GET /status': live, 'GET /streets': streets, 'GET /stations': stations });
    renderApp(<OpsMapPage />);
    const risk = await screen.findByRole('button', { name: /at Warning or Danger/ });
    const watch = screen.getByRole('button', { name: /at Watch/ });
    await waitFor(() => expect(watch).toHaveTextContent('1'));
    fireEvent.click(risk);
    fireEvent.click(watch);
    // Both lists stay open, each straight under its own panel.
    const riskList = screen.getByRole('list', { name: 'Streets at Warning or Danger' });
    expect(risk.nextElementSibling).toContainElement(riskList);
    const list = screen.getByRole('list', { name: 'Streets at Watch' });
    expect(watch.nextElementSibling).toContainElement(list);
    expect(within(list).getByRole('link', { name: /Persiaran Batu Belah/ })).toHaveAttribute('href', '/street/BBR-persiaran-batu-belah');
  });

  it('shows the replay chip on the map and a stop button in replay mode', async () => {
    const fn = stubApi({
      'GET /status': status,
      'GET /streets': streets,
      'GET /stations': stations,
      'DELETE /admin/replay': live,
    });
    renderApp(<OpsMapPage />);
    // A small chip floats on the map; the explanation sits in the Demo replay card.
    const chip = (await screen.findByText('12 Nov 2024 flood')).closest('.mode-chip')!;
    expect(chip.closest('.ops-map')).not.toBeNull();
    expect(chip).toHaveTextContent('Replay');
    expect(chip.querySelector('time')).toHaveTextContent('09:00');
    expect(document.querySelector('.ribbon')).toBeNull();
    expect(screen.getByText(/flagged as replay and excluded from statistics/).closest('.card')).toHaveTextContent('Demo replay');
    fireEvent.click(screen.getByRole('button', { name: 'Stop replay' }));
    expect(screen.getByText(/returns to live/)).toBeInTheDocument();
    expect(methods(fn)).not.toContain('DELETE');
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));
    await waitFor(() => expect(methods(fn)).toContain('DELETE'));
  });

  it('starts the 12 Nov 2024 replay from live mode', async () => {
    const fn = stubApi({
      'GET /status': live,
      'GET /streets': streets,
      'GET /stations': stations,
      'POST /admin/replay': status,
    });
    renderApp(<OpsMapPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Start replay: 12 Nov 2024' }));
    expect(methods(fn)).not.toContain('POST');
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));
    await waitFor(() => expect(methods(fn)).toContain('POST'));
    const post = fn.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === 'POST')!;
    expect(JSON.parse((post[1] as RequestInit).body as string)).toEqual({ event: '2024-11-12', speed: 60 });
  });

  it('shows a popup for the street under the map centre once zoomed in, with its level and View', async () => {
    stubApi({ 'GET /status': live, 'GET /streets': streets, 'GET /stations': stations });
    renderApp(<OpsMapPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'zoom to Jalan Makyong' }));
    const card = screen.getByRole('region', { name: 'Jalan Makyong' });
    expect(card).toHaveTextContent('Warning');
    expect(within(card).getByRole('link', { name: 'View' })).toHaveAttribute('href', '/street/BBR-jalan-makyong');
    fireEvent.click(screen.getByRole('button', { name: 'zoom out' }));
    expect(screen.queryByRole('region', { name: 'Jalan Makyong' })).toBeNull();
  });

  it('shows a live chip on the map in live mode', async () => {
    stubApi({ 'GET /status': live, 'GET /streets': streets, 'GET /stations': stations });
    renderApp(<OpsMapPage />);
    const chip = (await screen.findByText(/^Live/)).closest('.mode-chip')!;
    expect(chip.closest('.ops-map')).not.toBeNull();
    expect(screen.queryByText(/excluded from statistics/)).toBeNull();
  });
});
