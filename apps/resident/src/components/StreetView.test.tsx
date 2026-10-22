import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { streetDetail } from '@floodready/shared/mocks';
import { StreetView } from './StreetView';

let search = '';
function Spy() {
  search = useLocation().search;
  const navigate = useNavigate();
  return <button type="button" onClick={() => navigate(-1)}>browser back</button>;
}

function renderView(detail = { ...streetDetail, level: 'normal' as const, active_alert: null }) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('open-meteo') || url.includes('/stations') ? [] : detail), { status: 200 })));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/', '/street/BBR-jalan-makyong']} initialIndex={1}>
        <Routes>
          <Route path="/street/:id" element={<StreetView id="BBR-jalan-makyong" lang="en" deviceId="dev_1" showBack={false} />} />
          <Route path="/" element={<p>home</p>} />
        </Routes>
        <Spy />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const opener = () => screen.findByRole('button', { name: 'Open full weather and flood details' });
const dialog = () => screen.queryByRole('dialog', { name: 'Weather and flood details' });

beforeEach(() => {
  search = '';
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('StreetView full-screen sky', () => {
  it('opens from the hero card with a click, as a history entry', async () => {
    renderView();
    fireEvent.click(await opener());
    const view = dialog()!;
    expect(view).toBeInTheDocument();
    expect(view).toHaveAttribute('aria-modal', 'true');
    expect(search).toBe('?view=sky');
    expect(within(view).getByRole('heading', { name: 'Jalan Makyong' })).toBeInTheDocument();
    expect(within(view).getByText('Safe')).toBeInTheDocument();
    expect(within(view).getByRole('button', { name: 'Close' })).toHaveFocus();
  });

  it('shows everything from the street page inside: the panels, the tide and the technical details, open', async () => {
    renderView();
    fireEvent.click(await opener());
    const view = dialog()!;
    for (const name of ['Rain now', 'River level', 'This street', 'Tide · Port Klang']) {
      expect(within(view).getByRole('heading', { name })).toBeInTheDocument();
    }
    expect(within(view).getByRole('heading', { name: 'Tide · Port Klang' }).closest('.ptile')).toHaveTextContent('Next high water11:00');
    // Technical details are shown open, with the model chance and the reasons.
    expect(within(view).getByText('62%')).toBeVisible();
    expect(within(view).getByText('61.5 mm of rain in 1 h at Kg. Perepat, Kapar')).toBeInTheDocument();
    // Ids stay unique although the page and the full view show the same panels.
    const ids = [...document.querySelectorAll('[id]')].map((n) => n.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('opens with Enter or Space on the hero card', async () => {
    renderView();
    fireEvent.keyDown(await opener(), { key: 'Enter' });
    expect(dialog()).not.toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    await waitFor(() => expect(dialog()).toBeNull());
    fireEvent.keyDown(await opener(), { key: ' ' });
    expect(dialog()).not.toBeNull();
  });

  it('closes with × and returns focus to the hero card', async () => {
    renderView();
    const hero = await opener();
    fireEvent.click(hero);
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    await waitFor(() => expect(dialog()).toBeNull());
    expect(search).toBe('');
    expect(hero).toHaveFocus();
  });

  it('closes with Escape', async () => {
    renderView();
    const hero = await opener();
    fireEvent.click(hero);
    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(dialog()).toBeNull());
    expect(hero).toHaveFocus();
  });

  it('closes with the browser back button instead of leaving the street', async () => {
    renderView();
    fireEvent.click(await opener());
    fireEvent.click(screen.getByRole('button', { name: 'browser back' }));
    await waitFor(() => expect(dialog()).toBeNull());
    expect(screen.getByRole('heading', { level: 1, name: 'Jalan Makyong' })).toBeInTheDocument();
  });

  it('pauses the hero sky while the full view is open, so only one sky moves', async () => {
    renderView();
    fireEvent.click(await opener());
    const heroCanvas = document.querySelector('.hero canvas')!;
    const fullCanvas = dialog()!.querySelector('canvas')!;
    expect(heroCanvas).toHaveAttribute('data-still', 'true');
    expect(fullCanvas).toHaveAttribute('data-still', 'false');
    expect(Number(fullCanvas.getAttribute('data-drops'))).toBeGreaterThanOrEqual(Number(heroCanvas.getAttribute('data-drops')));
  });
});

describe('StreetView report', () => {
  it('shows Report a flood as a red card', async () => {
    renderView();
    expect(await screen.findByRole('link', { name: 'Report a flood' })).toHaveClass('report-card');
  });
});

describe('StreetView sky view follows the street page', () => {
  it('shows the same picture tiles in the sky view, under its own sky and rain curve', async () => {
    renderView();
    fireEvent.click(await opener());
    const view = dialog()!;
    expect(view.querySelector('.panel')).toBeNull();
    const grids = view.querySelectorAll('.ptiles');
    expect(grids).toHaveLength(2);
    const titles = [...grids[0].querySelectorAll('.ptile-head')].map((h) => h.textContent);
    expect(titles).toEqual(['Rain now', 'Next 12 hours', 'River level', 'This street', 'Tide · Port Klang']);
    expect(within(grids[1] as HTMLElement).getByRole('heading', { name: 'Flood model' })).toBeInTheDocument();
    // The sky's own curve stays above the tiles; the page's white curve card is not repeated.
    expect(view.querySelectorAll('.curve-scroll')).toHaveLength(1);
    expect(view.querySelector('.sky-view-chips')!.compareDocumentPosition(grids[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('draws the picture tiles on the page itself, below the hero card', async () => {
    renderView();
    await opener();
    const page = document.querySelector('.street') as HTMLElement;
    expect(page.querySelectorAll(':scope > .ptiles')).toHaveLength(2);
    const hero = page.querySelector('.hero')!;
    expect(hero.compareDocumentPosition(page.querySelector('.ptiles')!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

describe('StreetView loading skeleton', () => {
  it('holds the page with a "Loading your street" status, then the real page replaces it', async () => {
    let answer: () => void = () => {};
    const detail = { ...streetDetail, level: 'normal' as const, active_alert: null };
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url.includes('open-meteo') || url.includes('/stations')) return Promise.resolve(new Response('[]', { status: 200 }));
      return new Promise<Response>((resolve) => { answer = () => resolve(new Response(JSON.stringify(detail), { status: 200 })); });
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/street/BBR-jalan-makyong']}>
          <Routes><Route path="/street/:id" element={<StreetView id="BBR-jalan-makyong" lang="ms" deviceId="dev_1" showBack={false} />} /></Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const sk = screen.getByRole('status', { name: 'Memuatkan jalan anda' });
    expect(sk).toHaveTextContent('Memuatkan jalan anda…');
    expect(sk.querySelector('.sk-hero svg.logo-fill')).toHaveAttribute('width', '64');
    const tiles = sk.querySelectorAll('.ptiles .sk-tile');
    expect(tiles).toHaveLength(5);
    expect(tiles[4]).toHaveAttribute('data-wide', 'true');
    for (const tile of tiles) expect(tile.querySelectorAll('.bone').length).toBeGreaterThanOrEqual(2);
    answer();
    expect(await screen.findByRole('heading', { level: 1, name: 'Jalan Makyong' })).toBeInTheDocument();
    expect(screen.queryByRole('status', { name: 'Memuatkan jalan anda' })).toBeNull();
  });
});
