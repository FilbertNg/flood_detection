import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as subscribe from '../push/subscribe';
import { NotificationOffer } from './NotificationOffer';

vi.mock('../push/subscribe');
const mocked = vi.mocked(subscribe);

const base = { deviceId: 'dev_1', streetIds: ['BBR-a'], onDone: () => {} };

beforeEach(() => {
  mocked.pushSupport.mockReturnValue('ok');
  mocked.isSubscribed.mockResolvedValue(false);
  mocked.enablePush.mockResolvedValue('granted');
  mocked.stopPush.mockResolvedValue(undefined);
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('NotificationOffer', () => {
  it('explains why in English and subscribes with streets and language on tap', async () => {
    render(<NotificationOffer lang="en" {...base} />);
    expect(await screen.findByText(/even when the app is closed/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Turn on alerts' }));
    expect(mocked.enablePush).toHaveBeenCalledWith({ deviceId: 'dev_1', streetIds: ['BBR-a'], lang: 'en' });
    expect(await screen.findByText('Alerts are on for your streets.')).toBeInTheDocument();
  });

  it('speaks Malay', async () => {
    render(<NotificationOffer lang="ms" {...base} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Hidupkan amaran' }));
    expect(mocked.enablePush).toHaveBeenCalledWith(expect.objectContaining({ lang: 'ms' }));
    expect(await screen.findByText('Amaran telah dihidupkan untuk jalan anda.')).toBeInTheDocument();
  });

  it('explains a denied permission', async () => {
    mocked.enablePush.mockResolvedValue('denied');
    render(<NotificationOffer lang="en" {...base} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Turn on alerts' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/blocked/);
  });

  it('shows the install guide on iPhone Safari outside the installed app', async () => {
    mocked.pushSupport.mockReturnValue('needs-install');
    render(<NotificationOffer lang="en" {...base} />);
    expect(await screen.findByText(/Add to Home Screen/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Turn on alerts' })).toBeNull();
  });

  it('shows a message when the browser cannot receive alerts', async () => {
    mocked.pushSupport.mockReturnValue('unsupported');
    render(<NotificationOffer lang="en" {...base} />);
    expect(await screen.findByText(/cannot receive alerts/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Turn on alerts' })).toBeNull();
  });

  it('stops notifications when already subscribed', async () => {
    mocked.isSubscribed.mockResolvedValue(true);
    render(<NotificationOffer lang="en" {...base} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Stop notifications' }));
    await waitFor(() => expect(mocked.stopPush).toHaveBeenCalledWith('dev_1'));
    expect(await screen.findByText(/Notifications are off/)).toBeInTheDocument();
  });
});
