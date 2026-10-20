import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { status, streets } from '@floodready/shared/mocks';
import * as geo from '../lib/geo';
import { HomePage } from './Home';

// The real map is Leaflet; the stand-in offers one button per street line, calling onSelect like a tap.
vi.mock('../components/StreetMap', () => ({
  StreetMap: ({ data, onSelect }: { data: typeof streets; onSelect: (id: string) => void }) => (
    <div data-testid="map">
      {data.features.map((f) => (
        <button key={f.properties.street_id} type="button" onClick={() => onSelect(f.properties.street_id)}>line {f.properties.name}</button>
      ))}
    </div>
  ),
}));
vi.mock('../lib/geo', async (importOriginal) => ({ ...(await importOriginal<typeof geo>()), currentPosition: vi.fn() }));

let path = '';
function Where() {
  path = useLocation().pathname;
  return null;
}

function renderHome(lang: 'en' | 'ms', mine: string[], onSave = vi.fn()) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('/status') ? status : streets), { status: 200 })));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/map']}>
        <Routes>
          <Route path="/map" element={<HomePage lang={lang} mine={mine} deviceId="dev_1" onSave={onSave} />} />
          <Route path="*" element={null} />
        </Routes>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return onSave;
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
  it('has a red header with Back to the swipe home and the title', async () => {
    renderHome('en', []);
    await screen.findByText(/streets at Warning or Danger/);
    expect(screen.getByRole('link', { name: '← Back' })).toHaveAttribute('href', '/');
    expect(screen.getByRole('heading', { level: 1, name: 'Flood map' })).toBeInTheDocument();
  });

  it('shows my current street and level in the location card, with both buttons', async () => {
    renderHome('en', ['BBR-persiaran-batu-belah', 'BBR-jalan-makyong']);
    const card = await screen.findByRole('region', { name: 'My location' });
    expect(within(card).getByText('Persiaran Batu Belah')).toBeInTheDocument();
    expect(within(card).getByText('Watch')).toBeInTheDocument();
    expect(within(card).getByRole('button', { name: 'Use my location' })).toBeInTheDocument();
    expect(within(card).getByRole('button', { name: 'Choose another' })).toBeInTheDocument();
  });

  it('puts a tapped street line in the card; "Set as my street" replaces my street and opens it', async () => {
    const onSave = renderHome('en', ['BBR-persiaran-batu-belah']);
    fireEvent.click(await screen.findByRole('button', { name: 'line Jalan Makyong' }));
    const card = screen.getByRole('region', { name: 'My location' });
    expect(within(card).getByText('Jalan Makyong')).toBeInTheDocument();
    expect(within(card).getByText('Warning')).toBeInTheDocument();
    fireEvent.click(within(card).getByRole('button', { name: 'Set as my street' }));
    expect(onSave).toHaveBeenCalledWith(['BBR-jalan-makyong']);
    expect(path).toBe('/street/BBR-jalan-makyong');
  });

  it('offers "Set as my street" when no street is saved yet', async () => {
    const onSave = renderHome('en', []);
    fireEvent.click(await screen.findByRole('button', { name: 'line Jalan Makyong' }));
    fireEvent.click(screen.getByRole('button', { name: 'Set as my street' }));
    expect(onSave).toHaveBeenCalledWith(['BBR-jalan-makyong']);
    expect(path).toBe('/street/BBR-jalan-makyong');
  });

  it('fills the card from the phone location (nearest street found on the phone)', async () => {
    vi.mocked(geo.currentPosition).mockResolvedValue({ lat: 3.0899, lon: 101.4251 });
    renderHome('en', ['BBR-persiaran-batu-belah']);
    const card = await screen.findByRole('region', { name: 'My location' });
    fireEvent.click(within(card).getByRole('button', { name: 'Use my location' }));
    expect(await within(card).findByText('Jalan Makyong')).toBeInTheDocument();
    expect(within(card).getByRole('button', { name: 'Set as my street' })).toBeInTheDocument();
  });

  it('opens the street picker as a sheet over the map from "Choose another"', async () => {
    renderHome('en', ['BBR-persiaran-batu-belah']);
    fireEvent.click(await screen.findByRole('button', { name: 'Choose another' }));
    const sheet = screen.getByRole('dialog', { name: 'Choose your street' });
    expect(within(sheet).getByPlaceholderText('Search a street…')).toBeInTheDocument();
    fireEvent.click(within(sheet).getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog', { name: 'Choose your street' })).toBeNull();
  });
});
