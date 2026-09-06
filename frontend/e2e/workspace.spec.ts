import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mockApi, investigation, tree } from "./fixtures";
test("retired forecast route opens investigations without forecast requests", async ({
  page,
}) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await mockApi(page);
  await page.goto("/#forecast");
  const navigation = page.getByRole("navigation", { name: "Main navigation" });
  await expect(navigation.getByRole("link")).toHaveText([
    "Investigations",
    "Library",
    "Knowledge",
  ]);
  await expect(
    page.getByRole("heading", { name: investigation.goal, level: 1 }),
  ).toBeVisible();
  expect(requests.some((url) => url.includes("/api/forecasting/"))).toBe(false);
  await page.screenshot({ path: test.info().outputPath("dn-no-forecast.png") });
});

test("tree, live detail, recorded experiments and theme screenshots", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await mockApi(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: investigation.goal, level: 1 }),
  ).toBeVisible();
  await expect(page.locator(".agent-node")).toHaveCount(6);
  await page.waitForTimeout(500); // let the deliberate camera movement settle before inspecting geometry
  await page.screenshot({ path: test.info().outputPath("dn-tree-dark.png") });
  await page
    .getByRole("button", { name: "Inspect Variant-specific effects" })
    .click();
  await expect(
    page.getByText("Live update: robustness check has completed."),
  ).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("dn-detail-dark.png") });
  await page.getByRole("button", { name: "Close researcher detail" }).click();
  await expect(
    page.getByRole("tablist", { name: "Researcher detail" }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Inspect Sodium-channel excitability" })
    .click();
  await page
    .getByRole("tablist", { name: "Researcher detail" })
    .getByRole("tab", { name: "Experiments" })
    .click();
  await expect(page.getByText("0.42", { exact: true })).toBeVisible();
  await page.getByText("Analysis code", { exact: true }).click();
  await expect(
    page.getByText("result = fit_model(independent_samples)"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await page.waitForTimeout(400);
  await page.screenshot({
    path: test.info().outputPath("dn-detail-light.png"),
  });
  expect(errors).toEqual([]);
});
test("library edits, assistant proposals, uploads, build and launch requests", async ({
  page,
}) => {
  const writes = await mockApi(page);
  await page.goto("/?project=ion-channels#library");
  await page
    .getByRole("button", { name: "Manage collection", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Ion-channel mechanisms", exact: true }),
  ).toBeVisible();
  await page.getByText("Scope and relevance criteria", { exact: true }).click();
  await page
    .getByLabel("Relevance criteria")
    .fill("Only independent functional evidence");
  await page.getByRole("button", { name: "Save settings" }).click();
  expect(
    writes.some(
      (w) => w.body.spec?.theme === "Only independent functional evidence",
    ),
  ).toBeTruthy();
  await page
    .getByRole("tab", { name: "Research assistant", exact: true })
    .click();
  await page
    .getByLabel("Message the research assistant")
    .fill("Focus on functional assays");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await page.getByText("Proposed collection changes").click();
  await page.getByRole("button", { name: "Apply these settings" }).click();
  expect(writes.some((w) => w.path.endsWith("/chat/apply"))).toBeTruthy();
  await page.getByRole("tab", { name: "Collection settings" }).click();
  await page
    .getByRole("button", { name: "Build collection", exact: true })
    .click();
  await page.getByRole("button", { name: "Start build", exact: true }).click();
  expect(
    writes.some((w) => w.path.endsWith("/build") && !w.body.dry),
  ).toBeTruthy();
  await page
    .getByRole("button", { name: "New investigation", exact: true })
    .click();
  await page
    .getByLabel("Research question", { exact: true })
    .fill("Which mechanism explains this effect?");
  await page
    .getByRole("button", { name: "Start research", exact: true })
    .click();
  expect(
    writes.some(
      (w) => w.path.endsWith("/run") && w.body.goal.includes("Which mechanism"),
    ),
  ).toBeTruthy();
});
test("review controls are hidden and old knowledge links still work", async ({
  page,
}) => {
  const requests: string[] = [];
  page.on("request", (r) => requests.push(r.url()));
  await mockApi(page);
  for (const route of ["knowledge", "evidence", "review"]) {
    await page.goto("/?project=ion-channels#" + route);
    await expect(
      page.getByRole("heading", { name: "Explore knowledge" }),
    ).toBeVisible();
    await expect(
      page.getByRole("tab", { name: "Review findings" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Accept finding" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("link", { name: "Knowledge", exact: true }),
    ).toHaveAttribute("href", "#knowledge");
  }
  expect(requests.some((url) => url.includes("/api/review"))).toBe(false);
  await page.screenshot({ path: test.info().outputPath("dn-knowledge.png") });
});
test("playback conceals later evidence and mobile layout fits", async ({
  page,
}) => {
  await mockApi(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Play recorded activity" }).click();
  await page.getByRole("button", { name: "Pause playback" }).click();
  await expect(page.locator(".agent-node")).toHaveCount(1);
  await page.waitForTimeout(500);
  await page.screenshot({ path: test.info().outputPath("dn-mobile.png") });
  const width = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    width: innerWidth,
  }));
  expect(width.scroll).toBeLessThanOrEqual(width.width);
  await page.getByRole("button", { name: "Latest state" }).click();
  await expect(page.locator(".agent-node")).toHaveCount(6);
});
test("tree error is explicit, never silently empty", async ({ page }) => {
  await mockApi(page);
  await page.route("**/api/tree/**", (r) =>
    r.fulfill({ json: { ...tree, db_unreadable: "locked" } }),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText(
    "Experiment records are temporarily unavailable",
  );
});
test("keyboard navigation and accessible primary surfaces", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto("/");
  await expect(page.locator(".agent-node")).toHaveCount(6);
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    result.violations.map(
      (v) => `${v.id}: ${v.nodes.map((n) => n.target).join(",")}`,
    ),
  ).toEqual([]);
  await page.getByRole("tab", { name: "Search tree", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("tab", { name: "Activity", exact: true }),
  ).toHaveAttribute("data-state", "active");
});
test("empty real backend does not show test data", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Start with a research question" }),
  ).toBeVisible();
  await expect(page.locator(".agent-node")).toHaveCount(0);
});

test("library provenance, documents, history and accessible light theme", async ({
  page,
}) => {
  const writes = await mockApi(page);
  await page.goto("/?project=ion-channels#library");
  await page
    .getByRole("button", { name: "Manage collection", exact: true })
    .click();
  await expect(
    page.getByText(
      "The collection settings have changed since the last build. Rebuild to include those changes in future investigations.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await page.waitForTimeout(300);
  await page.screenshot({
    path: test.info().outputPath("dn-library-light.png"),
  });
  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    axe.violations.map(
      (v) => `${v.id}: ${v.nodes.map((n) => n.target).join(",")}`,
    ),
  ).toEqual([]);
  await page
    .getByRole("tab", { name: "Import documents", exact: true })
    .click();
  await page.locator("input[type=file]").setInputFiles({
    name: "research-note.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("Functional evidence notes"),
  });
  await expect
    .poll(() => writes.filter((w) => w.path.endsWith("/attachments")).length)
    .toBe(1);
  await page.getByRole("tab", { name: "Builds & runs" }).click();
  await page.getByRole("button", { name: "Collection build" }).click();
  await expect(page.getByText("Finding matching papers")).toBeVisible();
  await page.getByRole("button", { name: "Stop job" }).click();
  expect(writes.some((w) => w.path.endsWith("/cancel"))).toBeTruthy();
});
test("project creation and missing-project scope do not leak a prior graph", async ({
  page,
}) => {
  const writes = await mockApi(page);
  await page.goto("/#library");
  await page
    .getByRole("button", { name: "New collection", exact: true })
    .click();
  await page
    .getByLabel("Collection name", { exact: true })
    .fill("New test collection");
  await page
    .getByLabel("What does this collection cover?")
    .fill("Independent functional studies");
  await page
    .getByRole("button", { name: "Create collection", exact: true })
    .click();
  expect(writes.find((w) => w.path === "/api/projects")?.body.name).toBe(
    "New test collection",
  );
  await page.goto("/?project=other#investigations");
  await expect(page.locator(".agent-node")).toHaveCount(0);
  await expect(
    page.getByText(
      "This collection is unavailable. Select another collection or All collections.",
    ),
  ).toBeVisible();
});
test("standalone structures route is retired", async ({ page }) => {
  await mockApi(page);
  await page.goto("/#structures");
  await expect(
    page.getByRole("link", { name: "Structures", exact: true }),
  ).toHaveCount(0);
  await expect(page.locator(".agent-node")).toHaveCount(6);
});
