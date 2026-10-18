import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { report } from '@floodready/shared/mocks';
import { renderApp, stubApi } from '../test-utils';
import { ReportPage } from './Report';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('ReportPage', () => {
  it('renders every section from the API', async () => {
    stubApi({ 'GET /admin/report': report });
    renderApp(<ReportPage />);
    expect(await screen.findByRole('heading', { name: /^summary/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /^events/i })).toBeInTheDocument();
    expect(screen.getByText('Persiaran Sungai Keramat, Klang')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /^top streets/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /^suggestions/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /^data health/i })).toBeInTheDocument();
    expect(screen.getByText(/site survey needed\.$/)).toBeInTheDocument();
  });

  it('refetches for the chosen month', async () => {
    const fn = stubApi({ 'GET /admin/report': report });
    renderApp(<ReportPage />);
    await screen.findByRole('heading', { name: /^summary/i });
    fireEvent.change(screen.getByLabelText('Month'), { target: { value: '2024-10' } });
    await waitFor(() => expect(fn.mock.calls.some((c) => String(c[0]).includes('month=2024-10'))).toBe(true));
  });

  it('prints through the browser', async () => {
    stubApi({ 'GET /admin/report': report });
    const print = vi.fn();
    vi.stubGlobal('print', print);
    renderApp(<ReportPage />);
    await screen.findByRole('heading', { name: /^summary/i });
    fireEvent.click(screen.getByRole('button', { name: 'Print / Save as PDF' }));
    expect(print).toHaveBeenCalled();
  });

  it('shows empty states for a month without events', async () => {
    stubApi({ 'GET /admin/report': { ...report, events: [], top_streets: [], suggestions: [], data_health: [] } });
    renderApp(<ReportPage />);
    expect(await screen.findByText(/no events recorded this month/i)).toBeInTheDocument();
  });

  it('shows an error state', async () => {
    stubApi({ 'GET /admin/report': () => ({ status: 500, body: {} }) });
    renderApp(<ReportPage />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load/i);
  });
});
