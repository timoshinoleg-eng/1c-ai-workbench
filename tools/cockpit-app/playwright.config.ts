import { defineConfig, devices } from "@playwright/test";

// Playwright E2E config. The Tauri webview is Chromium-based, so we use the
// bundled chromium browser. In dev, Vite serves the SPA on http://localhost:1420
// and the Tauri shell is not required for the smoke flows below.
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL: "http://localhost:1420",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        channel: process.platform === "win32" ? "msedge" : undefined,
      },
    },
  ],
  webServer: {
    command: "npm run dev -- --mode test",
    url: "http://localhost:1420",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
