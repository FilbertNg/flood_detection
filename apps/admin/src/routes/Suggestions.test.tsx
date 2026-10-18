import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { suggestions } from '@floodready/shared/mocks';
import type { Suggestion } from '@floodready/shared';
import { renderApp, stubApi } from '../test-utils';
import { SuggestionsPage } from './Suggestions';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const mk = (id: string, priority: Suggestion['priority'], name: string): Suggestion => ({
  ...suggestions[0], id, priority, street_name: name,
  evidence: { flood_dates: ['2024-11-12'], rain_at_onset_mm: [61.5], notes: 'note ' + id },
});
const list = [mk('s_low', 'low', 'Low St'), mk('s_high', 'high', 'High St'), mk('s_med', 'medium', 'Med St')];

describe('SuggestionsPage', () => {
  it('ranks by priority and shows evidence and the screening suffix', async () => {
    stubApi({ 'GET /admin/suggestions': list });
    renderApp(<SuggestionsPage />);
    const items = await screen.findAllByRole('article');
    expect(items.map((i) => within(i).getByRole('heading').textContent)).toEqual(['High St', 'Med St', 'Low St']);
    expect(within(items[0]).getByText(/12 Nov 2024/)).toBeInTheDocument();
    expect(within(items[0]).getByText(/61\.5 mm/)).toBeInTheDocument();
    expect(within(items[0]).getByText('note s_high')).toBeInTheDocument();
    expect(within(items[0]).getByText(/Screening suggestion; site survey needed\.$/)).toBeInTheDocument();
  });

  it('PATCHes the status with the note and updates the card', async () => {
    const fn = stubApi({
      'GET /admin/suggestions': [mk('s_high', 'high', 'High St')],
      'PATCH /admin/suggestions/s_high': (init: RequestInit | undefined) => ({ body: { ...mk('s_high', 'high', 'High St'), ...JSON.parse(init!.body as string) } }),
    });
    renderApp(<SuggestionsPage />);
    const card = await screen.findByRole('article');
    fireEvent.change(within(card).getByLabelText('Note (optional)'), { target: { value: 'crew booked' } });
    fireEvent.click(within(card).getByRole('button', { name: 'Accepted' }));
    await waitFor(() => expect(within(card).getByRole('button', { name: 'Accepted' })).toHaveAttribute('aria-pressed', 'true'));
    const patch = fn.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === 'PATCH')!;
    expect(JSON.parse((patch[1] as RequestInit).body as string)).toEqual({ status: 'accepted', note: 'crew booked' });
  });

  it('saves a note without changing the status, and can clear it', async () => {
    const base = { ...mk('s_high', 'high', 'High St'), status: 'accepted' as const, note: 'crew booked' };
    const fn = stubApi({
      'GET /admin/suggestions': [base],
      'PATCH /admin/suggestions/s_high': (init: RequestInit | undefined) => ({ body: { ...base, ...JSON.parse(init!.body as string) } }),
    });
    renderApp(<SuggestionsPage />);
    const card = await screen.findByRole('article');
    fireEvent.change(within(card).getByLabelText('Note (optional)'), { target: { value: '' } });
    fireEvent.click(within(card).getByRole('button', { name: 'Save note' }));
    await waitFor(() => expect(fn.mock.calls.some((c) => (c[1] as RequestInit | undefined)?.method === 'PATCH')).toBe(true));
    const patch = fn.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === 'PATCH')!;
    expect(JSON.parse((patch[1] as RequestInit).body as string)).toEqual({ status: 'accepted', note: '' });
  });

  it('shows an empty state', async () => {
    stubApi({ 'GET /admin/suggestions': [] });
    renderApp(<SuggestionsPage />);
    expect(await screen.findByText(/no suggestions yet/i)).toBeInTheDocument();
  });

  it('shows an error state', async () => {
    stubApi({ 'GET /admin/suggestions': () => ({ status: 500, body: {} }) });
    renderApp(<SuggestionsPage />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load/i);
  });
});
