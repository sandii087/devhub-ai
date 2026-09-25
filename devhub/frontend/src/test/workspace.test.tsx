import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../App';
import { request } from '../api';
import { TaskForm } from '../TaskForm';
import { AIPanel } from '../AIPanel';

const user = { id: 'person-1', display_name: 'Alex Morgan', email: 'alex@example.com' };
const session = { user, csrf_token: 'csrf-test', auth_mode: 'development' as const };
function respond(data: unknown, status = 200) { return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } }); }

describe('Workspace boundaries', () => {
  it('renders OIDC sign-in without a development bypass', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond({ user: null, csrf_token: null, auth_mode: 'oidc' })));
    render(<App />);
    expect(await screen.findByRole('link', { name: /sign in with your organization/i })).toHaveAttribute('href', '/auth/login');
    expect(screen.queryByRole('textbox', { name: /email address/i })).not.toBeInTheDocument();
  });
  it('sends the CSRF token only on mutations and never as a URL parameter', async () => {
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(respond({ ok: true })));
    vi.stubGlobal('fetch', fetcher);
    await request('/api/v1/example', { method: 'POST', body: { title: 'Task' }, csrf: 'secret' });
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/example');
    expect(fetcher.mock.calls[0][1].headers['X-CSRF-Token']).toBe('secret');
    await request('/api/v1/example', { csrf: 'secret' });
    expect(fetcher.mock.calls[1][1].headers['X-CSRF-Token']).toBeUndefined();
  });
  it('keeps an edited task open on a version conflict', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond({ detail: 'This record changed. Refresh before trying again' }, 409)));
    const onClose = vi.fn();
    render(<TaskForm task={{ id: 'task', title: 'Ship release', description: '', status: 'todo', priority: 'medium', version: 1, assignee_id: null }} path="/tasks" csrf="csrf" members={[]} user={user} canEdit canDelete onClose={onClose} onSaved={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('This record changed');
    expect(onClose).not.toHaveBeenCalled();
  });
  it('renders untrusted task titles as text and disables viewer editing', () => {
    render(<TaskForm task={{ id: 'task', title: '<script>alert(1)</script>', description: '', status: 'todo', priority: 'medium', version: 1, assignee_id: null }} path="/tasks" csrf="csrf" members={[]} user={user} canEdit={false} canDelete={false} onClose={vi.fn()} onSaved={vi.fn()} />);
    expect(screen.getByRole('textbox', { name: 'Title' })).toHaveValue('<script>alert(1)</script>');
    expect(screen.getByRole('textbox', { name: 'Title' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Save changes' })).not.toBeInTheDocument();
  });
  it('does not simulate AI results when provider configuration is missing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond({ enabled: true, configured: false })));
    render(<AIPanel path="/projects/one" session={session} admin canEdit />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Generate a draft' })).toBeDisabled());
    expect(await screen.findByText(/provider is not connected yet/i)).toBeInTheDocument();
    expect(screen.queryByText('Your draft')).not.toBeInTheDocument();
  });
});
