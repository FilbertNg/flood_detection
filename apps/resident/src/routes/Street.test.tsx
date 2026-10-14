import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { streetDetail } from '@floodready/shared/mocks';
import { StreetPage } from './Street';

function renderStreet(lang: 'en' | 'ms') {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(streetDetail), { status: 200 })));
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

afterEach(() => vi.unstubAllGlobals());

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
});
