import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { streetDetail, streets } from '@floodready/shared/mocks';
import { SwipeShell } from './SwipeHome';

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

let path = '';
function Where() {
  path = useLocation().pathname;
  return null;
}

function renderShell(at: string, saved: string[], onSave = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[at]}>
        <Routes>
          <Route element={<SwipeShell lang="en" deviceId="dev_1" saved={saved} onSave={onSave} />}>
            <Route index element={null} />
            <Route path="street/:id" element={null} />
          </Route>
        </Routes>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return onSave;
}

beforeEach(() => {
  stubApi();
  sessionStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

/** The pager chains several requests (streets, then each street); allow for a busy test run. */
const slow = { timeout: 3000 };

const dotNames = () => screen.getAllByRole('button', { name: /^Street \d/ }).map((b) => b.getAttribute('aria-label'));

describe('SwipeShell', () => {
  it('shows the start screen when no street is saved', async () => {
    renderShell('/', []);
    expect(await screen.findByRole('heading', { name: 'See flood warnings for your street' }, slow)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Use my location' })).toBeInTheDocument();
  });

  it('orders pages Danger, Warning, Watch, Normal, keeping the saved order within a level', async () => {
    renderShell('/', ['BBR-jalan-mock-normal', 'BBR-persiaran-batu-belah', 'BBR-jalan-makyong', 'BBR-persiaran-sungai-keramat']);
    await screen.findAllByRole('button', { name: /^Street 1 of 4/ }, slow);
    expect(dotNames()).toEqual([
      'Street 1 of 4: Jalan Makyong, Warning',
      'Street 2 of 4: Persiaran Sungai Keramat, Warning',
      'Street 3 of 4: Persiaran Batu Belah, Watch',
      'Street 4 of 4: Jalan Mock (normal), Normal',
    ]);
  });

  it('opens on the first page when a street is alerting, and puts it in the URL', async () => {
    renderShell('/', ['BBR-jalan-mock-normal', 'BBR-jalan-makyong']);
    const first = await screen.findByRole('button', { name: /^Street 1 of 2/ }, slow);
    expect(first).toHaveAttribute('aria-current', 'true');
    expect(await screen.findByRole('heading', { level: 1, name: 'Jalan Makyong' }, slow)).toBeInTheDocument();
    // The pager puts the street in the URL in its own effect, so wait for it rather than read it at once.
    await waitFor(() => expect(path).toBe('/street/BBR-jalan-makyong'), slow);
  });

  it('mounts only the active page and its neighbours', async () => {
    renderShell('/', ['BBR-jalan-makyong', 'BBR-persiaran-sungai-keramat', 'BBR-persiaran-batu-belah', 'BBR-jalan-mock-normal']);
    await screen.findByRole('heading', { level: 1, name: 'Jalan Makyong' }, slow);
    const panels = document.querySelectorAll('.pager-panel');
    expect(panels).toHaveLength(4);
    expect(panels[0].querySelector('.street')).not.toBeNull();
    await waitFor(() => expect(panels[1].querySelector('.street')).not.toBeNull());
    expect(panels[2].children).toHaveLength(0);
    expect(panels[3].children).toHaveLength(0);
  });

  it('opens a saved street from /street/:id (a push notification click) on that page', async () => {
    renderShell('/street/BBR-persiaran-batu-belah', ['BBR-jalan-makyong', 'BBR-persiaran-batu-belah']);
    const dot = await screen.findByRole('button', { name: /Persiaran Batu Belah/ }, slow);
    expect(dot).toHaveAttribute('aria-current', 'true');
    await waitFor(() => expect(path).toBe('/street/BBR-persiaran-batu-belah'), slow);
  });

  it('opens a street that is not saved on its own, with an Add button and no dots', async () => {
    const onSave = renderShell('/street/BBR-persiaran-batu-belah', ['BBR-jalan-makyong']);
    const add = await screen.findByRole('button', { name: '+ Add to my streets' }, slow);
    expect(screen.queryByRole('button', { name: /^Street \d/ })).toBeNull();
    expect(screen.getByRole('link', { name: 'Flood map' })).toBeInTheDocument();
    fireEvent.click(add);
    expect(onSave).toHaveBeenCalledWith(['BBR-jalan-makyong', 'BBR-persiaran-batu-belah']);
  });

  it('has no Back link on the full-screen pages; the bottom bar navigates', async () => {
    renderShell('/', ['BBR-jalan-makyong']);
    const page = await screen.findByRole('heading', { level: 1, name: 'Jalan Makyong' }, slow);
    expect(within(page.closest('.street') as HTMLElement).queryByRole('link', { name: /Back/ })).toBeNull();
    expect(screen.getByRole('link', { name: 'My streets' })).toHaveAttribute('href', '/streets');
  });
});
