import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { streets } from '@floodready/shared/mocks';
import * as subscribe from '../push/subscribe';
import { PickStreetsPage } from './PickStreets';

vi.mock('../push/subscribe');
const mocked = vi.mocked(subscribe);

function renderPick(onSave = vi.fn()) {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(streets), { status: 200 })));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter><PickStreetsPage lang="en" mine={[]} deviceId="dev_1" onSave={onSave} /></MemoryRouter>
    </QueryClientProvider>,
  );
  return onSave;
}

beforeEach(() => {
  mocked.pushSupport.mockReturnValue('ok');
  mocked.isSubscribed.mockResolvedValue(false);
  mocked.enablePush.mockResolvedValue('granted');
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.resetAllMocks();
});

describe('PickStreetsPage push offer', () => {
  it('offers notifications after saving my street and subscribes with it', async () => {
    const onSave = renderPick();
    const options = await screen.findAllByRole('radio');
    fireEvent.click(options[0]);
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onSave).toHaveBeenCalledTimes(1);
    const saved = onSave.mock.calls[0][0] as string[];
    expect(saved).toHaveLength(1);
    fireEvent.click(await screen.findByRole('button', { name: 'Turn on alerts' }));
    expect(mocked.enablePush).toHaveBeenCalledWith({ deviceId: 'dev_1', streetIds: saved, lang: 'en' });
  });
});

describe('PickStreetsPage returns to the home page', () => {
  it('goes to / when the resident is done after saving', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(streets), { status: 200 })));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/streets']}>
          <Routes>
            <Route path="/streets" element={<PickStreetsPage lang="en" mine={[]} deviceId="dev_1" onSave={vi.fn()} />} />
            <Route path="/" element={<p>home</p>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.click((await screen.findAllByRole('radio'))[0]);
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Not now' }));
    expect(await screen.findByText('home')).toBeInTheDocument();
  });
});

describe('PickStreetsPage back link', () => {
  it('links back to the home page', async () => {
    renderPick();
    await screen.findAllByRole('radio');
    expect(screen.getByRole('link', { name: '← Back' })).toHaveAttribute('href', '/');
  });
});

describe('PickStreetsPage keeps one street', () => {
  it('lets the resident choose one street; a second choice replaces the first', async () => {
    const onSave = renderPick();
    const options = await screen.findAllByRole('radio');
    fireEvent.click(options[0]);
    fireEvent.click(options[1]);
    expect(options[0]).not.toBeChecked();
    expect(options[1]).toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onSave).toHaveBeenCalledWith([streets.features.map((f) => f.properties).sort((a, b) => a.name.localeCompare(b.name))[1].street_id]);
  });

  it('shows an older phone’s first saved street as chosen and saves just one', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(streets), { status: 200 })));
    const onSave = vi.fn();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter><PickStreetsPage lang="en" mine={['BBR-jalan-makyong', 'BBR-persiaran-batu-belah']} deviceId="dev_1" onSave={onSave} /></MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByRole('radio', { name: 'Jalan Makyong' })).toBeChecked();
    expect(screen.getByRole('radio', { name: 'Persiaran Batu Belah' })).not.toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onSave).toHaveBeenCalledWith(['BBR-jalan-makyong']);
  });
});
