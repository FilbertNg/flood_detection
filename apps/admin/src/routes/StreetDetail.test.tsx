import { cleanup, screen } from '@testing-library/react';
import { Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { levelSeriesPekanMeru, rainSeries26558, stations, streetDetail } from '@floodready/shared/mocks';
import { renderApp, stubApi } from '../test-utils';
import { StreetDetailPage } from './StreetDetail';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function show() {
  const fn = stubApi({
    'GET /streets/BBR-jalan-makyong': streetDetail,
    'GET /stations': stations,
    'GET /stations/26558/series': rainSeries26558,
    'GET /stations/PEKANMERU/series': levelSeriesPekanMeru,
  });
  renderApp(
    <Routes><Route path="/street/:id" element={<StreetDetailPage />} /></Routes>,
    '/street/BBR-jalan-makyong',
  );
  return fn;
}

describe('StreetDetailPage', () => {
  it('draws both the rain and the river chart when a graph_id is shared, and shows credits', async () => {
    const shared = { ...stations[1], graph_id: '26558' };
    const fn = stubApi({
      'GET /streets/BBR-jalan-makyong': streetDetail,
      'GET /stations': [stations[0], shared, stations[1]],
      'GET /stations/26558/series': rainSeries26558.map((p) => ({ ...p, wl_m: 3 })),
      'GET /stations/PEKANMERU/series': levelSeriesPekanMeru,
    });
    renderApp(<Routes><Route path="/street/:id" element={<StreetDetailPage />} /></Routes>, '/street/BBR-jalan-makyong');
    expect(await screen.findAllByRole('img', { name: /readings/ })).toHaveLength(3);
    expect(fn.mock.calls.filter((c) => String(c[0]).includes('/stations/26558/series'))).toHaveLength(1);
    expect(screen.getByText('Sources')).toBeInTheDocument();
  });

  it('shows level, window, reasons, probability and the river forecast', async () => {
    show();
    expect(await screen.findByRole('heading', { name: 'Jalan Makyong' })).toBeInTheDocument();
    expect(screen.getByText('Warning')).toBeInTheDocument();
    expect(screen.getByText(/09:30 to 10:30/)).toBeInTheDocument();
    expect(screen.getByText('61.5 mm of rain in 1 h at Kg. Perepat, Kapar')).toBeInTheDocument();
    expect(screen.getByText('62%')).toBeInTheDocument();
    expect(screen.getByText('likely 4.10 m (3.80 to 4.40 m) by 11:00')).toBeInTheDocument();
  });

  it('draws a chart for each of the street stations from their series', async () => {
    const fn = show();
    expect(await screen.findAllByRole('img', { name: /readings/ })).toHaveLength(2);
    const urls = fn.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.includes('/stations/26558/series'))).toBe(true);
    expect(urls.some((u) => u.includes('/stations/PEKANMERU/series'))).toBe(true);
  });
});
