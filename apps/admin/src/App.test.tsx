import { cleanup, screen, waitFor } from '@testing-library/react';
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

  it('placeholder routes say Coming in WP13', () => {
    auth.login('t');
    stubApi({ 'GET /status': status });
    renderApp(<App />, '/statistics');
    expect(screen.getByText(/Coming in WP13/)).toBeInTheDocument();
  });

  it('returns to login when the API answers 401', async () => {
    auth.login('expired');
    stubApi({ 'GET /status': unauthorized, 'GET /streets': unauthorized, 'GET /stations': unauthorized });
    renderApp(<App />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument());
    expect(auth.getToken()).toBeNull();
  });
});
