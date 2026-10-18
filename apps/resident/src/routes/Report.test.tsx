import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { streets } from '@floodready/shared/mocks';
import { ReportPage } from './Report';

function renderReport(lang: 'en' | 'ms', url = '/report', mine: string[] = []) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === 'POST') return new Response(JSON.stringify({ answer_id: 'ans_1' }), { status: 201 });
    void input;
    return new Response(JSON.stringify(streets), { status: 200 });
  });
  vi.stubGlobal('fetch', fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}><ReportPage lang={lang} deviceId="dev_1" mine={mine} /></MemoryRouter>
    </QueryClientProvider>,
  );
  return fetchMock;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('ReportPage', () => {
  it('reports a flood on the chosen street with no alert id, while no alert is active', async () => {
    const fetchMock = renderReport('en', '/report?street=BBR-persiaran-batu-belah');
    const select = (await screen.findByLabelText('Which street?')) as HTMLSelectElement;
    expect(select.value).toBe('BBR-persiaran-batu-belah');
    fireEvent.click(screen.getByRole('button', { name: 'Knee' }));
    fireEvent.click(screen.getByRole('button', { name: 'Send report' }));
    expect(await screen.findByRole('heading', { name: 'Thank you' })).toBeInTheDocument();
    const post = fetchMock.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === 'POST')!;
    const body = (post[1] as RequestInit).body as FormData;
    expect(body.get('street_id')).toBe('BBR-persiaran-batu-belah');
    expect(body.get('answer')).toBe('report');
    expect(body.get('device_id')).toBe('dev_1');
    expect(body.has('alert_id')).toBe(false);
  });

  it('defaults to the first followed street and speaks Malay', async () => {
    renderReport('ms', '/report', ['BBR-jalan-makyong']);
    const select = (await screen.findByLabelText('Jalan yang mana?')) as HTMLSelectElement;
    expect(select.value).toBe('BBR-jalan-makyong');
    expect(screen.getByRole('button', { name: 'Hantar laporan' })).toBeInTheDocument();
    expect(screen.getByText(/JPS, MET dan NADMA ialah sumber rasmi/)).toBeInTheDocument();
  });
});
