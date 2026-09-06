import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const path = process.env.KNOWLEDGE_REVIEW_SNAPSHOT;
const graph = path ? JSON.parse(readFileSync(path, "utf8")) : null;
test.skip(!graph, "Requires local read-only real corpus snapshot");
test("populated knowledge workspace visual review", async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/api/**", (route) => {
    const url = new URL(route.request().url());
    expect(route.request().method()).toBe("GET");
    if (url.pathname === "/api/projects")
      return route.fulfill({
        json: {
          projects: [
            {
              id: graph.source,
              name: "Pancreatic cancer",
              status: "ready",
              has_kg: true,
            },
          ],
        },
      });
    if (url.pathname === "/api/kg") {
      if (url.searchParams.has("claim"))
        return route.fulfill({
          json: graph._details[url.searchParams.get("claim")!],
        });
      const edges = graph.edges.slice(
        0,
        Number(url.searchParams.get("limit") || 160),
      );
      const ids = new Set(edges.flatMap((e: any) => [e.source, e.target]));
      return route.fulfill({
        json: {
          ...graph,
          edges,
          nodes: graph.nodes.filter((n: any) => ids.has(n.id)),
          shown: edges.length,
        },
      });
    }
    return route.fulfill({ json: [] });
  });
  await page.goto(`/?project=${graph.source}#knowledge`);
  await expect(page.locator(".kg-node").first()).toBeVisible();
  await page.waitForTimeout(800);
  await page.screenshot({
    path: test
      .info()
      .outputPath(
        process.env.KNOWLEDGE_BEFORE
          ? "knowledge-before.png"
          : "knowledge-after.png",
      ),
  });
  if (process.env.KNOWLEDGE_BEFORE) return;
  await expect(page.getByLabel("Relationship evidence")).toHaveCount(0);
  const canvas = await page.locator(".relationship-map").boundingBox();
  expect(canvas!.height).toBeGreaterThan(650);
  expect(canvas!.width).toBeGreaterThan(1500);
  await page.locator(".react-flow__node").first().click();
  await expect(page.getByLabel("Relationship evidence")).toBeVisible();
  await page.waitForTimeout(500);
  await page.screenshot({
    path: test.info().outputPath("knowledge-selection.png"),
  });
  await page.locator(".claim-result").first().click();
  await expect(page.locator(".source-evidence").first()).toBeVisible();
  await page.waitForTimeout(500);
  await page.screenshot({
    path: test.info().outputPath("knowledge-sources.png"),
  });
  const scroll = page.locator(".evidence-inspector .detail-scroll");
  await scroll.evaluate((e) => {
    e.scrollTop = e.scrollHeight;
  });
  expect(await scroll.evaluate((e) => e.scrollTop)).toBeGreaterThan(0);
  await page.keyboard.press("Escape");
  await expect(page.getByLabel("Relationship evidence")).toHaveCount(0);
  await page.waitForTimeout(600);
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await page.waitForTimeout(500);
  await page.screenshot({
    path: test.info().outputPath("knowledge-light.png"),
  });
  await page.getByLabel("Graph density").selectOption("800");
  await expect(page.locator(".react-flow__edge")).toHaveCount(800);
  await page.getByLabel("Graph density").selectOption("36");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(600);
  await page.screenshot({
    path: test.info().outputPath("knowledge-mobile.png"),
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
