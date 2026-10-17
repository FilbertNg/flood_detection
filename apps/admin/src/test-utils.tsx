import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router';
import { vi } from 'vitest';

type Handler = (init: RequestInit | undefined, url: string) => { status?: number; body: unknown };

/** Stub fetch with a body (or handler) per "METHOD /path" (query string ignored). Unknown routes return 404. */
export function stubApi(routes: Record<string, Handler | unknown>) {
  const fn = vi.fn(async (input: string, init?: RequestInit) => {
    const url = new URL(input);
    const key = `${init?.method ?? 'GET'} ${url.pathname.replace('/api/v1', '')}`;
    const route = routes[key];
    if (route === undefined) return new Response(JSON.stringify({ detail: 'nope' }), { status: 404 });
    const out = typeof route === 'function' ? (route as Handler)(init, input) : { body: route };
    return new Response(JSON.stringify(out.body), { status: out.status ?? 200 });
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}

/** A 401 answer for stubApi routes. */
export const unauthorized = () => ({ status: 401, body: { detail: 'Invalid token' } });

export function renderApp(ui: ReactElement, path = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}
