import { test, expect } from '@playwright/test';

test('responsive themes, keyboard drawer, and protected profile drafts', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'This test explicitly visits all six viewport widths.');
  test.setTimeout(60000);
  const failures: string[] = [];
  page.on('pageerror', error => failures.push(error.message));
  page.on('response', response => { if (response.status() >= 500) failures.push(`HTTP ${response.status()}`); });
  await page.goto('/');
  await page.getByLabel('Your name', { exact: true }).fill('Experience Reviewer');
  await page.getByLabel('Email address', { exact: true }).fill(`ux-${Date.now()}@example.com`);
  await page.getByRole('button', { name: 'Enter workspace' }).click();
  await page.getByRole('button', { name: 'Create your organization' }).click();
  await page.getByRole('textbox', { name: 'Name', exact: true }).fill('UX review ' + Date.now());
  await page.getByRole('button', { name: 'Create organization', exact: true }).click();
  await expect(page.getByRole('button', { name: 'New project', exact: true })).toBeVisible();
  for (const width of [320, 375, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const theme of ['light', 'dark']) {
      await page.getByLabel('Appearance').selectOption(theme);
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
      await page.getByRole('heading', { name: /Welcome back/ }).click();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ animations: 'disabled', path: `../output/playwright/overview-${width}-${theme}.png`, fullPage: true });
      await page.getByRole('button', { name: 'Open profile settings', exact: true }).click();
      await expect(page.getByLabel('Display name', { exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ animations: 'disabled', path: `../output/playwright/settings-${width}-${theme}.png`, fullPage: true });
      await page.getByRole('button', { name: 'Back to workspace' }).click();
      if (width <= 700) await page.getByRole('button', { name: 'Open navigation' }).click();
      await page.getByRole('button', { name: 'Members', exact: true }).click();
      await expect(page.getByRole('heading', { name: 'Your people.' })).toBeVisible();
      await expect(page.locator('tbody tr')).toHaveCount(1);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ animations: 'disabled', path: `../output/playwright/members-${width}-${theme}.png`, fullPage: true });
      if (width <= 700) await page.getByRole('button', { name: 'Open navigation' }).click();
      await page.getByRole('button', { name: 'Overview', exact: true }).click();
    }
  }
  await page.setViewportSize({ width: 390, height: 844 });
  const open = page.getByRole('button', { name: 'Open navigation' });
  await open.click();
  await expect(page.getByRole('dialog', { name: 'Workspace navigation' })).toBeVisible();
  await expect(page.locator('.main-shell')).toHaveAttribute('inert', '');
  await expect(page.getByRole('button', { name: 'Close navigation', exact: true }).last()).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  expect(await page.evaluate(() => !!document.activeElement?.closest('#workspace-navigation'))).toBe(true);
  await page.keyboard.press('Escape');
  await expect(open).toBeFocused();
  await expect(page.locator('#workspace-navigation')).toHaveAttribute('inert', '');
  await page.getByRole('button', { name: 'Open profile settings', exact: true }).click();
  await page.getByLabel('Display name', { exact: true }).fill('Unsaved draft');
  page.once('dialog', dialog => dialog.dismiss());
  await page.getByRole('button', { name: 'Back to workspace' }).click();
  await expect(page.getByLabel('Display name', { exact: true })).toHaveValue('Unsaved draft');
  page.once('dialog', dialog => dialog.dismiss());
  await page.goBack();
  await expect(page.getByLabel('Display name', { exact: true })).toHaveValue('Unsaved draft');
  await expect(page).toHaveURL(/#settings\/profile$/);
  await page.getByRole('button', { name: 'Discard name changes' }).click();
  await page.getByRole('button', { name: 'Back to workspace' }).click();
  expect(failures).toEqual([]);
});
