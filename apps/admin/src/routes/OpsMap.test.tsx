import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { status, stations, streets } from '@floodready/shared/mocks';
import type { Station, Status } from '@floodready/shared';
import { renderApp, stubApi } from '../test-utils';
import { OpsMapPage } from './OpsMap';

vi.mock('../components/OpsMapView', () => ({ OpsMapView: () => <div data-testid="map" /> }));

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
    expect(await screen.findByText('2 at Warning or Danger')).toBeInTheDocument();
    expect(screen.getByText('1 at Watch')).toBeInTheDocument();
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

  it('lists Warning and Danger streets as links to their detail page', async () => {
    stubApi({ 'GET /status': live, 'GET /streets': streets, 'GET /stations': stations });
    renderApp(<OpsMapPage />);
    const link = await screen.findByRole('link', { name: /Jalan Makyong/ });
    expect(link).toHaveAttribute('href', '/street/BBR-jalan-makyong');
  });

  it('shows the replay ribbon and a stop button in replay mode', async () => {
    const fn = stubApi({
      'GET /status': status,
      'GET /streets': streets,
      'GET /stations': stations,
      'DELETE /admin/replay': live,
    });
    renderApp(<OpsMapPage />);
    expect(await screen.findByText(/Replay: 12 Nov 2024, 09:00/)).toBeInTheDocument();
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
});
