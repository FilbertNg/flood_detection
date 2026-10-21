import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { status } from '@floodready/shared/mocks';
import { StatusLine } from './StatusLine';

function renderLine(reply: unknown, lang: 'en' | 'ms' = 'en') {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(reply), { status: 200 })));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><StatusLine lang={lang} /></QueryClientProvider>);
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('StatusLine chip', () => {
  const replay = { ...status, mode: 'replay', data_time: '2024-11-12T09:15:00+08:00', replay: { event: '2024-11-12', speed: 60 } };

  it('names the replayed flood and shows the replay clock', async () => {
    renderLine(replay);
    const bar = (await screen.findByText('12 Nov 2024 flood')).closest('.status-chip')!;
    expect(bar).toHaveClass('replay');
    expect(bar).toHaveTextContent('Replay');
    expect(bar.querySelector('time')).toHaveTextContent('09:15');
  });

  it('shows no clock when the replay time is not on the flood day', async () => {
    renderLine({ ...replay, data_time: '2026-10-21T00:39:00+08:00' });
    const bar = (await screen.findByText('12 Nov 2024 flood')).closest('.status-chip')!;
    expect(bar.querySelector('time')).toBeNull();
    expect(bar).not.toHaveTextContent('2026');
  });

  it('shows Live with the data time, the full date for screen readers', async () => {
    renderLine({ ...status, mode: 'live', replay: null, data_time: '2026-10-21T00:59:00+08:00' });
    const chip = (await screen.findByText(/^Live/)).closest('.status-chip')!;
    expect(chip).toHaveClass('live');
    expect(chip).toHaveTextContent('Live · 00:59');
    expect(chip).toHaveAttribute('aria-label', 'Live · Data as of 21 Oct 2026, 00:59');
  });

  it('is in Malay', async () => {
    renderLine(replay, 'ms');
    expect(await screen.findByText('Banjir 12 Nov 2024')).toBeInTheDocument();
    expect(screen.getByText('Main semula')).toBeInTheDocument();
  });
});
