import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  workers: 2,
  retries: 0,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5174",
    viewport: { width: 1600, height: 1000 },
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run dev",
    url: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5174",
    reuseExistingServer: true,
  },
  reporter: "list",
});
