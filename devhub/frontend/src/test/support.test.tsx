import { afterEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SupportContact } from '../SupportContact';

afterEach(() => vi.unstubAllGlobals());

it('opens support by keyboard and provides the exact mailto without making requests', async () => {
  const fetcher = vi.fn();
  vi.stubGlobal('fetch', fetcher);
  render(<SupportContact />);
  const trigger = screen.getByRole('button', { name: 'Help & Support' });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(trigger).toHaveAttribute('aria-haspopup', 'dialog');
  trigger.focus();
  await userEvent.keyboard('{Enter}');
  const dialog = screen.getByRole('dialog', { name: 'Need help?' });
  expect(trigger).toHaveAttribute('aria-expanded', 'true');
  expect(within(dialog).getByText(/Contact the DevHub owner directly/)).toBeVisible();
  expect(within(dialog).getByRole('link', { name: 'Email Support' })).toHaveAttribute('href', 'mailto:keeponn87@gmail.com');
  expect(within(dialog).getByText(/Opens your email app/)).toHaveTextContent('keeponn87@gmail.com');
  await userEvent.click(within(dialog).getByRole('button', { name: 'Close dialog' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
  expect(trigger).toHaveAttribute('aria-expanded', 'false');
  expect(fetcher).not.toHaveBeenCalled();
});

it('handles native dialog cancellation and restores the trigger', async () => {
  render(<SupportContact />);
  const trigger = screen.getByRole('button', { name: 'Help & Support' });
  await userEvent.click(trigger);
  fireEvent(screen.getByRole('dialog'), new Event('cancel', { bubbles: true, cancelable: true }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});
