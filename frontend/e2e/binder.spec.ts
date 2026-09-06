import { test, expect, type Page } from "@playwright/test";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { mockApi, investigation } from "./fixtures";
const baseRaw = readFileSync(
  new URL("./binder-fixture.json", import.meta.url),
  "utf8",
);
async function fixture(
  page: Page,
  recorded = false,
  raw = baseRaw,
  extra: {
    payloads?: [string, unknown][];
    blobs?: Record<string, string>;
  } = {},
) {
  const sha = createHash("sha256").update(raw).digest("hex");
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
  payloads.push(...(extra.payloads ?? []));
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
    if (u.pathname.includes("/blob/"))
      return r.fulfill({
        body: extra.blobs?.[u.pathname.split("/").at(-1)!] ?? raw,
      });
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
  const dir =
    process.env.BINDER_REVIEW_DIR ||
    test.info().outputPath("binder-review-r01");
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
    .poll(() =>
      page.evaluate(() => (window as any).sceneReview?.inspect().preset),
    )
    .toBe("reverse");
  await page.getByLabel("Activity playback position").fill("5");
  await expect
    .poll(() =>
      page.evaluate(() => (window as any).sceneReview?.inspect().preset),
    )
    .toBe("hero");
});

test("source-mapped surface and backbone trace preserve the coordinate assessment", async ({
  page,
}) => {
  test.setTimeout(120000);
  const review =
    process.env.BINDER_SURFACE_REVIEW_DIR || "/tmp/binder-surface-r02";
  mkdirSync(review, { recursive: true });
  const source = readFileSync(
    new URL("./binder-surface-fixture.json", import.meta.url),
    "utf8",
  );
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await fixture(page, false, source);
  await page.getByRole("button", { name: "Expand workbench" }).click();
  await page.evaluate(async () => {
    await (window as any).sceneReview.ready();
  });
  expect(
    await page.evaluate(
      () => (window as any).sceneReview.inspect().representation,
    ),
  ).toBe("surface");
  await page.screenshot({ path: review + "/hero-page.png" });
  await page
    .locator('[data-testid="binder-stage"]')
    .screenshot({ path: review + "/hero-stage.png" });
  const picked = await page.evaluate(() => {
    const bridge = (window as any).sceneReview;
    const { width, height } = bridge.inspect().viewport;
    for (let x = width * 0.35; x < width * 0.65; x += 20) {
      const id = bridge.pick(x, height * 0.5);
      if (id) return id;
    }
    return null;
  });
  expect(JSON.parse(source).structure.residues.map((r: any) => r.id)).toContain(
    picked,
  );
  await page.getByLabel("Molecular representation").selectOption("ribbon");
  await page.evaluate(async () => {
    await (window as any).sceneReview.ready();
  });
  expect(
    await page.evaluate(
      () => (window as any).sceneReview.inspect().representation,
    ),
  ).toBe("ribbon");
  await page
    .locator('[data-testid="binder-stage"]')
    .screenshot({ path: review + "/ribbon-stage.png" });
  await page
    .getByRole("button", { name: "interface close", exact: true })
    .click();
  await page.evaluate(async () => {
    await (window as any).sceneReview.ready();
  });
  expect(
    await page.evaluate(
      () => (window as any).sceneReview.inspect().representation,
    ),
  ).toBe("atoms");
  await expect(page.locator(".binder-inspector")).toContainText("404");
  await expect(page.locator(".binder-inspector")).toContainText("Not measured");
  await page.evaluate(async () => {
    await (window as any).sceneReview.apply({
      preset: "hero",
      representation: "surface",
      selected: null,
      style: "copper",
    });
    await (window as any).sceneReview.ready();
  });
  await page
    .locator('[data-testid="binder-stage"]')
    .screenshot({ path: review + "/copper-stage.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.evaluate(async () => {
    await (window as any).sceneReview.apply({
      preset: "small-screen",
      representation: "surface",
      style: "pearl",
    });
    await (window as any).sceneReview.ready();
  });
  await page.screenshot({ path: review + "/mobile.png" });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= 390),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});

test("native binder records and real job states respect the experiment cursor", async ({
  page,
}) => {
  const record = JSON.stringify({
    schema: "binder_target.v1",
    scope: { project_id: "fixture", run_id: "fixture", experiment_id: "exp1" },
    data: {
      construct_policy: "Illustrative chain crop; accessibility unavailable",
    },
  });
  const key = createHash("sha256").update(record).digest("hex");
  await fixture(page, false, baseRaw, {
    blobs: { [key]: record },
    payloads: [
      [
        "artifact",
        {
          artifact_id: "target",
          kind: "binder_target",
          name: "Target review",
          status: "available",
          sha256: key,
          storage_key: key,
          provenance: { category: "derived_geometry" },
        },
      ],
      ["binder.job", { receipt: "fixture-only", state: "queued", cursor: 1 }],
      [
        "binder.job",
        {
          receipt: "fixture-only",
          state: "canceled",
          cursor: 2,
          reason: "Canceled by experiment owner; partial candidates retained",
        },
      ],
    ],
  });
  await page.getByText("Inspect Binder target", { exact: true }).click();
  await expect(
    page.getByText(/Illustrative chain crop; accessibility unavailable/),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Download record" }),
  ).toHaveAttribute("href", new RegExp(key));
  await page.getByText("Binder design activity", { exact: true }).click();
  await expect(
    page.getByText(/Canceled by experiment owner; partial candidates retained/),
  ).toBeVisible();
  await page.getByLabel("Activity playback position").fill("4");
  await expect(
    page.getByText("Inspect Binder target", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Binder design activity", { exact: true }),
  ).toHaveCount(0);
});


test("node scene persists across activity tabs and selects only available sources", async ({ page }) => {
  test.setTimeout(90000);
  const surfaceRaw = readFileSync(new URL("./binder-surface-fixture.json", import.meta.url), "utf8");
  const second = JSON.parse(surfaceRaw);
  second.manifest.candidate_id = "second illustrative view";
  const raw = JSON.stringify(second), hash = createHash("sha256").update(raw).digest("hex");
  await fixture(page, false, surfaceRaw, { blobs: { [hash]: raw }, payloads: [["artifact", {
    artifact_id: "second", kind: "binder_bundle", name: "Second illustrative candidate",
    status: "available", storage_key: hash, sha256: hash, provenance: { category: "illustration" },
  }], ["scene.review", { observation: "Fixture image observation: compare the source contact distances." }],
  ["scene.recipe", { note: "Fixture action: inspect the opposite interface", bundle_sha256: "other-unavailable-source" }]] });
  const stage = page.locator('[data-testid="binder-stage"] canvas');
  await stage.evaluate(el => el.setAttribute("data-preserved", "yes"));
  await page.getByRole("tablist", { name: "Researcher detail" }).getByRole("tab", { name: "Activity", exact: true }).click();
  await expect(stage).toHaveAttribute("data-preserved", "yes");
  await expect(page.getByText("Fixture image observation: compare the source contact distances.", { exact: true })).toBeVisible();
  await expect(page.getByText("Fixture action: inspect the opposite interface", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Research activity and findings" })).toBeVisible();
  const left = await page.getByRole("region", { name: "Research scene", exact: true }).boundingBox();
  const right = await page.getByRole("region", { name: "Research activity and findings" }).boundingBox();
  expect(left!.x + left!.width).toBeLessThanOrEqual(right!.x + 1);
  await page.screenshot({ path: test.info().outputPath("node-scene-desktop.png") });
  await page.getByRole("combobox", { name: "Scene source", exact: true }).selectOption("exp1:second");
  await expect(page.locator(`.binder-workbench[data-bundle-sha256="${hash}"]`)).toBeVisible();
  await expect(page.locator('[data-testid="binder-stage"] canvas')).toHaveCount(1);
  await page.getByLabel("Activity playback position").fill("4");
  await expect(page.getByRole("combobox", { name: "Scene source", exact: true }).locator("option")).toHaveCount(1);
  await expect(page.locator(`.binder-workbench[data-bundle-sha256="${hash}"]`)).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForFunction(() => Boolean((window as any).sceneReview));
  await page.evaluate(async () => { await (window as any).sceneReview.ready(); });
  await page.screenshot({ path: test.info().outputPath("node-scene-mobile.png") });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await expect(page.getByRole("button", { name: "Close scene workspace" })).toBeVisible();
});

test("binder camera travels continuously and user takeover cancels the remaining motion", async ({ page }) => {
  test.setTimeout(90000);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await fixture(page);
  const samples = await page.evaluate(async () => {
    const bridge = (window as any).sceneReview;
    const start = bridge.inspect().camera.position;
    await bridge.apply({ preset: "reverse" });
    const positions = [start], frames: string[] = [];
    const deadline = performance.now() + 2000;
    while (frames.length < 3 && performance.now() < deadline) {
      await new Promise(requestAnimationFrame);
      const position = bridge.inspect().camera.position;
      if (JSON.stringify(position) === JSON.stringify(positions.at(-1))) continue;
      positions.push(position); frames.push(bridge.capture());
    }
    return { positions, frames };
  });
  expect(samples.frames).toHaveLength(3);
  samples.frames.forEach((png, i) => writeFileSync(test.info().outputPath(`camera-motion-${i}.png`), Buffer.from(png.split(",")[1], "base64")));
  writeFileSync(test.info().outputPath("camera-motion.json"), JSON.stringify(samples.positions));
  expect(samples.positions[1]).not.toEqual(samples.positions[0]);
  expect(samples.positions[2]).not.toEqual(samples.positions[1]);
  expect(samples.positions[3]).not.toEqual(samples.positions[2]);
  const box = await page.locator('[data-testid="binder-stage"] canvas').boundingBox();
  await page.mouse.move(box!.x + 20, box!.y + 20);
  await page.evaluate(async () => { await (window as any).sceneReview.apply({ preset: "hero" }); });
  expect(await page.evaluate(() => (window as any).sceneReview.inspect().camera_transitioning)).toBe(true);
  await page.mouse.down();
  expect(await page.evaluate(() => (window as any).sceneReview.inspect().camera_transitioning)).toBe(false); await page.mouse.move(box!.x + 45, box!.y + 25); await page.mouse.up();
  const held = await page.evaluate(() => (window as any).sceneReview.inspect().camera);
  await page.waitForTimeout(800);
  const afterHold = await page.evaluate(() => (window as any).sceneReview.inspect().camera);
  for (const field of ["position", "target", "quaternion", "up"])
    for (let i = 0; i < held[field].length; i++)
      expect(afterHold[field][i]).toBeCloseTo(held[field][i], 9);
  for (const field of ["fov", "near", "far", "projection"])
    expect(afterHold[field]).toEqual(held[field]);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.evaluate(async () => { await (window as any).sceneReview.apply({ preset: "hero" }); await (window as any).sceneReview.ready(); });
  const fixed = await page.evaluate(() => (window as any).sceneReview.inspect().camera);
  await page.waitForTimeout(150);
  const afterFixed = await page.evaluate(() => (window as any).sceneReview.inspect().camera);
  for (const field of ["position", "target", "quaternion", "up"])
    for (let i = 0; i < fixed[field].length; i++)
      expect(afterFixed[field][i]).toBeCloseTo(fixed[field][i], 9);
  for (const field of ["fov", "near", "far", "projection"])
    expect(afterFixed[field]).toEqual(fixed[field]);
});


test("comparison shares camera and scale, returns the picked candidate and respects source history", async ({ page }) => {
  test.setTimeout(90000);
  const raw = readFileSync(new URL("./binder-comparison-fixture.json", import.meta.url), "utf8");
  const second = JSON.parse(raw), hash = createHash("sha256").update(raw).digest("hex");
  await fixture(page, false, baseRaw, { blobs: { [hash]: raw }, payloads: [["artifact", {
    artifact_id: "comparison", kind: "binder_bundle", name: "Comparison illustration", status: "available",
    storage_key: hash, sha256: hash, provenance: { category: "illustration" },
  }]] });
  const errors: string[] = []; page.on("pageerror", e => errors.push(e.message));
  await page.getByRole("button", { name: "Expand workbench" }).click();
  await page.getByRole("combobox", { name: "Compare candidate", exact: true }).selectOption(hash);
  await page.evaluate(async () => { await (window as any).sceneReview.ready(); });
  const initial = await page.evaluate(() => (window as any).sceneReview.inspect());
  expect(initial.views).toHaveLength(2);
  expect(initial.views[0].camera).toEqual(initial.views[1].camera);
  expect(initial.views[0].viewport.width).toEqual(initial.views[1].viewport.width);
  expect(initial.views[0].physical_to_scene).toEqual(initial.views[1].physical_to_scene);
  expect(initial.views[1].bundle_sha256).toBe(hash);
  await expect(page.locator('[data-testid="binder-stage"] canvas')).toHaveCount(1);
  await page.screenshot({ path: test.info().outputPath("comparison-desktop.png") });
  const box = await page.locator('[data-testid="binder-stage"]').boundingBox();
  await page.mouse.move(box!.x + box!.width * .7, box!.y + box!.height * .5);
  await page.mouse.down(); await page.mouse.move(box!.x + box!.width * .75, box!.y + box!.height * .53); await page.mouse.up();
  const rotated = await page.evaluate(() => (window as any).sceneReview.inspect());
  expect(rotated.views[0].camera).toEqual(rotated.views[1].camera);
  expect(rotated.views[0].camera.position).not.toEqual(initial.views[0].camera.position);
  const picked = await page.evaluate(() => {
    const bridge = (window as any).sceneReview, { width, height } = bridge.inspect().viewport;
    for (let y = height * .3; y < height * .8; y += 15)
      for (let x = width * .6; x < width * .9; x += 15) {
        const pick = bridge.pick(x, y); if (pick) return pick;
      }
    return null;
  });
  expect(picked?.bundle_sha256).toBe(hash);
  await expect(page.locator('.binder-inspected-candidate')).toHaveText('Inspecting shifted illustrative pair');
  await expect(page.locator('.binder-inspector').getByText(String(second.metrics.counts["4.5"]), { exact: true })).toBeVisible();
  await expect(page.getByRole('table', { name: 'Candidate geometry trade-offs' })).toContainText('171');
  await page.setViewportSize({ width: 1000, height: 800 });
  await page.evaluate(async () => { await (window as any).sceneReview.ready(); });
  const resized = await page.evaluate(() => (window as any).sceneReview.inspect());
  expect(resized.views[0].camera).toEqual(resized.views[1].camera);
  expect(resized.views[0].viewport.width).toEqual(resized.views[1].viewport.width);
  const resizedPick = await page.evaluate(() => {
    const bridge = (window as any).sceneReview, { width, height } = bridge.inspect().viewport;
    for (let y = height * .3; y < height * .8; y += 10)
      for (let x = width * .6; x < width * .9; x += 10) {
        const pick = bridge.pick(x, y); if (pick) return pick;
      }
    return null;
  });
  expect(resizedPick?.bundle_sha256).toBe(hash);
  await page.screenshot({ path: test.info().outputPath("comparison-resized.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(async () => { await (window as any).sceneReview.ready(); });
  await page.screenshot({ path: test.info().outputPath("comparison-mobile.png") });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.getByRole("button", { name: "Compact view" }).click();
  await page.getByLabel("Activity playback position").fill("4");
  await expect(page.getByRole("combobox", { name: "Compare candidate", exact: true }).locator('option')).toHaveCount(1);
  await expect(page.locator('.binder-compare-stage')).toHaveCount(0);
  expect(errors).toEqual([]);
});
