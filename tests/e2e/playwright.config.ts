import { defineConfig, devices } from "@playwright/test";

/**
 * Starts the Next.js dev server for the duration of the test run unless
 * one is already running on :3000. Back-end calls are intercepted via
 * page.route() inside each spec — no uvicorn required.
 *
 * Run locally:
 *   cd tests/e2e
 *   npm install
 *   npx playwright install chromium
 *   npx playwright test
 */
export default defineConfig({
  testDir: ".",
  timeout: 30_000,
  // The webServer takes a few seconds to boot; the default expect timeout
  // bumps so the first navigation doesn't race against compile.
  expect: { timeout: 10_000 },
  fullyParallel: false,
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  webServer: {
    command: "npm run dev",
    cwd: "../../frontend",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
