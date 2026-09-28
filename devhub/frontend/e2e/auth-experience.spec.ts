import { test, expect } from '@playwright/test';

// UI-only provider/session fixtures. Real OAuth and email are not called here.
test('authentication appearance, password reveal, recovery and invalid reset feedback', async ({ page }, testInfo) => {
  await page.route('**/auth/session', route => route.fulfill({ json: { user: null, csrf_token: null, auth_mode: 'configured', providers: ['google', 'github'], email_enabled: true, email_delivery: true } }));
  await page.route('**/auth/forgot-password', route => route.fulfill({ status: 202, json: { detail: 'If this address is eligible, an email will arrive shortly. Check your inbox and spam folder.' } }));
  await page.route('**/auth/reset-password', route => route.fulfill({ status: 400, json: { detail: 'This link is invalid, expired, or already used.' } }));
  await page.goto('/');
  for (const width of testInfo.project.name === 'mobile' ? [320, 375, 390] : [768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const theme of ['light', 'dark']) {
      await page.getByLabel('Appearance').selectOption(theme);
      await page.getByRole('heading', { name: 'Welcome to DevHub' }).click();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ animations: 'disabled', path: `../output/playwright/login-${width}-${theme}.png`, fullPage: true });
    }
  }
  await expect(page.getByRole('link', { name: 'Continue with Google' })).toHaveAttribute('href', '/auth/google/login');
  await expect(page.getByRole('link', { name: 'Continue with GitHub' })).toHaveAttribute('href', '/auth/login');
  await page.getByRole('button', { name: 'Create account' }).click();
  await page.getByLabel('Password', { exact: true }).fill('Synthetic1!');
  await page.getByRole('button', { name: 'Show password', exact: true }).click();
  await expect(page.getByLabel('Password', { exact: true })).toHaveAttribute('type', 'text');
  await page.getByRole('button', { name: 'Hide password', exact: true }).click();
  await expect(page.getByLabel('Password', { exact: true })).toHaveAttribute('type', 'password');
  await page.getByRole('button', { name: 'Forgot password?' }).click();
  await page.getByLabel('Email', { exact: true }).fill('unknown@example.com');
  await page.getByRole('button', { name: 'Send reset link' }).click();
  await expect(page.getByRole('status')).toContainText('If this address is eligible');
  await page.goto('/#reset-password=' + 'x'.repeat(43));
  await page.getByLabel('Password', { exact: true }).fill('Synthetic1!');
  await page.getByLabel('Confirm password', { exact: true }).fill('Synthetic1!');
  await page.getByRole('button', { name: 'Reset password' }).click();
  await expect(page.getByRole('alert')).toContainText('invalid, expired, or already used');
  await expect(page.getByLabel('Password', { exact: true })).toHaveAccessibleDescription('This link is invalid, expired, or already used.');
});
