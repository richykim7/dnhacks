import { test, expect } from "@playwright/test";
import { mockApi, investigation } from "./fixtures";
import type { SpindleBundle, Vec3 } from "../src/components/spindle/types";
function fixture(): SpindleBundle {
  const radius: Vec3 = [12, 9, 8];
  return {
    schema_version: 1,
    dimensionality: 3,
    category: "illustration",
    model_id: "deterministic-art-fixture-v1",
    units: { length: "um", time: "s" },
    radius,
    runs: [
      "Bipolar illustration",
      "Multipolar illustration",
      "Transient illustration",
    ].map((condition, c) => ({
      seed: 41,
      condition,
      frames: Array.from({ length: 21 }, (_, t) => {
        const poles = Array.from({ length: 4 }, (_, i) => {
          const start: Vec3 = [
            Math.cos((i * Math.PI) / 2) * 5,
            Math.sin((i * Math.PI) / 2) * 4,
            (i % 2 ? 1 : -1) * 2,
          ];
          const end: Vec3 =
            c === 1
              ? start
              : [
                  i < 2 ? -5 : 5,
                  (i % 2 ? 1 : -1) * 0.7,
                  (i % 2 ? 1 : -1) * 0.5,
                ];
          const f = c === 2 ? Math.sin((t / 20) * Math.PI) : t / 20;
          return {
            id: `C${i + 1}`,
            position: start.map((v, j) => v * (1 - f) + end[j] * f) as Vec3,
          };
        });
        const filaments = poles.flatMap((p, k) =>
          Array.from({ length: 100 }, (_, i) => {
            const z = 1 - (2 * (i + 0.5)) / 100,
              a = i * 2.39996323 + k * 0.5,
              r = Math.sqrt(1 - z * z);
            const target: Vec3 = [
              radius[0] * r * Math.cos(a) * 0.96,
              radius[1] * r * Math.sin(a) * 0.96,
              radius[2] * z * 0.96,
            ];
            return {
              id: `${p.id}-f${i}`,
              pole: p.id,
              points: Array.from({ length: 14 }, (_, j) => {
                const f = j / 13;
                return p.position.map(
                  (v, n) =>
                    v * (1 - f) +
                    target[n] * f +
                    (n === 1
                      ? 1.8 * Math.sin(Math.PI * f) * Math.sin(i * 0.07)
                      : n === 2
                        ? 1.2 * Math.sin(Math.PI * f) * Math.cos(i * 0.07)
                        : 0),
                ) as Vec3;
              }),
            };
          }),
        );
        return { time: t * 5, poles, filaments };
      }),
    })),
  };
}
test("spindle saved coordinates, deterministic views, condition comparison and review captures", async ({
  page,
}) => {
  await mockApi(page);
  const root = investigation.root;
  const raw = [
    [
      "attempt.started",
      {
        original_question: "Spindle art study",
        branch_objective: "Inspect spindle trajectories",
      },
    ],
    [
      "experiment.queued",
      { title: "Spindle visual development", method: "Illustrative geometry" },
    ],
    ["experiment.finished", { status: "completed", exploratory: true }],
    [
      "artifact",
      {
        artifact_id: "spindle",
        name: "spindle.json",
        kind: "filament_trajectory",
        status: "available",
        storage_key: "spindle",
        provenance: { category: "illustration" },
      },
    ],
  ];
  const events = raw.map(([kind, payload], i) => ({
    schema_version: 1,
    sequence: i + 1,
    run_id: root,
    attempt_id: "fixture",
    event_id: `s${i}`,
    kind,
    payload,
    experiment_id: i ? "spindle-exp" : undefined,
    producer: kind === "artifact" ? "collector" : "runner",
    recorded_at: 1,
  }));
  await page.route("**/api/investigations**", (r) =>
    r.fulfill({ json: [{ ...investigation, runtime: true }] }),
  );
  await page.route("**/api/runtime/**", (r) => {
    const u = new URL(r.request().url());
    if (u.pathname.includes("/blob/")) return r.fulfill({ json: fixture() });
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
    return r.fulfill({ status: 404, json: { error: "fixture" } });
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Inspect Inspect spindle trajectories" })
    .click();
  await page
    .getByRole("tablist", { name: "Researcher detail" })
    .getByRole("tab", { name: "Experiments", exact: true })
    .click();
  await page.getByRole("button", { name: "Expand scene" }).click();
  const scene = page.locator(".spindle-observatory");
  await expect(scene).toHaveAttribute("data-scene-ready", "true");
  const pass = process.env.SPINDLE_REVIEW_PASS || "draft";
  for (const shot of ["front", "oblique", "detail"]) {
    await page.getByLabel("Centrosome", { exact: true }).selectOption("C1");
    await page.getByLabel("View", { exact: true }).selectOption(shot);
    await expect(scene).toHaveAttribute("data-scene-ready", "true");
    await page.screenshot({ path: test.info().outputPath(`spindle-${pass}-${shot}.png`) });
  }
  await page.getByLabel("View", { exact: true }).selectOption("oblique");
  for (const t of [0, 10, 20]) {
    await page.getByLabel("Spindle physical time").fill(String(t));
    await expect(scene).toHaveAttribute("data-scene-ready", "true");
    await page.screenshot({ path: test.info().outputPath(`spindle-${pass}-time-${t}.png`) });
  }
  await expect(page.locator(".spindle-readout")).toContainText(
    "C1 · (-5.000, -0.700, -0.500)",
  );
  await page.getByLabel("Condition", { exact: true }).selectOption("1");
  await expect(page.locator(".spindle-caption")).toContainText("100.00 s");
  await expect(scene).toHaveAttribute("data-scene-ready", "true");
  await page.screenshot({ path: test.info().outputPath(`spindle-${pass}-multipolar.png`) });
  await page.getByLabel("Filaments", { exact: true }).selectOption("fine");
  await expect(scene).toHaveAttribute("data-scene-ready", "true");
  await page.screenshot({ path: test.info().outputPath(`spindle-${pass}-fine.png`) });
  await page.setViewportSize({ width: 1920, height: 1080 });
  await expect(scene).toHaveAttribute("data-scene-ready", "true");
  await page.screenshot({ path: test.info().outputPath(`spindle-${pass}-presentation.png`) });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(scene).toHaveAttribute("data-scene-ready", "true");
  await page.screenshot({ path: test.info().outputPath(`spindle-${pass}-mobile.png`) });
});
