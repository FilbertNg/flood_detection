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
          <Route path="/street/:id" element={<StreetPage lang={lang} deviceId="dev_1" />} />
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
    expect(screen.getAllByText('Amaran').length).toBeGreaterThan(0);
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

  it('asks "Is it flooding here?" during an active Warning alert', async () => {
    renderStreet('en');
    expect(await screen.findByRole('heading', { name: 'Is it flooding here?' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Report a flood' })).not.toBeInTheDocument();
  });

  it('offers the Report a flood link instead when no alert is active', async () => {
    renderStreet('en', { ...streetDetail, level: 'normal', active_alert: null });
    const link = await screen.findByRole('link', { name: 'Report a flood' });
    expect(link).toHaveAttribute('href', '/report?street=BBR-jalan-makyong');
    expect(screen.queryByRole('heading', { name: 'Is it flooding here?' })).not.toBeInTheDocument();
  });

  it('does not ask for verification during a Watch alert', async () => {
    renderStreet('en', { ...streetDetail, level: 'watch', active_alert: { alert_id: 'a_09', level: 'watch', issued_at: '2024-11-12T09:00:00+08:00' } });
    await screen.findByRole('link', { name: 'Report a flood' });
    expect(screen.queryByRole('heading', { name: 'Is it flooding here?' })).not.toBeInTheDocument();
  });

  it('shows the Open-Meteo weather for the data hour and credits it', async () => {
    const weather = { hourly: { time: ['2024-11-12T09:00'], weather_code: [3], is_day: [1], precipitation_probability: [70] } };
    vi.stubGlobal('fetch', vi.fn(async (url: string) =>
      new Response(JSON.stringify(url.includes('open-meteo') ? weather : url.includes('/stations') ? [] : { ...streetDetail, level: 'normal', active_alert: null }), { status: 200 })));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/street/BBR-jalan-makyong']}>
          <Routes><Route path="/street/:id" element={<StreetPage lang="en" deviceId="dev_1" />} /></Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText('Cloudy · 70% chance of rain')).toBeInTheDocument();
    expect(screen.getByText('Weather: Open-Meteo')).toBeInTheDocument();
  });

  it('labels replayed data inside the full-screen page and offers the language switch', async () => {
    const onLang = vi.fn();
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ ...streetDetail, is_replay: true }), { status: 200 })));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/street/BBR-jalan-makyong']}>
          <Routes><Route path="/street/:id" element={<StreetPage lang="en" deviceId="dev_1" onLang={onLang} />} /></Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText('Replay of a past flood')).toBeInTheDocument();
    screen.getByRole('button', { name: 'Bahasa Melayu' }).click();
    expect(onLang).toHaveBeenCalledWith('ms');
  });

  it('shows no replay label for live data', async () => {
    renderStreet('en', { ...streetDetail, is_replay: false });
    expect(await screen.findByText('Jalan Makyong')).toBeInTheDocument();
    expect(screen.queryByText('Replay of a past flood')).not.toBeInTheDocument();
  });

  it('lists the alert history with outcome and keeps the footer', async () => {
    renderStreet('ms');
    expect(await screen.findByRole('heading', { name: 'Amaran lepas di jalan ini' })).toBeInTheDocument();
    expect(screen.getByText('Belum disahkan')).toBeInTheDocument();
    expect(screen.getByText('Main semula')).toBeInTheDocument();
    expect(screen.getByText(/JPS, MET dan NADMA ialah sumber rasmi/)).toBeInTheDocument();
  });
});
