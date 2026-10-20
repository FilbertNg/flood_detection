import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { streets } from '@floodready/shared/mocks';
import { HomePage } from './Home';

vi.mock('../components/StreetMap', () => ({ StreetMap: () => <div data-testid="map" /> }));

function renderHome(lang: 'en' | 'ms', mine: string[]) {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(streets), { status: 200 })));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter><HomePage lang={lang} mine={mine} /></MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('HomePage watch and credits', () => {
  it('counts Warning/Danger separately from Watch (English)', async () => {
    renderHome('en', []);
    await screen.findByText(/streets at Warning or Danger/);
    expect(document.querySelector('.summary')!.textContent).toBe('2 streets at Warning or Danger · 1 at Watch');
  });

  it('counts Warning/Danger separately from Watch (Malay)', async () => {
    renderHome('ms', []);
    await screen.findByText(/jalan pada tahap Amaran atau Bahaya/);
    expect(document.querySelector('.summary')!.textContent).toBe('2 jalan pada tahap Amaran atau Bahaya · 1 pada tahap Waspada');
  });

  it('shows a followed Watch street with a Watch badge and a distinct watch banner', async () => {
    renderHome('en', ['BBR-persiaran-batu-belah']);
    expect(await screen.findByText('Persiaran Batu Belah', { selector: 'span' })).toBeInTheDocument();
    expect(screen.getByText('Watch', { selector: '.badge' })).toBeInTheDocument();
    expect(document.querySelector('.alert-banner.watch')!.textContent).toContain('Watch on your street: Persiaran Batu Belah');
    expect(document.querySelector('.alert-banner:not(.watch)')).toBeNull();
  });

  it('prefers the Warning banner over Watch when both are followed', async () => {
    renderHome('en', ['BBR-persiaran-batu-belah', 'BBR-jalan-makyong']);
    await screen.findByText('Jalan Makyong', { selector: 'span' });
    expect(document.querySelector('.alert-banner:not(.watch)')!.textContent).toContain('Jalan Makyong');
    expect(document.querySelector('.alert-banner.watch')).toBeNull();
  });

  it('shows a short credits line and the full licence text under Sources', async () => {
    renderHome('en', []);
    expect(await screen.findByText('© OpenStreetMap contributors · JPS Public Infobanjir · MET Malaysia · Open-Meteo · FABDEM (Univ. of Bristol, CC BY-NC-SA) · ESA WorldCover')).toBeInTheDocument();
    const details = document.querySelector('details.credits-full')!;
    expect(details.querySelector('summary')!.textContent).toBe('Sources');
    expect(details.textContent).toContain('Copernicus GLO-30');
    expect(details.textContent).toContain('CC BY-NC-SA 4.0');
    expect(details.textContent).toContain('© ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium (CC BY 4.0)');
  });

  it('labels the sources in Malay', async () => {
    renderHome('ms', []);
    await screen.findByText(/© Penyumbang OpenStreetMap · JPS Public Infobanjir/);
    expect(document.querySelector('details.credits-full summary')!.textContent).toBe('Sumber');
  });
});

describe('HomePage report link', () => {
  it('links to Report a flood when none of my streets has an alert', async () => {
    renderHome('en', ['BBR-persiaran-batu-belah']);
    expect(await screen.findByRole('link', { name: 'Report a flood' })).toHaveAttribute('href', '/report');
  });
  it('hides it while a followed street is at Warning or Danger', async () => {
    const followed = streets.features.find((f) => f.properties.street_id === 'BBR-jalan-makyong');
    expect(['warning', 'danger']).toContain(followed?.properties.level);
    renderHome('en', ['BBR-jalan-makyong']);
    await screen.findByText('Jalan Makyong', { selector: 'span' });
    expect(screen.queryByRole('link', { name: 'Report a flood' })).not.toBeInTheDocument();
  });
});

describe('HomePage at /map', () => {
  it('links back to the swipe home', async () => {
    renderHome('en', []);
    await screen.findByText(/streets at Warning or Danger/);
    expect(screen.getByRole('link', { name: '← Back' })).toHaveAttribute('href', '/');
  });
});
