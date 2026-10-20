import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { streetDetail, streets } from '@floodready/shared/mocks';
import { StreetHome } from './StreetHome';

const nameOf = (id: string) => streets.features.find((f) => f.properties.street_id === id)?.properties.name ?? id;

function stubApi() {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.includes('open-meteo')) return new Response('{}', { status: 404 });
    if (url.includes('/stations')) return new Response('[]', { status: 200 });
    if (url.includes('/streets?')) return new Response(JSON.stringify(streets), { status: 200 });
    const id = decodeURIComponent(url.split('/streets/')[1] ?? '');
    const level = streets.features.find((f) => f.properties.street_id === id)?.properties.level ?? 'normal';
    return new Response(JSON.stringify({ ...streetDetail, street_id: id, name: nameOf(id), level, active_alert: null }), { status: 200 });
  }));
}

function renderHome(at: string, saved: string[], onSave = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const el = <StreetHome lang="en" deviceId="dev_1" saved={saved} onSave={onSave} />;
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[at]}>
        <Routes>
          <Route path="/" element={el} />
          <Route path="/street/:id" element={el} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return onSave;
}

/** The street view chains several requests; allow for a busy test run. */
const slow = { timeout: 3000 };

beforeEach(stubApi);
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('StreetHome (one street)', () => {
  it('shows the start screen when no street is saved', async () => {
    renderHome('/', []);
    expect(await screen.findByRole('heading', { name: 'See flood warnings for your street' })).toBeInTheDocument();
  });

  it('opens straight on my street, with no swiping and no page dots', async () => {
    renderHome('/', ['BBR-persiaran-batu-belah']);
    expect(await screen.findByRole('heading', { level: 1, name: 'Persiaran Batu Belah' }, slow)).toBeInTheDocument();
    expect(document.querySelector('.pager-track')).toBeNull();
    expect(screen.queryByRole('group', { name: 'Your streets' })).toBeNull();
    expect(screen.queryByRole('button', { name: /^Street \d/ })).toBeNull();
  });

  it('shows only the first street when an older phone still has several saved', async () => {
    renderHome('/', ['BBR-jalan-mock-normal', 'BBR-jalan-makyong']);
    expect(await screen.findByRole('heading', { level: 1, name: 'Jalan Mock (normal)' }, slow)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { level: 1, name: 'Jalan Makyong' })).toBeNull();
  });

  it('keeps the red map button to the flood map', async () => {
    renderHome('/', ['BBR-persiaran-batu-belah']);
    await screen.findByRole('heading', { level: 1, name: 'Persiaran Batu Belah' }, slow);
    expect(screen.getByRole('link', { name: 'Flood map and location' })).toHaveAttribute('href', '/map');
    expect(document.querySelector('.bottom-bar')).toBeNull();
  });

  it('opens my street from /street/:id (a push notification click)', async () => {
    renderHome('/street/BBR-persiaran-batu-belah', ['BBR-persiaran-batu-belah']);
    const page = await screen.findByRole('heading', { level: 1, name: 'Persiaran Batu Belah' }, slow);
    expect(within(page.closest('.street') as HTMLElement).queryByRole('button', { name: 'Set as my street' })).toBeNull();
  });

  it('opens another street on its own, with "Set as my street" that replaces my street', async () => {
    const onSave = renderHome('/street/BBR-jalan-makyong', ['BBR-persiaran-batu-belah']);
    expect(await screen.findByRole('heading', { level: 1, name: 'Jalan Makyong' }, slow)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Set as my street' }));
    expect(onSave).toHaveBeenCalledWith(['BBR-jalan-makyong']);
  });

  it('has no Back link on the street page; the red map button navigates', async () => {
    renderHome('/', ['BBR-jalan-makyong']);
    const page = await screen.findByRole('heading', { level: 1, name: 'Jalan Makyong' }, slow);
    expect(within(page.closest('.street') as HTMLElement).queryByRole('link', { name: /Back/ })).toBeNull();
  });
});
