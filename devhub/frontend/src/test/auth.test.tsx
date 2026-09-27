import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuthScreen, ChangePassword } from '../AuthScreen';
import App from '../App';
import type { Session } from '../types';

const session: Session = { user: null, csrf_token: null, auth_mode: 'configured', providers: ['google', 'github'], email_enabled: true, email_delivery: true };
const password = 'A secure river lantern passphrase!'; // pragma: allowlist secret -- synthetic fixture
function reply(data: unknown, status = 200) { return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } }); }
afterEach(() => { vi.unstubAllGlobals(); window.history.replaceState(null, '', '/'); });

describe('Authentication screens', () => {
  it('offers providers and email login with existing shared sessions', async () => {
    const signed = { ...session, user: { id: 'one', email: 'one@example.com', display_name: 'One' }, csrf_token: 'csrf' };
    const fetcher = vi.fn().mockResolvedValue(reply(signed));
    vi.stubGlobal('fetch', fetcher);
    const onLogin = vi.fn();
    render(<AuthScreen session={session} onLogin={onLogin} />);
    expect(screen.getByRole('link', { name: 'Continue with Google' })).toHaveAttribute('href', '/auth/google/login');
    expect(screen.getByRole('link', { name: 'Continue with GitHub' })).toHaveAttribute('href', '/auth/login');
    await userEvent.type(screen.getByLabelText('Email', { exact: true }), 'one@example.com');
    await userEvent.type(screen.getByLabelText('Password', { exact: true }), password);
    await userEvent.click(screen.getByRole('button', { name: 'Login' }));
    await waitFor(() => expect(onLogin).toHaveBeenCalledWith(signed));
    expect(fetcher.mock.calls[0][0]).toBe('/auth/email-login');
  });
  it('validates signup confirmation before submitting and shows verification notice', async () => {
    const fetcher = vi.fn().mockResolvedValue(reply({ detail: 'Check your inbox to verify your email.' }, 202));
    vi.stubGlobal('fetch', fetcher);
    render(<AuthScreen session={session} onLogin={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
    await userEvent.type(screen.getByLabelText('First Name'), 'One');
    await userEvent.type(screen.getByLabelText('Last Name'), 'Person');
    await userEvent.type(screen.getByLabelText('Email', { exact: true }), 'one@example.com');
    await userEvent.type(screen.getByLabelText('Password', { exact: true }), password);
    await userEvent.type(screen.getByLabelText('Confirm password'), 'Another very long wrong password');
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Passwords do not match');
    expect(fetcher).not.toHaveBeenCalled();
    await userEvent.clear(screen.getByLabelText('Confirm password'));
    await userEvent.type(screen.getByLabelText('Confirm password'), password);
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Check your inbox');
    expect(fetcher.mock.calls[0][0]).toBe('/auth/signup');
  });
  it('shows generic recovery confirmation and handles an expired reset link', async () => {
    const fetcher = vi.fn().mockResolvedValue(reply({ detail: 'If eligible, check your inbox.' }, 202));
    vi.stubGlobal('fetch', fetcher);
    const view = render(<AuthScreen session={session} onLogin={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: 'Forgot password?' }));
    await userEvent.type(screen.getByLabelText('Email'), 'one@example.com');
    await userEvent.click(screen.getByRole('button', { name: 'Send reset link' }));
    expect(await screen.findByRole('status')).toHaveTextContent('If eligible');
    view.unmount();
    fetcher.mockResolvedValue(reply({ detail: 'This link is invalid, expired, or already used.' }, 400));
    render(<AuthScreen session={session} onLogin={vi.fn()} authLink={'#reset-password=' + 'x'.repeat(43)} />);
    await userEvent.type(screen.getByLabelText('Password', { exact: true }), password);
    await userEvent.type(screen.getByLabelText('Confirm password'), password);
    await userEvent.click(screen.getByRole('button', { name: 'Reset password' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('expired');
    expect(fetcher.mock.calls[1][0]).toBe('/auth/reset-password');
  });
  it('removes emailed token fragments from the address bar without sending them in session requests', async () => {
    window.history.replaceState(null, '', '/#reset-password=' + 'x'.repeat(43));
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(reply(session)));
    vi.stubGlobal('fetch', fetcher);
    render(<App />);
    expect(await screen.findByRole('heading', { name: 'Choose a new password' })).toBeVisible();
    expect(window.location.hash).toBe('');
    expect(fetcher.mock.calls.every(call => call[0] === '/auth/session')).toBe(true);
  });
  it('renders cancelled OAuth errors with a retry path', () => {
    render(<AuthScreen session={session} onLogin={vi.fn()} authLink="#auth-error=retry" />);
    expect(screen.getByRole('alert')).toHaveTextContent('cancelled');
    expect(screen.getByRole('link', { name: 'Continue with Google' })).toBeVisible();
  });
  it('opens emailed links in an already loaded tab', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(reply(session))));
    render(<App />);
    await screen.findByRole('heading', { name: 'Welcome to DevHub' });
    await act(async () => {
      window.history.replaceState(null, '', '/#verify-email=' + 'x'.repeat(43));
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    });
    expect(await screen.findByRole('heading', { name: 'Verify your email' })).toBeVisible();
    expect(window.location.hash).toBe('');
  });
});


it('changes a password with CSRF, confirmation, and logout callback', async () => {
  const fetcher = vi.fn().mockResolvedValue(reply({ detail: 'Password changed' }));
  vi.stubGlobal('fetch', fetcher);
  const changed = vi.fn();
  render(<ChangePassword session={{ ...session, csrf_token: 'test-csrf' }} onClose={vi.fn()} onChanged={changed} />);
  await userEvent.type(screen.getByLabelText('Current password'), password);
  await userEvent.type(screen.getByLabelText('New password', { exact: true }), password);
  await userEvent.type(screen.getByLabelText('Confirm new password'), 'a different secure passphrase');
  await userEvent.click(screen.getByRole('button', { name: 'Save password and sign out' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Passwords do not match');
  expect(fetcher).not.toHaveBeenCalled();
  await userEvent.clear(screen.getByLabelText('Confirm new password'));
  await userEvent.type(screen.getByLabelText('Confirm new password'), password);
  await userEvent.click(screen.getByRole('button', { name: 'Save password and sign out' }));
  await waitFor(() => expect(changed).toHaveBeenCalled());
  expect(fetcher.mock.calls[0][0]).toBe('/auth/change-password');
  expect(new Headers(fetcher.mock.calls[0][1].headers).get('X-CSRF-Token')).toBe('test-csrf');
});
