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
    for (const name of ['Rain', 'River level', 'This street', 'Tide']) {
      expect(within(view).getByRole('heading', { name })).toBeInTheDocument();
    }
    expect(within(view).getByText('High tide 11:00 · 2.2 m')).toBeInTheDocument();
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

describe('StreetView sky view keeps its panels', () => {
  it('renders the current panels and technical details in the sky view, not the picture tiles', async () => {
    renderView();
    fireEvent.click(await opener());
    const view = dialog()!;
    expect(view.querySelectorAll('.panel').length).toBeGreaterThanOrEqual(4);
    expect(view.querySelector('.ptile')).toBeNull();
    expect(view.querySelector('.tide-chart')).not.toBeNull();
    const rain = within(view).getByText('Rain last hour').closest('.reading') as HTMLElement;
    expect(rain).toHaveTextContent('0 mm');
    expect(rain).toHaveTextContent('Nearest JPS rain gauge');
    const model = within(view).getByText('Flood model').closest('.reading') as HTMLElement;
    expect(model.parentElement).toBe(rain.parentElement);
    const meter = within(model).getByRole('meter');
    expect(meter).toHaveAttribute('aria-valuenow', '62');
    expect(meter).toHaveAttribute('aria-valuemax', '100');
    expect(view.querySelector('.why[data-tone="alert"]')).not.toBeNull();
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
