const { defineConfig } = require('@playwright/test');
const compactChromium = require('@sparticuz/chromium');
module.exports = defineConfig({
  testDir: './tests/browser',
  testMatch: '**/*.spec.cjs',
  timeout: 90000,
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'evidence/browser-tests.json' }]],
  use: {
    baseURL: process.env.PW_BASE_URL || 'http://127.0.0.1:8000',
    headless: true,
    viewport: { width: 1440, height: 1100 },
    acceptDownloads: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    launchOptions: process.env.CHROMIUM_EXECUTABLE_PATH ? {
      executablePath: process.env.CHROMIUM_EXECUTABLE_PATH,
      // Lambda's single-process default exits when an isolated Playwright context closes.
      // Real multi-context browser tests need normal Chromium process isolation.
      args: compactChromium.args.filter(arg => arg !== '--single-process'),
      env: { ...process.env }
    } : {}
  },
  webServer: process.env.PW_EXTERNAL_SERVER ? undefined : {
    command: 'python -m http.server 8000 --bind 0.0.0.0 --directory build/site',
    url: 'http://127.0.0.1:8000/docs/index.html',
    timeout: 30000,
    reuseExistingServer: !process.env.CI
  }
});
