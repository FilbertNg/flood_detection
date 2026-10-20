import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { streets } from '@floodready/shared/mocks';
import * as geo from '../lib/geo';
import { FindStreetPage } from './FindStreet';

vi.mock('../lib/geo', async (importOriginal) => ({ ...(await importOriginal<typeof geo>()), currentPosition: vi.fn() }));
const position = vi.mocked(geo.currentPosition);

function renderFind(lang: 'en' | 'ms' = 'en') {
  const onSave = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter><FindStreetPage lang={lang} onSave={onSave} /></MemoryRouter>
    </QueryClientProvider>,
  );
  return onSave;
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(streets), { status: 200 })));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  position.mockReset();
});

describe('FindStreetPage', () => {
  it('asks for the location only after the button is tapped', async () => {
    renderFind();
    expect(await screen.findByRole('heading', { name: 'See flood warnings for your street' })).toBeInTheDocument();
    expect(position).not.toHaveBeenCalled();
    expect(screen.getByRole('link', { name: 'Choose from the list' })).toHaveAttribute('href', '/streets');
  });

  it('finds the nearest street on the phone and saves it on Yes', async () => {
    position.mockResolvedValue({ lat: 3.0899, lon: 101.4251 });
    const onSave = renderFind();
    fireEvent.click(await screen.findByRole('button', { name: 'Use my location' }));
    expect(await screen.findByText('Is this your street?')).toBeInTheDocument();
    expect(screen.getByText('Jalan Makyong')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Yes' }));
    expect(onSave).toHaveBeenCalledWith(['BBR-jalan-makyong']);
    // Only the location API was used; nothing was sent with the position.
    const calls = vi.mocked(fetch).mock.calls.map((c) => String(c[0]));
    expect(calls.some((u) => u.includes('3.0899') || u.includes('101.4251'))).toBe(false);
  });

  it('offers the list for another street', async () => {
    position.mockResolvedValue({ lat: 3.0899, lon: 101.4251 });
    renderFind();
    fireEvent.click(await screen.findByRole('button', { name: 'Use my location' }));
    expect(await screen.findByRole('link', { name: 'Choose another' })).toHaveAttribute('href', '/streets');
  });

  it('says so when the phone is outside Bandar Bukit Raja', async () => {
    position.mockResolvedValue({ lat: 3.139, lon: 101.687 });
    renderFind();
    fireEvent.click(await screen.findByRole('button', { name: 'Use my location' }));
    expect(await screen.findByText('You seem to be outside Bandar Bukit Raja.')).toBeInTheDocument();
    expect(screen.queryByText('Is this your street?')).toBeNull();
  });

  it('explains a denied location in plain words and keeps the list', async () => {
    position.mockRejectedValue(new Error('denied'));
    renderFind('ms');
    fireEvent.click(await screen.findByRole('button', { name: 'Guna lokasi saya' }));
    expect(await screen.findByText('Kami tidak dapat lokasi anda. Anda boleh pilih jalan dari senarai.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Pilih dari senarai' })).toBeInTheDocument();
  });
});
