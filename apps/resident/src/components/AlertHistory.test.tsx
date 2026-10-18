import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { AlertSummary } from '@floodready/shared';
import { alertSummary } from '@floodready/shared/mocks';
import { AlertHistory } from './AlertHistory';

afterEach(cleanup);

const confirmed: AlertSummary = { ...alertSummary, alert_id: 'a_02', level: 'danger', outcome: 'confirmed', is_replay: false, issued_at: '2026-10-01T14:05:00+08:00' };
const notConfirmed: AlertSummary = { ...alertSummary, alert_id: 'a_03', level: 'watch', outcome: 'not_confirmed', is_replay: false };
const allClear: AlertSummary = { ...alertSummary, alert_id: 'a_04', kind: 'all_clear', level: 'normal', push: false };

describe('AlertHistory', () => {
  it('lists each alert with level, time and outcome badge', () => {
    render(<AlertHistory lang="en" history={[confirmed, notConfirmed]} />);
    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent('Danger');
    expect(items[0]).toHaveTextContent('1 Oct 2026, 14:05');
    expect(items[0]).toHaveTextContent('Confirmed');
    expect(items[1]).toHaveTextContent('Not confirmed');
    expect(screen.queryByText('Replay')).not.toBeInTheDocument();
  });

  it('explains unverified as no answers yet, never a false alarm, and tags replay alerts', () => {
    render(<AlertHistory lang="en" history={[alertSummary]} />);
    expect(screen.getByText('Unverified')).toBeInTheDocument();
    expect(screen.getByText(/no answers yet/i)).toBeInTheDocument();
    expect(screen.getByText('Replay')).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/false alarm/i);
  });

  it('is in Malay and skips all-clears', () => {
    render(<AlertHistory lang="ms" history={[confirmed, allClear]} />);
    expect(screen.getAllByRole('listitem')).toHaveLength(1);
    expect(screen.getByText('Disahkan')).toBeInTheDocument();
    render(<AlertHistory lang="ms" history={[alertSummary]} />);
    expect(screen.getByText('Belum disahkan')).toBeInTheDocument();
    expect(screen.getByText(/belum ada jawapan/i)).toBeInTheDocument();
    expect(screen.getByText('Main semula')).toBeInTheDocument();
  });

  it('shows an empty state', () => {
    render(<AlertHistory lang="en" history={[]} />);
    expect(screen.getByText(/No alerts for this street yet/)).toBeInTheDocument();
  });
});
