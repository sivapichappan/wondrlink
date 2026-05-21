import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright config — accessibility tests only.
 *
 * Run against a deployed preview URL by default (set TEST_BASE_URL to a
 * preview URL in CI). For local dev, point at http://localhost:3000 or
 * the Vercel-dev server.
 *
 * Accessibility tests are under tests/accessibility.spec.ts and use
 * @axe-core/playwright. PRs are blocked on 'serious' or 'critical'
 * violations; 'moderate' and 'minor' land as warnings for triage.
 */

const baseURL = process.env.TEST_BASE_URL || 'http://localhost:3000';

export default defineConfig({
  testDir: './tests',
  testMatch: '**/accessibility.spec.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: {
    baseURL,
    headless: true,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
