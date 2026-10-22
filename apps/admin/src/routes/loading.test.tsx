import { cleanup, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { OpsMapPage } from './OpsMap';
import { ReportPage } from './Report';
import { ReviewPage } from './Review';
import { StatisticsPage } from './Statistics';
import { StreetDetailPage } from './StreetDetail';
import { SuggestionsPage } from './Suggestions';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

/** Every request stays pending, so each page shows its loading state. */
function renderPending(ui: ReactElement, path: string, route: string) {
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => {})));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}><Routes><Route path={route} element={ui} /></Routes></MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('admin pages show the logo-fill loader while their data loads', () => {
  it.each([
    ['suggestions', <SuggestionsPage />, '/suggestions', '/suggestions', 'Loading suggestions…'],
    ['review', <ReviewPage />, '/review', '/review', 'Loading the review queue…'],
    ['street detail', <StreetDetailPage />, '/street/BBR-jalan-makyong', '/street/:id', 'Loading the street…'],
    ['map', <OpsMapPage />, '/', '/', 'Loading the map…'],
    ['statistics', <StatisticsPage />, '/statistics', '/statistics', 'Loading statistics…'],
    ['report', <ReportPage />, '/reports', '/reports', 'Loading the report…'],
  ] as const)('%s', async (_name, ui, path, route, text) => {
    renderPending(ui, path, route);
    const el = (await screen.findByText(text)).closest('[role="status"]') as HTMLElement;
    expect(el).not.toBeNull();
    expect(el.querySelector('svg.logo-fill')).not.toBeNull();
  });
});

describe('whole-page loads are centred in the page', () => {
  it.each([
    [<SuggestionsPage />, '/suggestions', '/suggestions', 'Loading suggestions…'],
    [<StatisticsPage />, '/statistics', '/statistics', 'Loading statistics…'],
  ] as const)('%#', async (ui, path, route, text) => {
    renderPending(ui, path, route);
    expect((await screen.findByText(text)).closest('[role="status"]')).toHaveClass('page-loading');
  });
});
