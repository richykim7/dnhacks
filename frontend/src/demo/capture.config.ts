import { defineConfig } from "@playwright/test";
if (!process.env.E2E_RUN_DIR || !process.env.PLAYWRIGHT_BASE_URL)
  throw new Error("Use npm run e2e with this configuration.");
export default defineConfig({
  testDir: ".",
  testMatch: "capture.spec.ts",
  testIgnore: "**/scenes/**",
  workers: 1,
  timeout: 120000,
  outputDir: process.env.E2E_RUN_DIR + "/cinematic",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL,
    viewport: { width: 1920, height: 1080 },
    launchOptions: {
      args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
    },
  },
});
