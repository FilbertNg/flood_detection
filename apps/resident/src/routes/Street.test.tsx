import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { streetDetail } from '@floodready/shared/mocks';
import { StreetPage } from './Street';

function renderStreet(lang: 'en' | 'ms', detail: unknown = streetDetail) {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(detail), { status: 200 })));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/street/BBR-jalan-makyong']}>
        <Routes>
          <Route path="/street/:id" element={<StreetPage lang={lang} />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('StreetPage', () => {
  it('shows level, time window, ML probability and reasons in Malay', async () => {
    renderStreet('ms');
    expect(await screen.findByText('Jalan Makyong')).toBeInTheDocument();
    expect(screen.getByText('Amaran')).toBeInTheDocument();
    expect(screen.getByText(/antara 09:30 dan 10:30/)).toBeInTheDocument();
    expect(screen.getByText('62%')).toBeInTheDocument();
    expect(screen.getByText('Hujan 61.5 mm dalam 1 jam di Kg. Perepat, Kapar')).toBeInTheDocument();
    expect(screen.getByText(/JPS, MET dan NADMA ialah sumber rasmi/)).toBeInTheDocument();
  });

  it('shows advice for the level in English', async () => {
    renderStreet('en');
    expect(await screen.findByText(/Move your car to higher ground/)).toBeInTheDocument();
  });

  it('shows the river forecast with its range and the warning level', async () => {
    renderStreet('en');
    expect(await screen.findByRole('heading', { name: 'River forecast' })).toBeInTheDocument();
    expect(screen.getByText('likely 4.10 m (3.80 to 4.40 m) by 11:00')).toBeInTheDocument();
    expect(screen.getByText('likely 3.90 m (3.70 to 4.10 m) by 10:00')).toBeInTheDocument();
    expect(screen.getByText('Warning level: 4.00 m')).toBeInTheDocument();
    expect(screen.getByText('The upper estimate reaches the warning level.')).toBeInTheDocument();
  });

  it('hides the river forecast block when there is none', async () => {
    renderStreet('en', { ...streetDetail, river_forecast: null });
    expect(await screen.findByText('Jalan Makyong')).toBeInTheDocument();
    expect(screen.queryByText('River forecast')).not.toBeInTheDocument();
  });
});
