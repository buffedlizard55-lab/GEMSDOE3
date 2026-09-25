const { test, expect } = require('@playwright/test');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

test('home makes the real file obvious and all navigation works', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.goto('/docs/index.html');
  await expect(page.locator('#portfolio .portfolio-download').first()).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Previous candidate: Riftline.' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Build & download/ })).toBeEnabled();
  await expect(page.locator('[data-leader-score]')).toHaveText(/0\.\d{4}/);
  await page.getByRole('navigation').getByRole('link', { name: 'Executive summary' }).click();
  await expect(page.locator('#steps')).toContainText('Submit in six steps');
  await expect(page.locator('#submission-note')).toHaveValue(/Riftline/);
  await page.getByRole('navigation').getByRole('link', { name: 'Experiments' }).click();
  await expect(page.locator('.selected-row')).toHaveCount(1);
  await expect(page.locator('main')).toContainText('not a hidden-label or leaderboard score');
  expect(errors).toEqual([]);
});

test('actual browser builds and downloads a TIFF that independently validates', async ({ page }, testInfo) => {
  await page.goto('/docs/index.html');
  const button = page.getByRole('button', { name: /Build & download/ });
  await expect(button).toBeEnabled();
  const pending = page.waitForEvent('download', { timeout: 90000 });
  await button.click();
  const download = await pending;
  expect(download.suggestedFilename()).toMatch(/^riftline-.*\.tif$/);
  const output = testInfo.outputPath(download.suggestedFilename());
  await download.saveAs(output);
  expect(fs.statSync(output).size).toBeGreaterThan(100000);
  const python = process.env.PYTHON || path.resolve('.venv/bin/python');
  const checked = spawnSync(python, ['scripts/validate_submission.py', output, '--template', 'legacy/data/bridge/example_submission.tif'], { encoding: 'utf8' });
  expect(checked.status, checked.stdout + checked.stderr).toBe(0);
  await expect(page.locator('.build-status')).toContainText('not submitted to DrivenData');
  await expect(page.locator('#submission-note')).toHaveValue(/\| tif [a-f0-9]{10}/);
  await page.locator('#submission .file-details summary').click();
  await expect(page.getByRole('button', { name: 'Download this build’s receipt' })).toBeVisible();
});

test('corrupt payload causes a visible failure and no download', async ({ page }) => {
  let downloads = 0;
  page.on('download', () => downloads++);
  await page.route('**/data/field.f32.zlib', async route => {
    const body = fs.readFileSync('docs/data/field.f32.zlib');
    body[body.length - 1] ^= 1;
    await route.fulfill({ status: 200, contentType: 'application/octet-stream', body });
  });
  await page.goto('/docs/index.html');
  await page.getByRole('button', { name: /Build & download/ }).click();
  await expect(page.locator('.build-status')).toContainText('SHA-256 mismatch');
  await expect(page.locator('.build-status')).toHaveClass(/error/);
  expect(downloads).toBe(0);
});

test('source search and type filtering are functional', async ({ page }) => {
  await page.goto('/docs/sources.html');
  await page.getByRole('button', { name: 'Scientific papers', exact: true }).click();
  await expect(page.locator('#source-table tbody tr:visible')).toHaveCount(4);
  await page.getByRole('searchbox').fill('Hermant');
  await expect(page.locator('#source-table tbody tr:visible')).toHaveCount(1);
  await expect(page.locator('#source-count')).toHaveText('1 source');
  await page.getByRole('searchbox').fill('no-source-with-this-name');
  await expect(page.locator('#source-count')).toHaveText('0 sources');
  await page.getByRole('searchbox').fill('');
  await page.getByRole('button', { name: 'All', exact: true }).click();
  const register = JSON.parse(fs.readFileSync('research/sources.json', 'utf8'));
  await expect(page.locator('#source-table tbody tr:visible')).toHaveCount(register.sources.length);
});

test('stale evidence never looks like a live successful feed', async ({ page }) => {
  await page.route('**/data/feed.json', async route => {
    const feed = JSON.parse(fs.readFileSync('docs/data/feed.json', 'utf8'));
    feed.sources.forEach(source => { source.last_verified_at = '2020-01-01T00:00:00Z'; });
    feed.leaderboard.verified_at = '2020-01-01T00:00:00Z';
    await route.fulfill({ json: feed });
  });
  await page.goto('/docs/index.html');
  await expect(page.locator('#feed-status')).toContainText('need review');
  await expect(page.locator('[data-board-time]')).toContainText('STALE');
});

test('missing feed is explicit and direct file remains available', async ({ page }) => {
  await page.route('**/data/feed.json', route => route.abort());
  await page.goto('/docs/index.html');
  await expect(page.locator('#feed-status')).toContainText('Feed unavailable');
  const link = page.getByRole('link', { name: 'Direct validated TIF', exact: true });
  const response = await page.request.get('/docs/' + await link.getAttribute('href'));
  expect(response.status()).toBe(200);
});

test('mobile layout fits the viewport and navigation remains accessible', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/docs/index.html');
  await expect(page.getByRole('button', { name: /Build & download/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.screenshot({ path: 'test-results/mobile-home.png', fullPage: true });
  await page.getByRole('navigation').getByRole('link', { name: 'Data & sources' }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test('desktop screenshot and same-origin runtime assets', async ({ page }) => {
  const requests = [];
  page.on('request', request => requests.push(request.url()));
  await page.goto('/docs/index.html');
  await expect(page.getByRole('button', { name: /Build & download/ })).toBeEnabled();
  await page.screenshot({ path: 'test-results/desktop-home.png', fullPage: true });
  const origin = new URL(page.url()).origin;
  expect(requests.filter(url => !url.startsWith(origin + '/') && !url.startsWith('data:'))).toEqual([]);
});

test('mixed page and manifest versions disable generation', async ({ page }) => {
  await page.route('**/data/submission.json', async route => {
    const meta = JSON.parse(fs.readFileSync('docs/data/submission.json', 'utf8'));
    meta.artifact.sha256 = '0'.repeat(64);
    await route.fulfill({ json: meta });
  });
  await page.goto('/docs/index.html');
  await expect(page.locator('.build-status')).toContainText('Page and artifact versions differ');
  await expect(page.getByRole('button', { name: /Build & download/ })).toBeDisabled();
});

test('browser receipt and subsequent direct download retain the correct identities', async ({ page }) => {
  await page.goto('/docs/index.html');
  let pending = page.waitForEvent('download');
  await page.getByRole('button', { name: /Build & download/ }).click();
  const built = await pending;
  await page.locator('#submission .file-details summary').click();
  pending = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download this build’s receipt' }).click();
  const receiptDownload = await pending;
  const receipt = JSON.parse(fs.readFileSync(await receiptDownload.path(), 'utf8'));
  expect(receipt.filename).toBe(built.suggestedFilename());
  expect(receipt.sha256).toMatch(/^[a-f0-9]{64}$/);
  await expect(page.locator('#submission .file-details .hash')).toContainText(receipt.sha256);
  expect(new Date(receipt.built_at).getTime()).toBeLessThanOrEqual(Date.now());
  pending = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Direct validated TIF', exact: true }).click();
  const direct = await pending;
  const meta = JSON.parse(fs.readFileSync('docs/data/submission.json', 'utf8'));
  expect(direct.suggestedFilename()).toBe(meta.artifact.filename);
  await expect(page.locator('#submission-note')).toHaveValue(meta.note);
  await expect(page.locator('#submission .file-details .hash')).toContainText(meta.artifact.sha256);
});

test('without JavaScript the direct artifact and instructions still work', async ({ browser, baseURL }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(baseURL + '/docs/executive_summary.html');
  await expect(page.locator('.noscript')).toContainText('JavaScript is off');
  await expect(page.getByRole('link', { name: 'Direct validated TIF', exact: true })).toBeVisible();
  await expect(page.locator('#steps')).toContainText('File to submit');
  await context.close();
});

test('portfolio: every direct download is the exact published file and each Note copies', async ({ page, context }, testInfo) => {
  const manifest = JSON.parse(fs.readFileSync('docs/data/portfolio.json', 'utf8'));
  const crypto = require('node:crypto');
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  for (const name of ['index.html', 'executive_summary.html']) {
    await page.goto('/docs/' + name);
    await expect(page.locator('#portfolio .portfolio-card')).toHaveCount(manifest.items.length);
    await expect(page.locator('#portfolio .portfolio-card').first()).toContainText('SUBMIT FIRST');
  }
  await page.goto('/docs/index.html');
  const python = process.env.PYTHON || path.resolve('.venv/bin/python');
  for (const [i, item] of manifest.items.entries()) {
    const pending = page.waitForEvent('download');
    await page.locator('#portfolio a.portfolio-download').nth(i).click();
    const download = await pending;
    expect(download.suggestedFilename()).toBe(item.filename);
    const output = testInfo.outputPath(item.filename);
    await download.saveAs(output);
    expect(crypto.createHash('sha256').update(fs.readFileSync(output)).digest('hex')).toBe(item.sha256);
    const checked = spawnSync(python, ['scripts/validate_submission.py', output, '--template', 'legacy/data/bridge/example_submission.tif'], { encoding: 'utf8' });
    expect(checked.status, checked.stdout + checked.stderr).toBe(0);
    await page.locator(`button.copy-portfolio-note[data-target="note-${item.variant}"]`).click();
    await expect(page.locator('#portfolio-status')).toContainText('Note copied');
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(item.note);
  }
  expect(errors).toEqual([]);
});

test('building the Riftline file never rewrites portfolio file identities', async ({ page }) => {
  const manifest = JSON.parse(fs.readFileSync('docs/data/portfolio.json', 'utf8'));
  await page.goto('/docs/index.html');
  const pending = page.waitForEvent('download', { timeout: 90000 });
  await page.getByRole('button', { name: /Build & download/ }).click();
  await pending;
  for (const [i, item] of manifest.items.entries()) {
    const card = page.locator('#portfolio .portfolio-card').nth(i);
    await expect(card.locator('.filename')).toHaveText(item.filename);
    await expect(card.locator('.hash')).toContainText(item.sha256);
  }
});
