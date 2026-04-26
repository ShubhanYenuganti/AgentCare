import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for AgentCare dashboard E2E tests.
 * Tests run against the real FastAPI backend (started via globalSetup).
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false, // share the same backend instance
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,

  use: {
    baseURL: process.env.DASHBOARD_URL || "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  // Start the FastAPI backend and the Vite dev server before running tests
  webServer: [
    {
      command: "python -m uvicorn api.main:app --host 0.0.0.0 --port 8000",
      port: 8000,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      cwd: "..",
      env: {
        SQLITE_DB_PATH: process.env.E2E_DB_PATH || "data/e2e_test.db",
        EXECUTOR_INTERNAL_URL: "",
      },
    },
    {
      command: "npm run dev",
      port: 5173,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      cwd: "..",
      env: {
        VITE_API_URL: "http://localhost:8000",
      },
    },
  ],
});
