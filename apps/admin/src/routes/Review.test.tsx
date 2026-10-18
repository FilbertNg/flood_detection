import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { pendingAnswers } from '@floodready/shared/mocks';
import type { Answer } from '@floodready/shared';
import { renderApp, stubApi } from '../test-utils';
import { ReviewPage } from './Review';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const resident: Answer = { ...pendingAnswers[0], answer_id: 'ans_r', source: 'resident', photo_url: 'https://x.test/p.jpg', distance_m: 120 };
const demo: Answer = { ...pendingAnswers[0], answer_id: 'ans_d', source: 'demo' };

describe('ReviewPage', () => {
  it('lists pending answers with street, answer, depth, distance, time and photo', async () => {
    stubApi({ 'GET /admin/answers': [resident, demo] });
    renderApp(<ReviewPage />);
    const items = await screen.findAllByRole('article');
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByText('BBR-jalan-makyong')).toBeInTheDocument();
    expect(within(items[0]).getByText(/Answer: yes/i)).toBeInTheDocument();
    expect(within(items[0]).getByText(/Depth: knee/i)).toBeInTheDocument();
    expect(within(items[0]).getByText(/120 m/)).toBeInTheDocument();
    expect(within(items[0]).getByText(new RegExp(pendingAnswers[0].answered_at.slice(11, 16)))).toBeInTheDocument();
    expect(within(items[0]).getByRole('img', { name: /photo/i })).toHaveAttribute('src', 'https://x.test/p.jpg');
    expect(within(items[0]).queryByText('Demo')).toBeNull();
    expect(within(items[1]).getByText('Demo')).toBeInTheDocument();
  });

  it('marks an answer spam via PATCH and removes it from the queue', async () => {
    const fn = stubApi({
      'GET /admin/answers': [resident],
      'PATCH /admin/answers/ans_r': (init: RequestInit | undefined) => ({ body: { ...resident, ...JSON.parse(init!.body as string) } }),
    });
    renderApp(<ReviewPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Spam' }));
    await waitFor(() => expect(screen.getByText(/no answers waiting for review/i)).toBeInTheDocument());
    const patch = fn.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === 'PATCH')!;
    expect(JSON.parse((patch[1] as RequestInit).body as string)).toEqual({ review_status: 'spam' });
  });

  it('marks valid', async () => {
    const fn = stubApi({ 'GET /admin/answers': [resident], 'PATCH /admin/answers/ans_r': { ...resident, review_status: 'valid' } });
    renderApp(<ReviewPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Valid' }));
    await waitFor(() => expect(fn.mock.calls.some((c) => (c[1] as RequestInit | undefined)?.method === 'PATCH')).toBe(true));
    const patch = fn.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === 'PATCH')!;
    expect(JSON.parse((patch[1] as RequestInit).body as string)).toEqual({ review_status: 'valid' });
  });

  it('shows street names, resolves relative photos against the API and labels replay answers', async () => {
    const rel: Answer = { ...resident, answer_id: 'ans_rel', photo_url: '/photos/1.jpg', alert_id: 'a_replay', source: 'resident' };
    stubApi({
      'GET /admin/answers': [rel],
      'GET /streets': { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'LineString', coordinates: [] }, properties: { street_id: 'BBR-jalan-makyong', name: 'Jalan Makyong' } }] },
      'GET /alerts': [{ alert_id: 'a_replay', is_replay: true }],
    });
    renderApp(<ReviewPage />);
    expect(await screen.findByText('Jalan Makyong')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /photo/i }).getAttribute('src')).toMatch(/^https?:\/\/[^/]+\/photos\/1\.jpg$/);
    expect(await screen.findByText('Replay')).toBeInTheDocument();
  });

  it('shows an empty state', async () => {
    stubApi({ 'GET /admin/answers': [] });
    renderApp(<ReviewPage />);
    expect(await screen.findByText(/no answers waiting for review/i)).toBeInTheDocument();
  });

  it('shows an error state', async () => {
    stubApi({ 'GET /admin/answers': () => ({ status: 500, body: {} }) });
    renderApp(<ReviewPage />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load/i);
  });
});
