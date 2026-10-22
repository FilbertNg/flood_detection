import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { status, streets } from '@floodready/shared/mocks';
import { App } from './App';

const replay = { ...status, mode: 'replay', replay: { event: '2024-11-12', speed: 60 } };

function renderAt(path: string) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('/status') ? replay : streets), { status: 200 })));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe('App header', () => {
  it('shows no header on the first-visit onboarding screen', async () => {
    renderAt('/');
    expect(await screen.findByRole('button', { name: 'Find my street' })).toBeInTheDocument();
    expect(document.querySelector('header.top')).toBeNull();
    expect(screen.queryByRole('link', { name: /Flood-Ready/ })).toBeNull();
  });

  it('keeps the header on the other screens before a street is chosen', async () => {
    renderAt('/streets');
    expect(await screen.findByRole('link', { name: /Flood-Ready/ })).toBeInTheDocument();
  });

  it('shows the Flood-Ready logo next to the name', async () => {
    renderAt('/report');
    const brand = await screen.findByRole('link', { name: /Flood-Ready/ });
    expect(brand.querySelector('svg.logo')).not.toBeNull();
  });

  it('names the township under the logo until a street is chosen', async () => {
    renderAt('/report');
    const brand = await screen.findByRole('link', { name: /Flood-Ready/ });
    expect(brand.querySelector('small')).toHaveTextContent('Bandar Bukit Raja');
  });

  it('names my chosen street under the logo once one is saved', async () => {
    localStorage.setItem('floodready.prefs.v1', JSON.stringify({ lang: 'en', deviceId: 'device_test_000001', streets: ['BBR-jalan-makyong'] }));
    renderAt('/report');
    const brand = await screen.findByRole('link', { name: /Flood-Ready/ });
    await waitFor(() => expect(brand.querySelector('small')).toHaveTextContent('Jalan Makyong'));
  });
});

describe('App status line', () => {
  // The live / replay chip lives on the map only; a replayed street is labelled inside its hero card.
  it.each(['/report', '/streets'])('shows no live or replay chip under the header on %s', async (path) => {
    renderAt(path);
    await screen.findByRole('link', { name: /Flood-Ready/ });
    // Give the status request time to answer, then check nothing was drawn.
    await new Promise((r) => setTimeout(r, 50));
    expect(document.querySelector('.status-chip')).toBeNull();
  });
});

describe('App splash', () => {
  function renderSlow(delayMs: number) {
    let answer: () => void = () => {};
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (!url.includes('/status')) return Promise.resolve(new Response(JSON.stringify(streets), { status: 200 }));
      return new Promise<Response>((resolve) => {
        answer = () => resolve(new Response(JSON.stringify(status), { status: 200 }));
        if (delayMs >= 0) setTimeout(answer, delayMs);
      });
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/']}><App /></MemoryRouter></QueryClientProvider>);
    return () => answer();
  }
  const splash = () => screen.queryByRole('status', { name: /Flood-Ready/ });

  it('shows the splash only after 300 ms of loading, and removes it when the data arrives', async () => {
    const answer = renderSlow(-1);
    await new Promise((r) => setTimeout(r, 150));
    expect(splash()).toBeNull();
    await waitFor(() => expect(splash()).not.toBeNull(), { timeout: 1000 });
    expect(splash()).toHaveTextContent('Checking the river and rain…');
    expect(splash()!.querySelector('svg.logo-fill')).toHaveAttribute('width', '104');
    answer();
    expect(await screen.findByRole('button', { name: 'Find my street' })).toBeInTheDocument();
    expect(splash()).toBeNull();
  });

  it('never flashes on a fast load', async () => {
    renderSlow(50);
    expect(await screen.findByRole('button', { name: 'Find my street' })).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 400));
    expect(splash()).toBeNull();
  });

  it('goes on to the app when the first status request fails, so the screens can show their own errors', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.includes('/status') ? {} : streets), { status: url.includes('/status') ? 500 : 200 })));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/']}><App /></MemoryRouter></QueryClientProvider>);
    expect(await screen.findByRole('button', { name: 'Find my street' }, { timeout: 4000 })).toBeInTheDocument();
  });
});
