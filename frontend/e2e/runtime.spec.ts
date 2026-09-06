import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { mockApi, investigation } from "./fixtures";
import type { RuntimeEvent } from "../src/lib/runtime";

// Synthetic execution fixture; molecular coordinates are experimental reference 1CRN from RCSB.
// https://files.rcsb.org/download/1CRN.pdb — no generated predictions or measured runtime claims.
const pdb = readFileSync(new URL("./1crn.pdb", import.meta.url), "utf8");
const root = investigation.root;
const child = `${root}~1`;
function history(): RuntimeEvent[] {
  const raw: any[] = [
    [
      root,
      "attempt.started",
      {
        original_question: investigation.goal,
        branch_objective: "Investigate channel structure",
        lifecycle: "running",
      },
    ],
    [
      child,
      "attempt.started",
      {
        original_question: investigation.goal,
        branch_objective: "Inspect the experimental fold",
        parent_run_id: root,
      },
    ],
    [
      child,
      "intent",
      {
        intent:
          "Inspect the reference fold before choosing a structural experiment.",
      },
    ],
    [
      child,
      "tool.started",
      {
        phase: "tool",
        action: "run_experiments",
        label: "Running structural experiment",
      },
    ],
    [
      child,
      "experiment.queued",
      {
        title: "Reference fold inspection",
        status: "queued",
        method: "Structure inspection",
      },
      "exp1",
    ],
    [child, "experiment.started", { status: "running" }, "exp1"],
    [
      child,
      "experiment.output",
      { text: "Reading atomic coordinates…", stream: "stdout", offset: 0 },
      "exp1",
    ],
    [
      child,
      "experiment.finished",
      { status: "completed", exploratory: true },
      "exp1",
    ],
    [
      child,
      "artifact",
      {
        artifact_id: "1crn",
        name: "1CRN.pdb",
        kind: "molecular_structure",
        format: "pdb",
        status: "available",
        atom_count: 327,
        storage_key: "molecule",
        provenance: {
          category: "experimental_reference",
          source_ids: ["PDB:1CRN"],
          tool: "RCSB",
          tool_version: "reference",
        },
      },
      "exp1",
    ],
    [child, "tool.ended", {}],
    [child, "heartbeat", {}],
  ];
  return raw.map(([run_id, kind, payload, experiment_id], i) => ({
    schema_version: 1,
    sequence: i + 1,
    run_id,
    attempt_id: "fixture",
    event_id: `fixture-${i}`,
    kind,
    payload,
    experiment_id,
    producer: kind === "intent" ? "agent" : "runner",
    recorded_at: Date.now() / 1000,
  }));
}
async function fixture(page: Page, invalid = false) {
  await mockApi(page);
  let terminalReads = 0,
    artifactReads = 0;
  const events = history();
  await page.route("**/api/investigations**", (r) =>
    r.fulfill({ json: [{ ...investigation, runtime: true }] }),
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
    if (url.pathname.endsWith("/terminal")) {
      terminalReads++;
      return route.fulfill({
        json: {
          available: false,
          reason: "Terminal unavailable for this agent.",
        },
      });
    }
    if (url.pathname.includes("/blob/")) {
      artifactReads++;
      return route.fulfill({
        contentType: "text/plain",
        body: invalid ? "not a structure" : pdb,
      });
    }
    return route.fulfill({ status: 404, json: { error: "Not in fixture" } });
  });
  return {
    terminalReads: () => terminalReads,
    artifactReads: () => artifactReads,
  };
}
test("node execution, opt-in terminal, inline real geometry and replay boundary", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const reads = await fixture(page);
  await page.goto("/");
  await expect(page.locator(".agent-node")).toHaveCount(2);
  expect(reads.artifactReads()).toBe(0);
  await page
    .getByRole("button", { name: "Inspect Inspect the experimental fold" })
    .click();
  await expect(page.locator(".current-work")).toContainText(
    "Inspect the reference fold",
  );
  expect(reads.terminalReads()).toBe(0);
  await page.getByRole("button", { name: "Show terminal" }).click();
  await expect(
    page.getByText("Terminal unavailable for this agent."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Hide terminal" }).click();
  await page
    .getByRole("tablist", { name: "Researcher detail" })
    .getByRole("tab", { name: "Experiments" })
    .click();
  await expect(page.locator(".artifact-canvas canvas")).toBeVisible({
    timeout: 20000,
  });
  await expect(page.getByText("Preparing experiment structure")).toHaveCount(0);
  await page.waitForTimeout(700);
  await page.screenshot({ path: "/tmp/dn-runtime-molecule-dark.png" });
  await page.getByRole("tab", { name: "Surface", exact: true }).click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: "/tmp/dn-runtime-surface.png" });
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await page.getByRole("tab", { name: "Ribbon", exact: true }).click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: "/tmp/dn-runtime-molecule-light.png" });
  await page.getByLabel("Activity playback position").fill("7");
  await expect(page.locator(".artifact-viewer")).toHaveCount(0);
  await expect(page.locator(".experiment-detail")).toContainText("Running");
  await expect(
    page.getByRole("button", { name: "Show terminal" }),
  ).toBeDisabled();
  await page.getByLabel("Activity playback position").fill("1");
  await expect(page.locator(".agent-node")).toHaveCount(1);
  await expect(page.locator(".detail-panel")).toHaveCount(0);
  expect(errors).toEqual([]);
});
test("malformed experiment structure is an explicit error", async ({
  page,
}) => {
  await fixture(page, true);
  await page.goto("/");
  await page
    .getByRole("button", { name: "Inspect Inspect the experimental fold" })
    .click();
  await page
    .getByRole("tablist", { name: "Researcher detail" })
    .getByRole("tab", { name: "Experiments" })
    .click();
  await expect(page.getByRole("alert")).toContainText("No atoms could be read");
});
test("experiment list opens its owning experiment and navigation preserves investigation", async ({
  page,
}) => {
  await fixture(page);
  await page.goto(`/#investigations/${root}`);
  await page
    .getByRole("tablist", { name: "Investigation view" })
    .getByRole("tab", { name: "Experiments" })
    .click();
  await page.getByRole("button", { name: /Reference fold inspection/ }).click();
  await expect(
    page
      .getByRole("tablist", { name: "Researcher detail" })
      .getByRole("tab", { name: "Experiments" }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.locator('[data-experiment-id="exp1"]')).toBeVisible();
  await page.getByRole("link", { name: "Library", exact: true }).click();
  await page.getByRole("link", { name: "Investigations", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`#investigations/${root}$`));
});
test("mobile node-specific geometry remains usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fixture(page);
  await page.goto("/");
  await page
    .getByRole("button", { name: "Inspect Inspect the experimental fold" })
    .click();
  await page
    .getByRole("tablist", { name: "Researcher detail" })
    .getByRole("tab", { name: "Experiments" })
    .click();
  await expect(page.locator(".artifact-canvas canvas")).toBeVisible({
    timeout: 20000,
  });
  await page.locator(".artifact-canvas").scrollIntoViewIfNeeded();
  await page.waitForTimeout(700);
  await page.screenshot({ path: "/tmp/dn-runtime-mobile.png" });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
