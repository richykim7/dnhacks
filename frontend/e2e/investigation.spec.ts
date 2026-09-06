import { test, expect, type Page } from "@playwright/test";
import { mockApi, investigation } from "./fixtures";
import type { RuntimeEvent } from "../src/lib/runtime";

const root = investigation.root;
const child = `${root}~1`;
async function fixture(page: Page) {
  await mockApi(page);
  const now = Date.now() / 1000;
  const raw: [string, string, Record<string, unknown>, string?][] = [
    [
      root,
      "attempt.started",
      {
        branch_objective: "Explain neuronal excitability",
        original_question: investigation.goal,
      },
    ],
    [
      child,
      "attempt.started",
      {
        branch_objective: "Test sodium-channel mechanism",
        parent_run_id: root,
        original_question: investigation.goal,
      },
    ],
    [
      child,
      "intent",
      { intent: "Compare the observed response with independent controls." },
    ],
    [
      child,
      "experiment.queued",
      {
        title: "Independent control comparison",
        method: "Control comparison",
        status: "queued",
      },
      "exp-controls",
    ],
    [child, "experiment.started", { status: "running" }, "exp-controls"],
    [
      child,
      "experiment.finished",
      { status: "completed", result: { effect: 0.3, n_units: 24 } },
      "exp-controls",
    ],
    [
      child,
      "checkpoint.report",
      {
        report: {
          findings: [
            { claim: "The control comparison supports further investigation." },
          ],
        },
      },
    ],
    [
      child,
      "experiment.reviewed",
      { verification: "CANDIDATE", submission_id: "submission-controls" },
      "exp-controls",
    ],
    [
      child,
      "experiment.reviewed",
      { verification: "CANDIDATE", submission_id: "submission-controls" },
      "exp-controls",
    ],
    [
      child,
      "tool.started",
      { label: "Reviewing independent evidence", action: "search_papers" },
    ],
    [child, "heartbeat", {}],
  ];
  const events: RuntimeEvent[] = raw.map(
    ([run_id, kind, payload, experiment_id], index) => ({
      schema_version: 1,
      sequence: index + 1,
      event_id: `redesign-${index}`,
      run_id,
      kind,
      payload,
      experiment_id,
      recorded_at: now - (raw.length - index),
      attempt_id: "fixture",
      producer: "runner",
    }),
  );
  await page.route("**/api/investigations**", (route) =>
    route.fulfill({
      json: [{ ...investigation, runtime: true, updated_at: now }],
    }),
  );
  await page.route("**/api/runtime/**", (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/events"))
      return route.fulfill({
        json: {
          events: events.filter(
            (e) => e.sequence > Number(url.searchParams.get("after") || 0),
          ),
        },
      });
    if (url.pathname.endsWith("/stream"))
      return route.fulfill({
        contentType: "text/event-stream",
        body: ": connected\n\n",
      });
    return route.fulfill({
      status: 404,
      json: { error: "No artifact in this fixture" },
    });
  });
  let review: string | undefined;
  const decisions: unknown[] = [];
  await page.route("**/api/review/candidate**", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON();
      decisions.push(body);
      review = body.decision;
    }
    return route.fulfill({
      json: {
        project: "ion-channels",
        verification: "CANDIDATE",
        test: {
          hypothesis:
            "Sodium-channel response matches the independent controls",
          subject: "Sodium channel",
          object: "Neuronal response",
          method: "control_comparison",
          human_review: review,
          review_note: review ? "Independent controls reviewed." : undefined,
        },
        evidence: [],
        result: { effect: 0.3 },
      },
    });
  });
  return decisions;
}

test("full-canvas researcher morph, stable origin and candidate replay", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const decisions = await fixture(page);
  await page.goto("/");
  await expect(page.locator(".agent-node")).toHaveCount(2);
  const lead = page.locator(`.react-flow__node[data-id="${root}"]`);
  const branch = page.locator(`.react-flow__node[data-id="${child}"]`);
  await expect(page.locator(".summary-candidates")).toHaveText("1 candidates");
  await expect(branch.locator(".activity-dot.live")).toBeVisible();
  const top = await lead.boundingBox();
  const bottom = await branch.boundingBox();
  expect(bottom!.y).toBeGreaterThan(top!.y + top!.height);
  await page.getByRole("button", { name: "Collapse main navigation" }).click();
  await page
    .getByRole("button", { name: "Collapse investigation list" })
    .click();
  await expect(page.locator("#main-navigation")).toBeHidden();
  await expect(page.locator("#investigation-navigation")).toBeHidden();
  await page.screenshot({
    path: test.info().outputPath("investigation-dark.png"),
  });
  await page.waitForTimeout(900);
  const stage = await page.locator(".research-stage").boundingBox();
  await page.mouse.move(stage!.x + 45, stage!.y + 80);
  await page.mouse.down();
  await page.mouse.move(stage!.x + 75, stage!.y + 60, { steps: 5 });
  await page.mouse.up();
  const origin = await branch.boundingBox();
  const initialViewport = await page
    .locator(".react-flow__viewport")
    .getAttribute("style");
  await branch.locator(".candidate-badge").click();
  const detail = page.getByRole("article", {
    name: "Expanded researcher workspace",
  });
  await expect(detail).toBeVisible();
  await expect(page.locator(".detail-panel")).toHaveCount(0);
  const headings = await detail.locator("h3").allTextContents();
  expect(headings.findIndex((t) => t.includes("Experiments"))).toBeLessThan(
    headings.indexOf("Major steps"),
  );
  await expect(
    detail.getByRole("button", { name: "Review candidate", exact: true }),
  ).toBeVisible();
  await page.waitForTimeout(900);
  const expanded = await detail.boundingBox();
  await expect(page.locator(".agent-node")).toHaveCount(2);
  expect(await branch.boundingBox()).toEqual(origin);
  const canvas = await page.locator(".research-stage").boundingBox();
  expect(Math.abs(expanded!.x - canvas!.x)).toBeLessThan(2);
  expect(Math.abs(expanded!.y - canvas!.y)).toBeLessThan(2);
  expect(Math.abs(expanded!.width - canvas!.width)).toBeLessThan(2);
  expect(Math.abs(expanded!.height - canvas!.height)).toBeLessThan(2);
  await expect(detail.locator(".workspace-render")).toHaveCount(0);
  const information = await detail.locator(".node-research").boundingBox();
  const workspace = await detail.locator(".researcher-workspace").boundingBox();
  expect(Math.abs(information!.width - workspace!.width)).toBeLessThan(2);
  const viewport = page.locator(".react-flow__viewport");
  const before = await viewport.getAttribute("style");
  await page.waitForTimeout(5500); // One investigation poll must preserve the user's viewport.
  expect(await viewport.getAttribute("style")).toBe(before);
  await page.screenshot({ path: test.info().outputPath("node-dark.png") });
  await detail
    .getByRole("button", { name: "Review candidate", exact: true })
    .click();
  await expect(
    detail.getByRole("button", { name: "Accept", exact: true }),
  ).toBeDisabled();
  await detail
    .getByLabel("Decision note (required)")
    .fill("Independent controls reviewed.");
  await detail.getByRole("button", { name: "Accept", exact: true }).click();
  await expect(
    detail.getByText("Accepted by human review").first(),
  ).toBeVisible();
  expect(decisions).toEqual([
    expect.objectContaining({
      decision: "validated",
      note: "Independent controls reviewed.",
      experiment: "exp-controls",
    }),
  ]);
  await page.screenshot({
    path: test.info().outputPath("candidate-review.png"),
  });
  await page.keyboard.press("Escape");
  await expect(detail).toHaveCount(0);
  expect(await branch.boundingBox()).toEqual(origin);
  expect(
    await page.locator(".react-flow__viewport").getAttribute("style"),
  ).toBe(initialViewport);
  await expect(branch.locator(".agent-button")).toBeFocused();
  await page.locator(".summary-candidates").click();
  await expect(
    page.getByRole("heading", { name: "Candidate review", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".agent-node")).toHaveCount(2);
  await page.locator(".candidate-queue .experiment-row").click();
  await expect(detail).toBeVisible();
  await page.getByLabel("Activity playback position").fill("7");
  await expect(page.locator(".summary-candidates")).toHaveText("0 candidates");
  await expect(
    detail.getByRole("button", { name: "Review candidate", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Latest state", exact: true }).click();
  await expect(page.locator(".summary-candidates")).toHaveText("1 candidates");
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await page.screenshot({ path: test.info().outputPath("node-light.png") });
  await page.setViewportSize({ width: 430, height: 900 });
  await page.waitForTimeout(900);
  await page.screenshot({ path: test.info().outputPath("node-mobile.png") });
  expect(errors).toEqual([]);
});

// Opt-in read-only public projection capture; the snapshot never enters git.
test("public investigation snapshot screenshots", async ({ page }) => {
  test.skip(
    !process.env.S16_SNAPSHOT,
    "Set S16_SNAPSHOT to a read-only public projection snapshot",
  );
  const { readFileSync, writeFileSync } = await import("node:fs");
  const snapshot = JSON.parse(readFileSync(process.env.S16_SNAPSHOT!, "utf8"));
  await mockApi(page);
  await page.route("**/api/**", (route) => {
    const url = new URL(route.request().url());
    if (route.request().method() !== "GET")
      return route.fulfill({
        status: 403,
        json: { error: "Read-only snapshot" },
      });
    if (url.pathname === "/api/projects")
      return route.fulfill({ json: snapshot.projects });
    if (url.pathname === "/api/investigations")
      return route.fulfill({
        json: snapshot.investigations.filter(
          (i: { root: string }) => i.root === snapshot.root,
        ),
      });
    if (url.pathname.endsWith("/events"))
      return route.fulfill({
        json: {
          events: snapshot.events
            .filter(
              (e: RuntimeEvent) =>
                e.sequence > Number(url.searchParams.get("after") || 0),
            )
            .slice(0, 1000),
        },
      });
    if (url.pathname.endsWith("/stream"))
      return route.fulfill({
        contentType: "text/event-stream",
        body: ": read-only snapshot\n\n",
      });
    if (url.pathname === "/api/review/candidate") {
      const card =
        snapshot.cards[
          `${url.searchParams.get("run")}:${url.searchParams.get("experiment")}`
        ];
      return route.fulfill({
        status: card ? 200 : 404,
        json: card || { error: "Not in snapshot" },
      });
    }
    return route.fulfill({
      status: 404,
      json: { error: "Not in read-only snapshot" },
    });
  });
  await page.goto("/");
  await expect(page.locator(".agent-node")).toHaveCount(6);
  await page.getByRole("button", { name: "Collapse main navigation" }).click();
  await page
    .getByRole("button", { name: "Collapse investigation list" })
    .click();
  await page.waitForTimeout(1100);
  await page.screenshot({ path: test.info().outputPath("investigation.png") });
  await test.info().attach("computed-fonts", {
    body: JSON.stringify(
      await page.evaluate(() => ({
        fonts: [
          document.documentElement,
          document.body,
          document.querySelector(".app-shell")!,
          document.querySelector(".agent-node")!,
        ].map((e) => getComputedStyle(e).fontFamily),
        plexLoaded: document.fonts.check('14px "IBM Plex Sans Variable"'),
      })),
    ),
    contentType: "application/json",
  });
  writeFileSync(
    test.info().outputPath("fonts.json"),
    JSON.stringify(
      await page.evaluate(() => ({
        fonts: [
          document.documentElement,
          document.body,
          document.querySelector(".app-shell")!,
          document.querySelector(".agent-node")!,
        ].map((e) => getComputedStyle(e).fontFamily),
        plexLoaded: document.fonts.check('14px "IBM Plex Sans Variable"'),
      })),
    ),
  );
  await page.locator(".agent-node .agent-button").first().click();
  await expect(page.locator(".inline-research-detail")).toBeVisible();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: test.info().outputPath("node.png") });
  await page.locator("[data-workspace-close]").click();
  await expect(page.locator(".researcher-workspace-overlay")).toHaveCount(0);
  await page.locator(".agent-node .candidate-badge").first().click();
  const review = page
    .getByRole("button", { name: "Review candidate", exact: true })
    .first();
  await review.click();
  await expect(page.locator(".candidate-review-body h4").first()).toBeVisible();
  await page
    .getByLabel("Decision note (required)")
    .first()
    .scrollIntoViewIfNeeded();
  await expect(
    page.getByRole("button", { name: "Accept", exact: true }).first(),
  ).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("candidate.png") });
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await page.screenshot({ path: test.info().outputPath("node-light.png") });
  await page.setViewportSize({ width: 430, height: 900 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: test.info().outputPath("node-mobile.png") });
});
