import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { status, streets } from '@floodready/shared/mocks';
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

const live = { ...status, mode: 'live' };

function stubApi(state: unknown = live) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('/status') ? state : streets), { status: 200 })));
}

beforeEach(() => stubApi());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  position.mockReset();
});

describe('FindStreetPage', () => {
  it('is one screen: the title, "Find my street" and "Choose from the list", with no language switch', async () => {
    renderFind();
    expect(await screen.findByRole('heading', { level: 1, name: 'Know before the water reaches your street' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Find my street' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Choose from the list' })).toHaveAttribute('href', '/streets');
    expect(screen.queryByRole('group', { name: /language/i })).toBeNull();
    expect(document.querySelector('.lang-switch')).toBeNull();
    // The privacy promise belongs to the locating step, not the start screen.
    expect(screen.queryByText('Your location stays on this phone.')).toBeNull();
  });

  it('asks for the location only after the button is tapped, and promises it stays on the phone while it asks', async () => {
    let resolve: (p: { lat: number; lon: number }) => void = () => {};
    position.mockReturnValue(new Promise((r) => { resolve = r; }));
    renderFind();
    await screen.findByRole('button', { name: 'Find my street' });
    expect(position).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Find my street' }));
    expect(await screen.findByText('Finding your street…')).toBeInTheDocument();
    expect(screen.getByText('Your location stays on this phone.')).toBeInTheDocument();
    resolve({ lat: 3.0899, lon: 101.4251 });
    expect(await screen.findByText('Is this your street?')).toBeInTheDocument();
  });

  it('hides the illustration from screen readers and labels the logo Flood-Ready', async () => {
    renderFind();
    await screen.findByRole('button', { name: 'Find my street' });
    const art = document.querySelector('.onb-art > svg')!;
    expect(art).toHaveAttribute('aria-hidden', 'true');
    expect(screen.getByRole('img', { name: 'Flood-Ready' })).toBeInTheDocument();
  });

  it('says who it is built for, with the Sime Darby Property logo (Malay too)', async () => {
    renderFind();
    const badge = (await screen.findByText('Built for')).closest('.onb-builtfor') as HTMLElement;
    expect(badge.querySelector('img')).toHaveAttribute('alt', 'Sime Darby Property');
    expect(badge.querySelector('img')).toHaveAttribute('src', '/sdp-logo.png');
    cleanup();
    renderFind('ms');
    expect(await screen.findByText('Dibina untuk')).toBeInTheDocument();
  });

  it('shows the replay label as a chip in replay mode, and never "Live"', async () => {
    stubApi({ ...status, mode: 'replay', replay: { event: '2024-11-12', speed: 60 } });
    renderFind();
    expect(await screen.findByText('Replay of a past flood')).toBeInTheDocument();
    expect(screen.queryByText(/Live/)).toBeNull();
  });

  it('shows no replay chip on live data (Malay title)', async () => {
    renderFind('ms');
    expect(await screen.findByRole('heading', { level: 1, name: 'Tahu lebih awal sebelum air sampai ke jalan anda' })).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 30));
    expect(screen.queryByText('Main semula banjir lalu')).toBeNull();
  });

  it('finds the nearest street on the phone and saves it on Yes', async () => {
    position.mockResolvedValue({ lat: 3.0899, lon: 101.4251 });
    const onSave = renderFind();
    fireEvent.click(await screen.findByRole('button', { name: 'Find my street' }));
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
    fireEvent.click(await screen.findByRole('button', { name: 'Find my street' }));
    expect(await screen.findByRole('link', { name: 'Choose another' })).toHaveAttribute('href', '/streets');
  });

  it('says so when the phone is outside Bandar Bukit Raja', async () => {
    position.mockResolvedValue({ lat: 3.139, lon: 101.687 });
    renderFind();
    fireEvent.click(await screen.findByRole('button', { name: 'Find my street' }));
    expect(await screen.findByText('You seem to be outside Bandar Bukit Raja.')).toBeInTheDocument();
    expect(screen.queryByText('Is this your street?')).toBeNull();
  });

  it('explains a denied location in plain words and keeps the list', async () => {
    position.mockRejectedValue(new Error('denied'));
    renderFind('ms');
    fireEvent.click(await screen.findByRole('button', { name: 'Cari jalan saya' }));
    expect(await screen.findByText('Kami tidak dapat lokasi anda. Anda boleh pilih jalan dari senarai.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Pilih dari senarai' })).toBeInTheDocument();
  });
});
