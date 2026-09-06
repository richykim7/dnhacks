import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";
const directory = fileURLToPath(new URL(".", import.meta.url));
test("capture deterministic spindle tableaux", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  for (const time of [0, 8, 14, 18]) {
    await page.goto(`/src/demo/scenes/spindle/preview.html?time=${time}`);
    await expect(page.locator("canvas")).toBeVisible();
    await page.waitForTimeout(1800);
    await page.screenshot({ path: `${directory}still-${time}.png` });
  }
  expect(errors).toEqual([]);
});

test("record the illustrative sequence", async ({ browser, baseURL }) => {
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: {
      dir: directory + ".video-tmp",
      size: { width: 1920, height: 1080 },
    },
  });
  const page = await context.newPage();
  await page.goto(`${baseURL}/src/demo/scenes/spindle/preview.html?play`);
  await page.waitForTimeout(19500);
  await context.close();
  await page.video()!.saveAs(directory + "spindle.webm");
  await page.video()!.delete();
});
