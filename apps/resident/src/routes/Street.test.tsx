import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { stations, streetDetail } from '@floodready/shared/mocks';
import { StreetPage } from './Street';

function renderStreet(lang: 'en' | 'ms', detail: unknown = streetDetail, withStations = false) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) =>
    new Response(JSON.stringify(withStations && url.includes('/stations') ? stations : detail), { status: 200 })));
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
    expect(screen.getByRole('heading', { name: 'Updated' }).closest('.ptile')).toHaveTextContent('JPS Infobanjir, Open-Meteo');
  });

  it('labels replayed data inside the hero card', async () => {
    renderStreet('en', { ...streetDetail, is_replay: true });
    expect(await screen.findByText('Replay of a past flood')).toBeInTheDocument();
    expect(screen.getByText('Replay of a past flood').closest('.hero')).not.toBeNull();
  });

  it('describes a flood-prone street in plain words', async () => {
    renderStreet('en', { ...streetDetail, susceptibility: 5 });
    const street = (await screen.findByRole('heading', { name: 'This street' })).closest('.ptile') as HTMLElement;
    expect(street).toHaveTextContent('Low-lying');
    expect(street).toHaveTextContent('of 5');
  });

  it('shows no replay label for live data', async () => {
    renderStreet('en', { ...streetDetail, is_replay: false });
    expect(await screen.findByText('Jalan Makyong')).toBeInTheDocument();
    expect(screen.queryByText('Replay of a past flood')).not.toBeInTheDocument();
  });

  it('puts the plain answer first: big word, headline, then what to do, with no separate Rain / River / Flood list', async () => {
    renderStreet('en');
    expect(await screen.findByText('Get ready')).toBeInTheDocument();
    expect(screen.getByText('Flooding is expected on this street from about 09:30.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'What to do now' })).toBeInTheDocument();
    expect(document.querySelector('.keys')).toBeNull();
  });

  it('draws "Right now" as picture tiles: rain now, next 12 hours, river, this street, then the tide full width', async () => {
    renderStreet('en');
    await screen.findByText('Get ready');
    const grid = screen.getByRole('heading', { name: 'Right now' }).closest('.ptiles') as HTMLElement;
    const titles = [...grid.querySelectorAll('.ptile-head')].map((h) => h.textContent);
    expect(titles).toEqual(['Rain now', 'Next 12 hours', 'River level', 'This street', 'Tide · Port Klang']);
    expect(grid.querySelectorAll('.ptile')[4]).toHaveAttribute('data-wide', 'true');
    for (const pic of grid.querySelectorAll('svg.pic')) expect(pic).toHaveAttribute('aria-hidden', 'true');
  });

  it('keeps technical words and numbers inside the Technical details card, shown open with no toggle', async () => {
    renderStreet('en');
    await screen.findByText('Jalan Makyong');
    const details = screen.getByRole('heading', { name: 'Technical details' }).closest('section.tech-tiles') as HTMLElement;
    expect(details).not.toBeNull();
    expect(document.querySelector('details.tech')).toBeNull();
    expect(details).toBeVisible();
    expect(details).toHaveTextContent('62%');
    expect(details).toHaveTextContent('61.5 mm of rain in 1 h at Kg. Perepat, Kapar');
    // Everything above the Technical details card reads without jargon.
    const above: string[] = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (details.compareDocumentPosition(n) & Node.DOCUMENT_POSITION_PRECEDING) above.push(n.textContent ?? '');
    }
    const text = above.join(' ');
    // River heights are shown above it on purpose (the River level tile); source and model names are not.
    expect(text).not.toMatch(/JPS|ML|model|Open-Meteo/);
  });

  it('ends with the "Is it flooding here?" question, after the alert history', async () => {
    renderStreet('en');
    const ask = await screen.findByRole('heading', { name: 'Is it flooding here?' });
    const sections = [...document.querySelectorAll('.street > section, .street > a, .street > details')];
    expect(sections[sections.length - 1]).toContainElement(ask);
    const history = screen.getByRole('heading', { name: 'Past alerts on this street' });
    expect(history.compareDocumentPosition(ask) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('ends with the report card when no alert is active', async () => {
    renderStreet('en', { ...streetDetail, level: 'normal', active_alert: null });
    const link = await screen.findByRole('link', { name: 'Report a flood' });
    const sections = [...document.querySelectorAll('.street > section, .street > a, .street > details')];
    expect(sections[sections.length - 1]).toBe(link);
  });

  it('lists the alert history with outcome and keeps the footer', async () => {
    renderStreet('ms');
    expect(await screen.findByRole('heading', { name: 'Amaran lepas di jalan ini' })).toBeInTheDocument();
    expect(screen.getByText('Belum disahkan')).toBeInTheDocument();
    expect(screen.getByText('Main semula')).toBeInTheDocument();
    expect(screen.getByText(/JPS, MET dan NADMA ialah sumber rasmi/)).toBeInTheDocument();
  });

  it('shows "What to do now" from Watch up, and leaves it out when the street is Safe', async () => {
    renderStreet('en', { ...streetDetail, level: 'normal', window: null, active_alert: null });
    await screen.findByText('Safe');
    expect(screen.queryByRole('heading', { name: 'What to do now' })).not.toBeInTheDocument();
    cleanup();
    renderStreet('en', { ...streetDetail, level: 'watch', window: null, active_alert: null });
    expect(await screen.findByRole('heading', { name: 'What to do now' })).toBeInTheDocument();
  });

  it('gives the river its own panel: height, distance to the next mark, status and the forecast highlight', async () => {
    renderStreet('en', streetDetail, true);
    // The station reading arrives after the street.
    const panel = (await screen.findByText('Measured at Sg. Binjai di Pekan Meru')).closest('.ptile') as HTMLElement;
    expect(panel).toHaveTextContent('3.52m');
    expect(panel).toHaveTextContent('0.28 m below the alert line');
    expect(panel).toHaveTextContent('Close to alert');
    expect(panel).toHaveTextContent('Estimate: may reach the warning line by 10:00');
    expect(panel.querySelectorAll('[data-tick]')).toHaveLength(3);
  });

  it('says there is no reading in the river panel when no river station reports', async () => {
    renderStreet('en');
    const panel = (await screen.findByRole('heading', { name: 'River level' })).closest('.ptile') as HTMLElement;
    expect(panel).toHaveTextContent('No reading right now');
  });

  it('shows rain, street and tide tiles outside Technical details', async () => {
    renderStreet('en', streetDetail, true);
    await screen.findByText('Measured at Sg. Binjai di Pekan Meru');
    const tile = (name: string) => screen.getByRole('heading', { name }).closest('.ptile') as HTMLElement;
    const tech = screen.getByRole('heading', { name: 'Technical details' });
    expect(tile('Rain now')).toHaveTextContent('61.5mm');
    expect(tile('Next 12 hours')).toHaveTextContent('2.5mm');
    expect(tile('This street')).toHaveTextContent('of 5');
    expect(tile('Tide · Port Klang')).toHaveTextContent('11:00');
    expect(tile('Tide · Port Klang')).toHaveTextContent('2.2 m');
    for (const name of ['Rain now', 'Next 12 hours', 'This street', 'Tide · Port Klang']) {
      expect(tile(name).compareDocumentPosition(tech) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
  });

  it('puts the flood model, the update time and the reasons in Technical details, and hides the model tile without a value', async () => {
    renderStreet('en');
    const grid = (await screen.findByRole('heading', { name: 'Technical details' })).closest('.ptiles') as HTMLElement;
    expect(grid).toHaveTextContent('Flood model');
    expect(grid).toHaveTextContent('Updated');
    expect(grid).toHaveTextContent('Why this level');
    cleanup();
    renderStreet('en', { ...streetDetail, flood_probability: null });
    await screen.findByRole('heading', { name: 'Technical details' });
    expect(screen.queryByRole('heading', { name: 'Flood model' })).toBeNull();
  });
});
