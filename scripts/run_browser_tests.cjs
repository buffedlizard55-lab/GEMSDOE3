#!/usr/bin/env node
// Pinned npm-distributed headless Chromium keeps browser checks usable when browser CDNs
// are unavailable. No runtime site dependency. No system installation or credentials.
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const { spawnSync } = require('node:child_process');
const chromium = require('@sparticuz/chromium');
(async () => {
  if (process.platform !== 'linux' || process.arch !== 'x64') {
    throw new Error('This offline-friendly runner supports Linux x64. Else install Playwright Chromium and use npx playwright test.');
  }
  const directory = path.resolve('node_modules/.chromium-libs');
  fs.mkdirSync(directory, { recursive: true });
  const archive = path.resolve('node_modules/@sparticuz/chromium/bin/al2023.tar.br');
  const extracted = spawnSync('tar', ['-xf', '-', '-C', directory], { input: zlib.brotliDecompressSync(fs.readFileSync(archive)) });
  if (extracted.status !== 0) throw new Error('Could not extract the pinned Chromium shared libraries');
  const binary = await chromium.executablePath();
  const env = { ...process.env, CHROMIUM_EXECUTABLE_PATH: binary,
    LD_LIBRARY_PATH: path.join(directory, 'lib') + ':' + (process.env.LD_LIBRARY_PATH || '') };
  const run = spawnSync(process.execPath, [require.resolve('@playwright/test/cli'), 'test', ...process.argv.slice(2)], { env, stdio: 'inherit' });
  if (run.error) throw run.error;
  process.exitCode = run.status === null ? 1 : run.status;
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
