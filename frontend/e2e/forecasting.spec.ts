import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { illustrativePacket } from "../src/lib/forecasting";

async function recorded(page: Page) {
  const packet = structuredClone(illustrativePacket);
  packet.scenario.id = "recorded-test";
  packet.run.origin = "computed";
  packet.run.scenario_id = "recorded-test";
  packet.run.revisions = [0, 1, 2].map((revision) => ({
    revision,
    evidence_ids: packet.scenario.evidence
      .slice(0, revision + 1)
      .map((e) => e.id),
    forecasts: packet.run.forecasts,
    claim_count: revision + 1,
    node_count: 12,
  }));
  packet.run.forecasts[0].rank = 1;
  packet.future_evidence = [
    {
      id: "later-source",
      title: "Later evidence title",
      text: "A later recorded association, available only after reveal.",
      url: "https://example.org/later",
      available_at: "2022-03-01",
      publication_year: 2020,
    },
  ];
  packet.outcomes[0].evidence_ids = ["later-source"];
  await page.route("**/api/projects", (r) =>
    r.fulfill({ json: { projects: [] } }),
  );
  await page.route("**/api/forecasting/demo", (r) =>
    r.fulfill({ json: packet }),
  );
  await page.goto("/#forecast");
  await expect(
    page.getByText("Computed · historical graph", { exact: true }),
  ).toBeVisible();
}

test("recorded graph has stable positions, locked ranking, and an explicit evidence reveal", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await recorded(page);
  const before = await page
    .locator(".forecast-node")
    .evaluateAll((nodes) =>
      nodes.map((n) => [
        n.getAttribute("aria-label"),
        n.getAttribute("transform"),
      ]),
    );
  await page
    .getByRole("button", { name: "Connect evidence", exact: false })
    .click();
  const after = await page
    .locator(".forecast-node")
    .evaluateAll((nodes) =>
      nodes.map((n) => [
        n.getAttribute("aria-label"),
        n.getAttribute("transform"),
      ]),
    );
  expect(after).toEqual(before);
  await page
    .getByRole("button", { name: "Commit forecasts", exact: false })
    .click();
  const ranks = await page
    .locator(".forecast-recommendation strong")
    .allTextContents();
  await page.locator(".forecast-recommendation").first().click();
  await expect(
    page.getByText("Later evidence title", { exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Reveal evidence", exact: true })
    .click();
  await expect(
    page.getByText("Later evidence title", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Read later source" }),
  ).toHaveAttribute("href", "https://example.org/later");
  await page.getByRole("button", { name: "Clear selected entity" }).click();
  expect(
    await page.locator(".forecast-recommendation strong").allTextContents(),
  ).toEqual(ranks);
  await page.getByRole("button", { name: "Restart sequence" }).click();
  await expect(
    page.getByText("Later evidence title", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Graph revision 0", { exact: false }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("forecast has accessible controls in dark/light themes and a usable narrow layout", async ({
  page,
}) => {
  await recorded(page);
  for (const theme of ["dark", "light"]) {
    if (theme === "light")
      await page.getByRole("button", { name: "Switch to light theme" }).click();
    const result = await new AxeBuilder({ page })
      .include(".forecast-workspace")
      .analyze();
    expect(result.violations).toEqual([]);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("button", { name: "Continue", exact: true }),
  ).toBeVisible();
  const width = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
  }));
  expect(width.scroll).toBeLessThanOrEqual(width.viewport);
  expect(
    await page
      .locator(".forecast-graph-scene")
      .evaluate((el) => el.scrollWidth > el.clientWidth),
  ).toBe(true);
  await page.screenshot({
    path: "/tmp/dnhacks-forecast-mobile.png",
    fullPage: true,
  });
});

test("unavailable historical provider stays explicitly illustrative and never invents a scorecard", async ({
  page,
}) => {
  await page.route("**/api/projects", (r) =>
    r.fulfill({ json: { projects: [] } }),
  );
  await page.route("**/api/forecasting/demo", (r) =>
    r.fulfill({ json: { status: "preparing" } }),
  );
  await page.goto("/#forecast");
  await expect(
    page.getByText("Illustrative · no measured predictions", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Open the future", exact: false })
    .click();
  await expect(page.locator(".forecast-results")).toHaveCount(0);
  await page.getByLabel("Run provider").selectOption("illustrative");
  await expect(page.locator(".forecast-inspector-foot")).toContainText(
    "Illustrative walkthrough",
  );
});

test("recorded model memory changes representation and keeps unavailable metrics behind reveal", async ({
  page,
}) => {
  const { readFile } = await import("node:fs/promises");
  const read = async (path: string) =>
    JSON.parse(
      await readFile(new URL(`../../${path}`, import.meta.url), "utf8"),
    );
  const scenario = await read(
    "demo/forecasting/scenarios/civic-2018-2022/historical.json",
  );
  const comparison = await read(
    "demo/forecasting/reasoning/civic-model/comparison.json",
  );
  const evaluation = await read(
    "demo/forecasting/reasoning/civic-model/evaluation.json",
  );
  const suite = await read(
    "demo/forecasting/reasoning/civic-all-queries/evaluation.json",
  );
  const audit = await read(
    "demo/forecasting/reasoning/civic-all-queries/audit.json",
  );
  const study = {
    status: "ready",
    planned_queries: suite.coverage.planned_queries,
    saved_queries: suite.coverage.planned_queries,
    planned_candidates: suite.coverage.planned_candidates,
    requested_output_tokens: 6000,
    evaluation: suite,
    audit,
  };
  await page.route("**/api/projects", (r) =>
    r.fulfill({ json: { projects: [] } }),
  );
  await page.route("**/api/forecasting/demo", (r) =>
    r.fulfill({
      json: {
        ...illustrativePacket,
        scenario,
        run: {
          ...illustrativePacket.run,
          scenario_id: scenario.id,
          origin: "computed",
          forecasts: [],
          events: [],
        },
        outcomes: [],
        future_evidence: [],
      },
    }),
  );
  await page.route("**/api/forecasting/reasoning", (r) =>
    r.fulfill({ json: { status: "ready", comparison, evaluation, study } }),
  );
  await page.goto("/#forecast");
  const panel = page.locator("#forecast-model-memory");
  await expect(
    panel.getByText("Recorded model run", { exact: true }),
  ).toBeVisible();
  await expect(panel.getByText("Unmeasurable", { exact: true })).toHaveCount(0);
  await expect(panel.locator(".study-progress")).toContainText("22");
  await expect(panel.locator(".study-table")).toHaveCount(0);
  await expect(panel.locator(".study-coverage")).toHaveCount(0);
  const before = await panel
    .locator(".reasoning-map-node")
    .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("transform")));
  await panel
    .getByRole("button", { name: "Read & revise", exact: false })
    .click();
  expect(
    await panel
      .locator(".reasoning-map-node")
      .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("transform"))),
  ).toEqual(before);
  await expect(panel.locator(".reasoning-citations a").first()).toHaveAttribute(
    "href",
    /^https:\/\//,
  );
  await panel.getByRole("tab", { name: "Flat log", exact: false }).click();
  await expect(panel.getByLabel("Evidence in flat text memory")).toBeVisible();
  await panel.getByRole("tab", { name: "Static graph", exact: false }).click();
  await expect(
    panel.getByText("proposal in log", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Open the future", exact: false })
    .click();
  await expect(
    panel.getByText("Unmeasurable", { exact: true }).first(),
  ).toBeVisible();
  await panel
    .getByRole("tab", { name: "Evolving graph", exact: false })
    .click();
  await expect(panel.locator(".study-coverage")).toContainText("64/683");
  await expect(panel.locator(".study-table")).toContainText("8/22");
  await expect(panel.locator(".study-table-heading")).toContainText("1 query");
  await panel
    .getByText("Paired differences and uncertainty", { exact: true })
    .click();
  await expect(
    panel.getByText("Informative interval not estimated: 1 eligible query.", {
      exact: true,
    }),
  ).toHaveCount(3);
  for (const theme of ["dark", "light"]) {
    if (theme === "light")
      await page.getByRole("button", { name: "Switch to light theme" }).click();
    expect(
      (
        await new AxeBuilder({ page })
          .include("#forecast-model-memory")
          .analyze()
      ).violations,
    ).toEqual([]);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
});
