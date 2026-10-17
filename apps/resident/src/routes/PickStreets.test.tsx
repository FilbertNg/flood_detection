import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
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
  it('offers notifications after saving streets and subscribes with the saved streets', async () => {
    const onSave = renderPick();
    const boxes = await screen.findAllByRole('checkbox');
    fireEvent.click(boxes[0]);
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onSave).toHaveBeenCalledTimes(1);
    const saved = onSave.mock.calls[0][0] as string[];
    expect(saved).toHaveLength(1);
    fireEvent.click(await screen.findByRole('button', { name: 'Turn on alerts' }));
    expect(mocked.enablePush).toHaveBeenCalledWith({ deviceId: 'dev_1', streetIds: saved, lang: 'en' });
  });
});
