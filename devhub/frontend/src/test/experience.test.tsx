import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PasswordField } from '../ui';
import { ThemeControl } from '../ThemeControl';
import { allowNavigation, useUnsavedChanges } from '../useUnsavedChanges';

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
it('reveals a password without changing its value or submitting its form', async () => {
  const submit = vi.fn();
  render(<form onSubmit={submit}><PasswordField label="New password" name="password" hint="Use 8–128 characters" defaultValue="Synthetic1!" /></form>);
  const input = screen.getByLabelText('New password');
  expect(input).toHaveAttribute('type', 'password');
  expect(input).toHaveAccessibleDescription('Use 8–128 characters');
  await userEvent.click(screen.getByRole('button', { name: 'Show new password' }));
  expect(input).toHaveAttribute('type', 'text');
  expect(input).toHaveValue('Synthetic1!');
  await userEvent.click(screen.getByRole('button', { name: 'Hide new password' }));
  expect(input).toHaveAttribute('type', 'password');
  expect(submit).not.toHaveBeenCalled();
});
it('allows cancelling draft navigation and removes the guard once clean', () => {
  function Draft({ dirty }: { dirty: boolean }) { useUnsavedChanges(dirty); return null; }
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
  const view = render(<Draft dirty />);
  expect(allowNavigation()).toBe(false);
  const unload = new Event('beforeunload', { cancelable: true });
  window.dispatchEvent(unload);
  expect(unload.defaultPrevented).toBe(true);
  confirm.mockReturnValue(true);
  expect(allowNavigation()).toBe(true);
  view.rerender(<Draft dirty={false} />);
  confirm.mockClear();
  expect(allowNavigation()).toBe(true);
  expect(confirm).not.toHaveBeenCalled();
});
it('switches appearance and remains usable when preference storage is blocked', async () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw Error('blocked'); });
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw Error('blocked'); });
  render(<ThemeControl />);
  await userEvent.selectOptions(screen.getByLabelText('Appearance'), 'dark');
  expect(document.documentElement.dataset.theme).toBe('dark');
  await userEvent.selectOptions(screen.getByLabelText('Appearance'), 'light');
  expect(document.documentElement.dataset.theme).toBe('light');
});
