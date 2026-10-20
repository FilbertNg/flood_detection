import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { auth } from '../auth';
import { LoginPage } from './Login';

beforeEach(() => auth.logout());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function submit() {
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'ops@example.com' } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret' } });
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
}

describe('LoginPage', () => {
  it('stores the token on success', async () => {
    const fn = vi.fn(async () => new Response(JSON.stringify({ token: 'jwt-1' }), { status: 200 }));
    vi.stubGlobal('fetch', fn);
    render(<LoginPage />);
    submit();
    await waitFor(() => expect(auth.getToken()).toBe('jwt-1'));
    const call = fn.mock.calls[0] as unknown as [string, RequestInit];
    expect(call[0]).toMatch(/\/admin\/login$/);
    expect(JSON.parse(call[1].body as string)).toEqual({ email: 'ops@example.com', password: 'secret' });
  });

  it('shows the API message for a wrong password', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'Wrong email or password' }), { status: 401 })));
    render(<LoginPage />);
    submit();
    expect(await screen.findByRole('alert')).toHaveTextContent('Wrong email or password');
    expect(auth.getToken()).toBeNull();
  });
});
