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

const patches = (fn: ReturnType<typeof stubApi>) => fn.mock.calls
  .filter((c) => (c[1] as RequestInit | undefined)?.method === 'PATCH')
  .map((c) => JSON.parse((c[1] as RequestInit).body as string));
const echo = (base: Suggestion) => (init: RequestInit | undefined) => ({ body: { ...base, ...JSON.parse(init!.body as string) } });

describe('SuggestionsPage', () => {
  it('ranks by priority; the header has the street, the priority chip, the rule id and the status chip', async () => {
    stubApi({ 'GET /admin/suggestions': list });
    renderApp(<SuggestionsPage />);
    const items = await screen.findAllByRole('article');
    expect(items.map((i) => within(i).getByRole('heading').textContent)).toEqual(['High St', 'Med St', 'Low St']);
    const head = items[1].querySelector('.sug-top') as HTMLElement;
    expect(within(head).getByText('Medium priority')).toHaveClass('sug-prio');
    expect(within(head).getByText('SUG-2')).toHaveClass('sug-id');
    expect(within(head).getByText('Open')).toHaveClass('sug-status');
    expect(within(head).getByText('Open')).toHaveAttribute('data-s', 'open');
  });

  it('shows the action as the headline and the screening caveat under it', async () => {
    stubApi({ 'GET /admin/suggestions': [{ ...mk('s_a', 'high', 'High St'), text: 'Check outfall flap gates. Screening suggestion; site survey needed.' }] });
    renderApp(<SuggestionsPage />);
    const card = await screen.findByRole('article');
    expect(card.querySelector('.sug-action')).toHaveTextContent(/^Check outfall flap gates\.$/);
    expect(card.querySelector('.sug-caveat')).toHaveTextContent('Screening suggestion; site survey needed.');
  });

  it('shows the evidence as tiles and a date strip, with the method folded away', async () => {
    stubApi({ 'GET /admin/suggestions': list });
    renderApp(<SuggestionsPage />);
    const card = (await screen.findAllByRole('article'))[0];
    expect(within(card).getByText('Confirmed floods').closest('.sug-stat')).toHaveTextContent('1');
    expect(within(card).getByText('Heaviest rain at onset').closest('.sug-stat')).toHaveTextContent('61.5');
    const strip = within(card).getByLabelText('Flood dates: 12 November 2024');
    expect(strip.querySelector('.sug-days')).toHaveAttribute('aria-hidden', 'true');
    expect(strip.querySelectorAll('.sug-d.on')).toHaveLength(1);
    const how = card.querySelector('details.sug-method') as HTMLDetailsElement;
    expect(how.open).toBe(false);
    expect(within(how).getByText('How this was ranked')).toBeInTheDocument();
    expect(how).toHaveTextContent('note s_high');
  });

  it('labels SUG-5 alert episodes as such, never as flood dates', async () => {
    const sug5: Suggestion = { ...mk('s_five', 'medium', 'Five St'), rule: 'SUG-5',
      evidence: { episode_dates: ['2024-11-12', '2024-11-20'], max_depth: 'knee', rank: 2, eligible_streets: 40, notes: 'ranked' } };
    stubApi({ 'GET /admin/suggestions': [sug5] });
    renderApp(<SuggestionsPage />);
    const card = await screen.findByRole('article');
    expect(within(card).getByText('Alert episode starts')).toBeInTheDocument();
    expect(within(card).getByLabelText('Alert episode starts: 12 and 20 November 2024')).toBeInTheDocument();
    expect(within(card).getByText('Separate alert episodes').closest('.sug-stat')).toHaveTextContent('2');
    expect(within(card).getByText('Rank among eligible streets').closest('.sug-stat')).toHaveTextContent('2of 40');
    expect(within(card).queryByText(/Flood dates|Confirmed floods/)).toBeNull();
    expect(within(card).getByText('Deepest reported').closest('.sug-stat')).toHaveTextContent('knee');
  });

  it('hides a tile whose value is missing, and never shows an empty or 0 tile', async () => {
    const bare: Suggestion = { ...mk('s_bare', 'low', 'Bare St'), rule: 'SUG-7', evidence: { notes: 'stale' } };
    stubApi({ 'GET /admin/suggestions': [bare] });
    renderApp(<SuggestionsPage />);
    const card = await screen.findByRole('article');
    expect(card.querySelector('.sug-stats')).toBeNull();
    expect(card.querySelector('.sug-strip')).toBeNull();
  });

  it('falls back to a date list beyond three months', async () => {
    const many: Suggestion = { ...mk('s_many', 'high', 'Many St'),
      evidence: { flood_dates: ['2024-01-05', '2024-03-02', '2024-06-11', '2024-11-12'] } };
    stubApi({ 'GET /admin/suggestions': [many] });
    renderApp(<SuggestionsPage />);
    const card = await screen.findByRole('article');
    expect(card.querySelector('.sug-days')).toBeNull();
    expect(within(card).getByText(/Flood dates: 5 Jan 2024, 2 Mar 2024, 11 Jun 2024, 12 Nov 2024/)).toBeInTheDocument();
  });

  it('offers only the next step: Accept and Dismiss when open, Mark done and Back to open when accepted', async () => {
    stubApi({ 'GET /admin/suggestions': [mk('s_o', 'high', 'Open St'), { ...mk('s_a', 'low', 'Acc St'), status: 'accepted' }] });
    renderApp(<SuggestionsPage />);
    const [open, accepted] = await screen.findAllByRole('article');
    expect(within(open).getAllByRole('button').map((b) => b.textContent)).toEqual(['Accept', 'Dismiss']);
    expect(within(accepted).getAllByRole('button').map((b) => b.textContent)).toEqual(['Mark done', 'Back to open']);
    expect(within(accepted).getByText('Accepted')).toHaveAttribute('data-s', 'accepted');
  });

  it.each([
    ['open', 'Accept', 'accepted'], ['open', 'Dismiss', 'dismissed'], ['accepted', 'Mark done', 'done'],
    ['accepted', 'Back to open', 'open'], ['dismissed', 'Reopen', 'open'], ['done', 'Reopen', 'open'],
  ] as const)('from %s, %s PATCHes %s with the note and the card moves on', async (from, button, to) => {
    const base = { ...mk('s_high', 'high', 'High St'), status: from, note: 'crew booked' };
    const fn = stubApi({ 'GET /admin/suggestions': [base], 'PATCH /admin/suggestions/s_high': echo(base) });
    renderApp(<SuggestionsPage />);
    const card = await screen.findByRole('article');
    fireEvent.click(within(card).getByRole('button', { name: button }));
    await waitFor(() => expect(card.querySelector('.sug-status')).toHaveAttribute('data-s', to));
    expect(patches(fn)).toEqual([{ status: to, note: 'crew booked' }]);
  });

  it('saves the note on blur without changing the status, shows Saved, and can clear it', async () => {
    const base = { ...mk('s_high', 'high', 'High St'), status: 'accepted' as const, note: 'crew booked' };
    const fn = stubApi({ 'GET /admin/suggestions': [base], 'PATCH /admin/suggestions/s_high': echo(base) });
    renderApp(<SuggestionsPage />);
    const card = await screen.findByRole('article');
    const field = within(card).getByLabelText('Note (optional)');
    expect(within(card).queryByRole('button', { name: 'Save note' })).toBeNull();
    fireEvent.change(field, { target: { value: '' } });
    fireEvent.blur(field);
    await waitFor(() => expect(patches(fn)).toEqual([{ status: 'accepted', note: '' }]));
    expect(await within(card).findByText('Saved')).toBeInTheDocument();
    // Leaving the field again without a change sends nothing more.
    fireEvent.blur(field);
    await new Promise((r) => setTimeout(r, 50));
    expect(patches(fn)).toHaveLength(1);
  });

  it('saves the note 800 ms after typing stops', async () => {
    const base = mk('s_high', 'high', 'High St');
    const fn = stubApi({ 'GET /admin/suggestions': [base], 'PATCH /admin/suggestions/s_high': echo(base) });
    renderApp(<SuggestionsPage />);
    const card = await screen.findByRole('article');
    fireEvent.change(within(card).getByLabelText('Note (optional)'), { target: { value: 'Survey booked' } });
    await new Promise((r) => setTimeout(r, 400));
    expect(patches(fn)).toHaveLength(0);
    await waitFor(() => expect(patches(fn)).toEqual([{ status: 'open', note: 'Survey booked' }]), { timeout: 1500 });
  });

  it('shows the error message when a save fails', async () => {
    const base = mk('s_high', 'high', 'High St');
    stubApi({ 'GET /admin/suggestions': [base], 'PATCH /admin/suggestions/s_high': () => ({ status: 500, body: {} }) });
    renderApp(<SuggestionsPage />);
    const card = await screen.findByRole('article');
    fireEvent.click(within(card).getByRole('button', { name: 'Accept' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not save the change. Try again.');
    expect(within(card).queryByText('Saved')).toBeNull();
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
