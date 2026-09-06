import { test, expect, type Page } from "@playwright/test";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { mockApi, investigation } from "./fixtures";
const raw = readFileSync(
  new URL("./binder-fixture.json", import.meta.url),
  "utf8",
);
const sha = createHash("sha256").update(raw).digest("hex");
async function fixture(page: Page, recorded = false) {
  await mockApi(page);
  const root = investigation.root;
  const payloads: [string, unknown][] = [
    [
      "attempt.started",
      {
        original_question: investigation.goal,
        branch_objective: "Inspect illustrative interface",
        lifecycle: "running",
      },
    ],
    [
      "experiment.queued",
      {
        title: "Illustrative interface geometry",
        status: "queued",
        method: "exploratory",
      },
    ],
    ["experiment.finished", { status: "completed", exploratory: true }],
    [
      "artifact",
      {
        artifact_id: "binder",
        kind: "binder_bundle",
        name: "Illustrative translated 1CRN complex",
        status: "available",
        storage_key: sha,
        sha256: sha,
        provenance: { category: "illustration" },
        atom_count: 654,
      },
    ],
  ];
  if (recorded)
    for (const preset of ["hero", "interface-close", "reverse"])
      payloads.push([
        "scene.recipe",
        {
          scene_id: "fixture-scene",
          bundle_sha256: sha,
          actor: "agent",
          note: "Review " + preset,
          recipe: { sha256: "fixture-" + preset },
          view: { preset, style: "pearl", selected: null, camera: null },
        },
      ]);
  const events = payloads.map(([kind, payload], i) => ({
    schema_version: 1,
    sequence: i + 1,
    run_id: root,
    attempt_id: "fixture",
    event_id: `binder-${i}`,
    kind,
    payload,
    experiment_id: i ? "exp1" : null,
    producer: kind === "artifact" ? "collector" : "runner",
    recorded_at: Date.now() / 1000,
  }));
  await page.route("**/api/investigations**", (r) =>
    r.fulfill({ json: [{ ...investigation, runtime: true }] }),
  );
  await page.route("**/api/runtime/**", (r) => {
    const u = new URL(r.request().url());
    if (u.pathname.endsWith("/events"))
      return r.fulfill({
        json: {
          events: events.filter(
            (e) => e.sequence > Number(u.searchParams.get("after") || 0),
          ),
        },
      });
    if (u.pathname.endsWith("/stream"))
      return r.fulfill({
        contentType: "text/event-stream",
        body: ": connected\n\n",
      });
    if (u.pathname.includes("/blob/")) return r.fulfill({ body: raw });
    return r.fulfill({ status: 404, json: { error: "unavailable" } });
  });
  await page.goto("/?sceneReview=1");
  await page
    .getByRole("tablist", { name: "Investigation view" })
    .getByRole("tab", { name: "Experiments", exact: true })
    .click();
  await page
    .locator(".experiment-row")
    .filter({ hasText: "Illustrative interface geometry" })
    .click();
  await page
    .getByRole("tablist", { name: "Researcher detail" })
    .getByRole("tab", { name: "Experiments", exact: true })
    .click();
  await expect(page.locator('[data-testid="binder-stage"] canvas')).toBeVisible(
    { timeout: 30000 },
  );
  await page.evaluate(async () => {
    await (window as any).sceneReview.ready();
  });
}
test("binder artifact picking, camera stability, replay and responsive tables", async ({
  page,
}) => {
  test.setTimeout(90000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await fixture(page);
  await page.getByRole("button", { name: "Expand workbench" }).click();
  await page.evaluate(async () => {
    await (window as any).sceneReview.ready();
  });
  const before = await page.evaluate(
    () => (window as any).sceneReview.inspect().camera,
  );
  await page.locator(".binder-sequence button").first().click();
  const after = await page.evaluate(
    () => (window as any).sceneReview.inspect().camera,
  );
  for (const field of ["position", "target", "quaternion", "up"])
    for (let i = 0; i < before[field].length; i++)
      expect(after[field][i]).toBeCloseTo(before[field][i], 9);
  for (const field of ["fov", "near", "far", "projection"])
    expect(after[field]).toEqual(before[field]);
  await expect(page.locator(".binder-table table")).toBeVisible();
  const picked = await page.evaluate(() => {
    const bridge = (window as any).sceneReview;
    const { width, height } = bridge.inspect().viewport;
    for (let y = height * 0.3; y < height * 0.7; y += 20)
      for (let x = width * 0.3; x < width * 0.7; x += 20) {
        const id = bridge.pick(x, y);
        if (id) return id;
      }
    return null;
  });
  expect(picked).toBeTruthy();
  await page.getByRole("button", { name: "Compact view" }).click();
  await page.getByLabel("Activity playback position").fill("3");
  await expect(page.locator(".binder-workbench")).toHaveCount(0);
  expect(errors).toEqual([]);
});
test("binder visual review captures", async ({ page }) => {
  test.setTimeout(180000);
  await fixture(page);
  await page.getByRole("button", { name: "Expand workbench" }).click();
  const dir = process.env.BINDER_REVIEW_DIR || "/tmp/binder-review-r01";
  mkdirSync(dir, { recursive: true });
  for (const preset of [
    "hero",
    "interface-close",
    "reverse",
    "epitope",
    "exploded",
    "candidate-compare",
  ]) {
    await page.evaluate(async (preset) => {
      await (window as any).sceneReview.apply({ preset });
      await (window as any).sceneReview.ready();
    }, preset);
    expect(
      await page.evaluate(() => (window as any).sceneReview.inspect().preset),
    ).toBe(preset);
    await page.screenshot({ path: `${dir}/${preset}-page.png` });
    await page
      .locator('[data-testid="binder-stage"]')
      .screenshot({ path: `${dir}/${preset}-stage.png` });
    writeFileSync(
      `${dir}/${preset}.json`,
      JSON.stringify(
        await page.evaluate(() => (window as any).sceneReview.inspect()),
        null,
        2,
      ),
    );
  }
  await page.getByLabel("Material study").selectOption("copper");
  await page.evaluate(async () => {
    await (window as any).sceneReview.apply({ preset: "hero" });
    await (window as any).sceneReview.ready();
  });
  await page.screenshot({ path: `dir/copper.png`.replace("dir", dir) });
  await page.getByLabel("Material study").selectOption("pearl");
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.evaluate(async () => {
    await (window as any).sceneReview.apply({ preset: "hero" });
    await (window as any).sceneReview.ready();
  });
  await page.screenshot({ path: `${dir}/presentation.png` });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(async () => {
    await (window as any).sceneReview.apply({ preset: "small-screen" });
    await (window as any).sceneReview.ready();
  });
  await page.screenshot({ path: `${dir}/mobile.png` });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= 390),
  ).toBeTruthy();
});

test("recorded camera actions replay at adjustable speed while exploration stays local", async ({
  page,
}) => {
  test.setTimeout(90000);
  await fixture(page, true);
  await expect(page.getByText(/Review reverse/)).toBeVisible();
  await page.getByLabel("Agent scene action", { exact: true }).fill("0");
  await expect(page.getByText(/Review hero/)).toBeVisible();
  await page.getByLabel("Scene playback speed").selectOption("4");
  await page
    .getByRole("button", { name: "Replay agent inspection", exact: true })
    .click();
  await expect(page.getByText(/Review reverse/)).toBeVisible();
  await page.getByRole("button", { name: "epitope", exact: true }).click();
  await expect(page.getByText(/Your changes are local/)).toBeVisible();
  await page
    .getByRole("button", { name: "Follow latest agent view", exact: true })
    .click();
  await expect
    .poll(() => page.evaluate(() => (window as any).sceneReview?.inspect().preset))
    .toBe("reverse");
  await page.getByLabel("Activity playback position").fill("5");
  await expect
    .poll(() =>
      page.evaluate(() => (window as any).sceneReview?.inspect().preset),
    )
    .toBe("hero");
});
