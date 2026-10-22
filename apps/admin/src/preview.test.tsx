import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { status, stations, streets, suggestions } from '@floodready/shared/mocks';
import type { Status, Suggestion } from '@floodready/shared';
import { App } from './App';
import { auth } from './auth';
import { LoginPage } from './routes/Login';
import { OpsMapPage } from './routes/OpsMap';
import { SuggestionsPage } from './routes/Suggestions';
import { renderApp, stubApi } from './test-utils';

vi.mock('./components/OpsMapView', () => ({ OpsMapView: () => <div data-testid="map" /> }));

beforeEach(() => auth.logout());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const live: Status = { ...status, mode: 'live', replay: null };
const PREVIEW = 'Try a read-only preview';

describe('Read-only preview', () => {
  it('opens from the login page without an email or password', async () => {
    const fn = stubApi({ 'POST /admin/preview': { token: 'jwt-p' } });
    renderApp(<LoginPage />);
    fireEvent.click(screen.getByRole('button', { name: PREVIEW }));
    await waitFor(() => expect(auth.getToken()).toBe('jwt-p'));
    expect(auth.isPreview()).toBe(true);
    const call = fn.mock.calls[0] as unknown as [string, RequestInit];
    expect(call[0]).toMatch(/\/admin\/preview$/);
    expect(call[1].method).toBe('POST');
  });

  it('says so when the server has the preview switched off', async () => {
    stubApi({});
    renderApp(<LoginPage />);
    fireEvent.click(screen.getByRole('button', { name: PREVIEW }));
    expect(await screen.findByRole('alert')).toHaveTextContent('The read-only preview is not available right now.');
    expect(auth.getToken()).toBeNull();
  });

  it('a normal sign-in is not a preview', async () => {
    stubApi({ 'POST /admin/login': { token: 'jwt-1' } });
    renderApp(<LoginPage />);
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'ops@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    await waitFor(() => expect(auth.getToken()).toBe('jwt-1'));
    expect(auth.isPreview()).toBe(false);
  });

  it('shows a read-only banner, hides Review and offers Leave preview', () => {
    auth.login('t', { preview: true });
    stubApi({ 'GET /status': live, 'GET /streets': streets, 'GET /stations': stations });
    renderApp(<App />);
    expect(screen.getByRole('status', { name: 'Read-only preview' })).toHaveTextContent(
      "Read-only preview: changes are switched off and residents' answers are hidden.");
    for (const name of ['Map', 'Statistics', 'Reports', 'Suggestions']) {
      expect(screen.getByRole('link', { name })).toBeInTheDocument();
    }
    expect(screen.queryByRole('link', { name: 'Review' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Leave preview' }));
    expect(auth.getToken()).toBeNull();
    expect(auth.isPreview()).toBe(false);
  });

  it('sends /review back to the map', async () => {
    auth.login('t', { preview: true });
    const fn = stubApi({ 'GET /status': live, 'GET /streets': streets, 'GET /stations': stations });
    renderApp(<App />, '/review');
    expect(await screen.findByTestId('map')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /review/i })).not.toBeInTheDocument();
    expect(fn.mock.calls.some((c) => String(c[0]).includes('/admin/answers'))).toBe(false);
  });

  it('keeps the preview across a reload', () => {
    auth.login('t', { preview: true });
    auth.restore();
    expect(auth.getToken()).toBe('t');
    expect(auth.isPreview()).toBe(true);
  });

  it('shows suggestions without the note field or status buttons; an existing note is shown as text', async () => {
    auth.login('t', { preview: true });
    const s: Suggestion = { ...suggestions[0], id: 's1', status: 'accepted', note: 'crew booked' };
    stubApi({ 'GET /admin/suggestions': [s] });
    renderApp(<SuggestionsPage />);
    const card = await screen.findByRole('article');
    expect(within(card).queryByRole('button')).not.toBeInTheDocument();
    expect(within(card).queryByRole('textbox')).not.toBeInTheDocument();
    expect(within(card).getByText('Note: crew booked')).toBeInTheDocument();
  });

  it('hides the replay control on the map page', async () => {
    auth.login('t', { preview: true });
    stubApi({ 'GET /status': live, 'GET /streets': streets, 'GET /stations': stations });
    renderApp(<OpsMapPage />);
    await screen.findByTestId('map');
    expect(screen.queryByRole('heading', { name: 'Demo replay' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /replay/i })).not.toBeInTheDocument();
  });
});
