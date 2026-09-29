import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Settings } from '../Settings';
import { validPassword } from '../passwordPolicy';
import type { Profile, Session } from '../types';

const profile: Profile = { id: 'me', display_name: 'Ada', email: 'ada@example.com', avatar_url: null, email_verified: true, password_enabled: true, connected_providers: ['Google'] };
const session: Session = { user: profile, csrf_token: 'csrf', auth_mode: 'configured', email_enabled: true, email_delivery: true, providers: ['google', 'github'] };
const reply = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'Content-Type': 'application/json' } });
afterEach(() => vi.unstubAllGlobals());

it('saves profile name and immediately notifies the shared session', async () => {
  const fetcher = vi.fn().mockImplementation((_path, options) => Promise.resolve(reply(options.method === 'PATCH' ? { ...profile, display_name: 'Ada Lovelace' } : profile)));
  vi.stubGlobal('fetch', fetcher);
  const onUser = vi.fn();
  render(<Settings tab="profile" session={session} onUser={onUser} onLogout={vi.fn()} onBack={vi.fn()} />);
  await screen.findByLabelText('Display name');
  expect(screen.getByText('Email verified')).toBeVisible();
  await userEvent.clear(screen.getByLabelText('Display name'));
  await userEvent.type(screen.getByLabelText('Display name'), 'Ada Lovelace');
  await userEvent.click(screen.getByRole('button', { name: 'Save profile' }));
  await waitFor(() => expect(onUser).toHaveBeenCalledWith(expect.objectContaining({ display_name: 'Ada Lovelace' })));
  expect(screen.getByRole('status')).toHaveTextContent('Profile saved');
  expect(new Headers(fetcher.mock.calls[1][1].headers).get('X-CSRF-Token')).toBe('csrf');
});

it('uses the native file picker and sends selected bytes with CSRF', async () => {
  const fetcher = vi.fn().mockImplementation((_path, options) => Promise.resolve(reply(options.method === 'PUT' ? { ...profile, avatar_url: '/api/v1/me/avatar?v=1' } : profile)));
  vi.stubGlobal('fetch', fetcher);
  const onUser = vi.fn();
  render(<Settings tab="profile" session={session} onUser={onUser} onLogout={vi.fn()} onBack={vi.fn()} />);
  const input = await screen.findByLabelText('Choose profile picture');
  const file = new File(['synthetic image bytes'], 'photo.png', { type: 'image/png' });
  await userEvent.upload(input, file);
  await userEvent.click(screen.getByRole('button', { name: 'Save picture' }));
  await waitFor(() => expect(onUser).toHaveBeenCalledWith(expect.objectContaining({ avatar_url: '/api/v1/me/avatar?v=1' })));
  expect(fetcher.mock.calls[1][0]).toBe('/api/v1/me/avatar');
  expect(fetcher.mock.calls[1][1].body).toBe(file);
  expect(new Headers(fetcher.mock.calls[1][1].headers).get('X-CSRF-Token')).toBe('csrf');
});

it('shows security policy and generic recovery confirmation', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(path => Promise.resolve(reply(path === '/api/v1/me' ? profile : { detail: 'If eligible, check your inbox.' }))));
  render(<Settings tab="security" session={session} onUser={vi.fn()} onLogout={vi.fn()} onBack={vi.fn()} />);
  await screen.findByRole('button', { name: 'Change password' });
  expect(screen.getByText(/8–128 characters/)).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: 'Send password reset email' }));
  expect(await screen.findByRole('status')).toHaveTextContent('If eligible');
});

it('validates every password requirement in the frontend', () => {
  expect(validPassword('Aa1!aaaa')).toBe(true);
  expect(validPassword('Aa1_aaaa')).toBe(true);
  for (const value of ['Aa1!aaa', 'aa1!aaaa', 'AA1!AAAA', 'Aa!!aaaa', 'Aa12aaaa', 'Aa1!' + 'a'.repeat(125)]) expect(validPassword(value)).toBe(false);
});

// These boundary cases are also checked against the unchanged Python validator.
it.each([
  ['Aa1!😀😀', false],
  ['Aa1!' + '😀'.repeat(3), false],
  ['Aa1!' + '😀'.repeat(4), true],
  ['Aa1!' + '😀'.repeat(124), true],
  ['Aa1!' + '😀'.repeat(125), false],
  ['Aa1!' + 'a'.repeat(124), true],
  ['Aa1!' + 'a'.repeat(125), false],
  ['Aa1!e\u0301e\u0301', true],
])('counts Unicode code points for password length: %s', (value, accepted) => {
  expect(validPassword(value)).toBe(accepted);
});

it.each([
  { password_enabled: false, email_verified: false },
  { password_enabled: true, email_verified: false },
])('does not offer recovery without a verified local password: %j', async flags => {
  const fetcher = vi.fn().mockResolvedValue(reply({ ...profile, ...flags }));
  vi.stubGlobal('fetch', fetcher);
  render(<Settings tab="security" session={session} onUser={vi.fn()} onLogout={vi.fn()} onBack={vi.fn()} />);
  const button = await screen.findByRole('button', { name: 'Send password reset email' });
  expect(button).toBeDisabled();
  expect(screen.getByText(/recover access through that provider/)).toBeVisible();
  await userEvent.click(button);
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it('shows delivery request failures without a success notice', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(path => Promise.resolve(path === '/api/v1/me' ? reply(profile) : new Response(JSON.stringify({ detail: 'Email delivery is not configured' }), { status: 503 }))));
  render(<Settings tab="security" session={session} onUser={vi.fn()} onLogout={vi.fn()} onBack={vi.fn()} />);
  await userEvent.click(await screen.findByRole('button', { name: 'Send password reset email' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Email delivery is not configured');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});
