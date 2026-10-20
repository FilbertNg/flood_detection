import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { status, streets } from '@floodready/shared/mocks';
import { HomePage } from './Home';

// The real map is Leaflet; the stand-in offers one button per street, calling onFocus as zooming in on it
// would, and one that zooms back out. The real map shows `children` in a popup on the focused street.
vi.mock('../components/StreetMap', () => ({
  StreetMap: ({ data, onFocus, children }: { data: typeof streets; onFocus: (id: string | null) => void; children?: ReactNode }) => (
    <div data-testid="map">
      {children}
      {data.features.map((f) => (
        <button key={f.properties.street_id} type="button" onClick={() => onFocus(f.properties.street_id)}>zoom to {f.properties.name}</button>
      ))}
      <button type="button" onClick={() => onFocus(null)}>zoom out</button>
    </div>
  ),
}));

let path = '';
function Where() {
  path = useLocation().pathname;
  return null;
}

function renderHome(lang: 'en' | 'ms', mine: string[]) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('/status') ? status : streets), { status: 200 })));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/map']}>
        <Routes>
          <Route path="/map" element={<HomePage lang={lang} mine={mine} />} />
          <Route path="*" element={null} />
        </Routes>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('HomePage watch and credits', () => {
  it('counts Warning/Danger and Watch in two boxes, red and yellow (English)', async () => {
    renderHome('en', []);
    await screen.findByText(/streets at Warning or Danger/);
    const risk = document.querySelector('.summary-box[data-kind="risk"]')!;
    const watch = document.querySelector('.summary-box[data-kind="watch"]')!;
    expect(risk.textContent).toBe('2streets at Warning or Danger');
    expect(watch.textContent).toBe('1streets at Watch');
  });

  it('counts Warning/Danger and Watch in two boxes (Malay)', async () => {
    renderHome('ms', []);
    await screen.findByText(/jalan pada tahap Amaran atau Bahaya/);
    expect(document.querySelector('.summary-box[data-kind="risk"]')!.textContent).toBe('2jalan pada tahap Amaran atau Bahaya');
    expect(document.querySelector('.summary-box[data-kind="watch"]')!.textContent).toBe('1jalan pada tahap Waspada');
  });

  it('shows a distinct watch banner for my street at Watch', async () => {
    renderHome('en', ['BBR-persiaran-batu-belah']);
    await screen.findByTestId('map');
    expect(document.querySelector('.alert-banner.watch')!.textContent).toContain('Watch on your street: Persiaran Batu Belah');
    expect(document.querySelector('.alert-banner:not(.watch)')).toBeNull();
  });

  it('prefers the Warning banner over Watch when both are followed', async () => {
    renderHome('en', ['BBR-persiaran-batu-belah', 'BBR-jalan-makyong']);
    await screen.findByTestId('map');
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

describe('HomePage count panels', () => {
  it('opens the Warning or Danger streets in a sheet over a darkened page, as links', async () => {
    renderHome('en', []);
    const risk = await screen.findByRole('button', { name: /streets at Warning or Danger/ });
    fireEvent.click(risk);
    const sheet = screen.getByRole('dialog', { name: 'Streets at Warning or Danger' });
    expect(sheet.closest('.sheet-backdrop')).not.toBeNull();
    const links = within(sheet).getAllByRole('link');
    expect(links).toHaveLength(2);
    expect(within(sheet).getByRole('link', { name: /Jalan Makyong/ })).toHaveAttribute('href', '/street/BBR-jalan-makyong');
    fireEvent.click(within(sheet).getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('opens the Watch streets the same way and closes on the dark backdrop or Escape', async () => {
    renderHome('en', []);
    fireEvent.click(await screen.findByRole('button', { name: /streets at Watch/ }));
    const sheet = screen.getByRole('dialog', { name: 'Streets at Watch' });
    expect(within(sheet).getByRole('link', { name: /Persiaran Batu Belah/ })).toBeInTheDocument();
    fireEvent.click(sheet.closest('.sheet-backdrop')!);
    expect(screen.queryByRole('dialog')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /streets at Watch/ }));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
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
    await screen.findByTestId('map');
    expect(screen.queryByRole('link', { name: 'Report a flood' })).not.toBeInTheDocument();
  });
});

describe('HomePage at /map', () => {
  it('has a red header with Back to the swipe home and the title', async () => {
    renderHome('en', []);
    await screen.findByText(/streets at Warning or Danger/);
    // A round back button: a red arrow on white, no "Back" text (the name is for screen readers).
    const back = screen.getByRole('link', { name: 'Back' });
    expect(back).toHaveAttribute('href', '/');
    expect(back).toHaveClass('back-btn');
    expect(back.textContent).toBe('');
    expect(back.querySelector('svg')).not.toBeNull();
    expect(screen.getByRole('heading', { level: 1, name: 'Flood map' })).toBeInTheDocument();
  });

  it('has no "My location" card over the map', async () => {
    renderHome('en', ['BBR-persiaran-batu-belah']);
    await screen.findByTestId('map');
    expect(screen.queryByRole('region', { name: 'My location' })).toBeNull();
  });

  it('asks to zoom in until a street is under the centre of the map', async () => {
    renderHome('en', []);
    expect(await screen.findByText('Zoom in on a street to see it')).toBeInTheDocument();
  });

  it('shows the street under the map centre once zoomed in, with its level and a View button', async () => {
    renderHome('en', []);
    fireEvent.click(await screen.findByRole('button', { name: 'zoom to Jalan Makyong' }));
    const panel = screen.getByRole('region', { name: 'Jalan Makyong' });
    expect(within(panel).getByText('Warning')).toBeInTheDocument();
    fireEvent.click(within(panel).getByRole('link', { name: 'View' }));
    expect(path).toBe('/street/BBR-jalan-makyong');
  });

  it('hides the street panel again when zoomed out', async () => {
    renderHome('en', []);
    fireEvent.click(await screen.findByRole('button', { name: 'zoom to Jalan Makyong' }));
    fireEvent.click(screen.getByRole('button', { name: 'zoom out' }));
    expect(screen.queryByRole('region', { name: 'Jalan Makyong' })).toBeNull();
    expect(screen.getByText('Zoom in on a street to see it')).toBeInTheDocument();
  });

  it('has no "My street" list (my street is on the home page)', async () => {
    renderHome('en', ['BBR-persiaran-batu-belah']);
    await screen.findByTestId('map');
    expect(screen.queryByRole('heading', { name: 'My street' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Change' })).toBeNull();
    expect(document.querySelector('.my-streets')).toBeNull();
  });

  it('floats the live / replay chip on the map', async () => {
    renderHome('en', []);
    const chip = (await screen.findByText('Replay', { selector: '.replay-tag' })).closest('.status-chip')!;
    expect(chip.closest('.map-wrap')).not.toBeNull();
  });

  it('has a full-screen button on the map that expands it and closes again (button or Escape)', async () => {
    renderHome('en', []);
    await screen.findByTestId('map');
    const wrap = document.querySelector('.map-wrap')!;
    expect(wrap.contains(screen.getByRole('button', { name: 'Full screen map' }))).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Full screen map' }));
    expect(wrap).toHaveClass('is-full');
    fireEvent.click(screen.getByRole('button', { name: 'Exit full screen' }));
    expect(wrap).not.toHaveClass('is-full');
    fireEvent.click(screen.getByRole('button', { name: 'Full screen map' }));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(wrap).not.toHaveClass('is-full');
  });
});
