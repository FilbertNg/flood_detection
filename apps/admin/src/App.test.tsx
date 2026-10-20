import { cleanup, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { status, stations, streets } from '@floodready/shared/mocks';
import { App } from './App';
import { auth } from './auth';
import { renderApp, stubApi, unauthorized } from './test-utils';

vi.mock('./components/OpsMapView', () => ({ OpsMapView: () => <div data-testid="map" /> }));

beforeEach(() => auth.logout());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('App shell', () => {
  it('shows the login page when there is no token', () => {
    stubApi({});
    renderApp(<App />);
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Statistics' })).not.toBeInTheDocument();
  });

  it('shows the five navigation links when signed in', () => {
    auth.login('t');
    stubApi({ 'GET /status': status, 'GET /streets': streets, 'GET /stations': stations });
    renderApp(<App />);
    for (const name of ['Map', 'Statistics', 'Reports', 'Suggestions', 'Review']) {
      expect(screen.getByRole('link', { name })).toBeInTheDocument();
    }
  });

  it('groups the navigation in a sidebar: Monitor, Analyse, Follow up', () => {
    auth.login('t');
    stubApi({ 'GET /status': status, 'GET /streets': streets, 'GET /stations': stations });
    renderApp(<App />);
    const groups: Record<string, string[]> = {
      Monitor: ['Map'],
      Analyse: ['Statistics', 'Reports'],
      'Follow up': ['Suggestions', 'Review'],
    };
    const nav = screen.getByRole('navigation', { name: 'Main' });
    expect(nav.closest('aside')).not.toBeNull();
    for (const [group, links] of Object.entries(groups)) {
      const list = within(nav).getByRole('list', { name: group });
      expect(within(list).getAllByRole('link').map((a) => a.textContent)).toEqual(links);
    }
    expect(screen.getByRole('button', { name: 'Sign out' }).closest('aside')).not.toBeNull();
  });

  it('routes the four admin pages and returns to login on a 401 from them', async () => {
    auth.login('t');
    stubApi({ 'GET /admin/stats': unauthorized });
    renderApp(<App />, '/statistics');
    expect(screen.getByRole('heading', { name: 'Statistics' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument());
  });

  it('returns to login when the API answers 401', async () => {
    auth.login('expired');
    stubApi({ 'GET /status': unauthorized, 'GET /streets': unauthorized, 'GET /stations': unauthorized });
    renderApp(<App />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument());
    expect(auth.getToken()).toBeNull();
  });
});
