import { defineConfig } from "@playwright/test";
import { join } from "node:path";
if (!process.env.E2E_RUN_DIR || !process.env.PLAYWRIGHT_BASE_URL) {
  throw new Error("Use npm run e2e -- <filters> for queued, isolated browser tests.");
}
export default defineConfig({
  testDir: "./e2e",
  outputDir: join(process.env.E2E_RUN_DIR, "artifacts"),
  fullyParallel: true,
  workers: 2,
  retries: 0,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL,
    viewport: { width: 1600, height: 1000 },
    trace: "retain-on-failure",
  },
  reporter: "list",
});
