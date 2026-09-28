import { test, expect } from '@playwright/test';

test('support respects themes, keyboard focus and unsaved workspace context', async ({ page }, testInfo) => {
  const failures: string[] = [];
  page.on('pageerror', error => failures.push(error.message));
  if (testInfo.project.name === 'mobile') await page.setViewportSize({ width: 320, height: 800 });
  await page.goto('/');
  await page.getByLabel('Your name', { exact: true }).fill('Support Tester');
  await page.getByLabel('Email address', { exact: true }).fill(`support-${Date.now()}@example.com`);
  await page.getByRole('button', { name: 'Enter workspace' }).click();
  await page.getByRole('button', { name: 'Open profile settings', exact: true }).click();
  await page.getByLabel('Display name', { exact: true }).fill('Unsaved profile draft');
  const originalURL = page.url();
  for (const theme of ['light', 'dark']) {
    await page.getByLabel('Appearance').selectOption(theme);
    if (testInfo.project.name === 'mobile') await page.getByRole('button', { name: 'Open navigation' }).click();
    const trigger = page.getByRole('button', { name: 'Help & Support' });
    await trigger.focus();
    await page.keyboard.press('Enter');
    const dialog = page.getByRole('dialog', { name: 'Need help?' });
    await expect(dialog).toBeVisible();
    const link = dialog.getByRole('link', { name: 'Email Support' });
    await expect(link).toHaveAttribute('href', 'mailto:keeponn87@gmail.com');
    // Check native focus wrapping without launching an external email application.
    await link.focus();
    await page.keyboard.press('Tab');
    await expect(dialog.getByRole('button', { name: 'Close dialog' })).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(link).toBeFocused();
    const box = await dialog.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(page.viewportSize()!.width);
    await page.screenshot({ animations: 'disabled', path: `../output/playwright/support-${testInfo.project.name}-${theme}.png` });
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(trigger).toBeFocused();
    if (testInfo.project.name === 'mobile') {
      await expect(page.getByRole('dialog', { name: 'Workspace navigation' })).toBeVisible();
      await page.keyboard.press('Escape');
    }
    await expect(page.getByLabel('Display name', { exact: true })).toHaveValue('Unsaved profile draft');
    expect(page.url()).toBe(originalURL);
  }
  expect(failures).toEqual([]);
});
