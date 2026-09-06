import { test, expect } from "@playwright/test";
import { fileURLToPath } from "node:url";
const directory = fileURLToPath(new URL("./captures/", import.meta.url));
test("inspect the cinematic map and available scene controls", async ({
  page,
}) => {
  const errors: string[] = [];
  const apiRequests: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/"))
      apiRequests.push(request.url());
  });
  await page.goto("/?demo=cinematic");
  await expect(
    page.getByRole("heading", {
      name: "Follow the question. See the possibility.",
    }),
  ).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: directory + "map-1920x1080.png" });
  const nodes = page.locator(".cine-node:not(:disabled)");
  const count = await nodes.count();
  for (let i = 0; i < count; i++) {
    const name = await nodes.nth(i).getAttribute("aria-label");
    await nodes.nth(i).click();
    await expect(page.locator("canvas")).toBeVisible();
    await page.getByRole("button", { name: "Reset", exact: true }).click();
    await expect(page.getByRole("slider", { name: "Scene time" })).toHaveValue(
      "0",
    );
    await page
      .getByRole("button", { name: "Interaction", exact: false })
      .click();
    await expect(page.getByRole("slider", { name: "Scene time" })).toHaveValue(
      "11",
    );
    await page.waitForTimeout(1200);
    const id = name?.includes("interface")
      ? "binder"
      : name?.includes("neighborhood")
        ? "tissue"
        : "spindle";
    await page.screenshot({ path: directory + `${id}-1920x1080.png` });
    await page.getByRole("button", { name: "Play", exact: true }).click();
    await expect
      .poll(async () =>
        Number(
          await page.getByRole("slider", { name: "Scene time" }).inputValue(),
        ),
      )
      .toBeGreaterThan(11);
    await page.getByRole("button", { name: "Pause", exact: true }).click();
    const paused = await page
      .getByRole("slider", { name: "Scene time" })
      .inputValue();
    await page.waitForTimeout(150);
    await expect(page.getByRole("slider", { name: "Scene time" })).toHaveValue(
      paused,
    );
    await page.getByRole("button", { name: "Investigation map" }).click();
    await expect(nodes.nth(i)).toBeFocused();
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: directory + "map-mobile.png" });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.emulateMedia({ reducedMotion: "reduce" });
  if (count) {
    await nodes.first().click();
    await expect(
      page.getByRole("button", { name: "Play", exact: true }),
    ).toBeVisible();
    await page.waitForTimeout(500);
    await expect(page.getByRole("slider", { name: "Scene time" })).toHaveValue(
      "0",
    );
    await page.screenshot({ path: directory + "scene-mobile.png" });
  }
  expect(errors).toEqual([]);
  expect(apiRequests).toEqual([]);
});
