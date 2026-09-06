import { test, expect } from "@playwright/test";
import { readFileSync, mkdirSync } from "node:fs";
import { mockApi, investigation } from "./fixtures";
import { initialView } from "../src/components/tissue/types";
test.use({
  launchOptions: {
    args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
  },
});
const tissue = JSON.parse(
  readFileSync(new URL("./tissue/fixture.json", import.meta.url), "utf8"),
);
test("living tissue renders scoped artifact, synchronized views and exact-frame selection", async ({
  page,
}) => {
  test.setTimeout(120000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await mockApi(page);
  const root = investigation.root;
  const raw: any[] = [
    [
      "attempt.started",
      {
        original_question: investigation.goal,
        branch_objective: "Inspect alanine exchange",
      },
    ],
    [
      "experiment.queued",
      { title: "Paired tissue experiment", status: "queued" },
      "tissue1",
    ],
    [
      "experiment.finished",
      { status: "completed", exploratory: true },
      "tissue1",
    ],
    [
      "artifact",
      {
        artifact_id: "tissue-a",
        name: tissue.name,
        kind: "tissue_simulation",
        status: "available",
        storage_key: "tissue-fixture",
        sha256: "tissue-fixture",
        provenance: tissue.provenance,
      },
      "tissue1",
    ],
  ];
  for (const [i, view] of [
    initialView,
    { ...initialView, preset: "Core", section: 0, frame: 2 },
  ].entries()) {
    raw.push([
      "tissue.scene",
      {
        artifact_sha256: "tissue-fixture",
        recipe_sha256: `recipe-${i}`,
        view,
        note: i ? "Inspect final core" : "Establish exterior",
        actor: "agent",
      },
      "tissue1",
    ]);
  }
  const events = raw.map(([kind, payload, experiment_id], i) => ({
    schema_version: 1,
    sequence: i + 1,
    run_id: root,
    attempt_id: "tissue-test",
    event_id: `e${i}`,
    kind,
    payload,
    experiment_id,
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
    if (u.pathname.includes("/blob/")) return r.fulfill({ json: tissue });
    if (u.pathname.endsWith("/stream"))
      return r.fulfill({
        contentType: "text/event-stream",
        body: ": connected\n\n",
      });
    return r.fulfill({ status: 404, json: { error: "fixture" } });
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Inspect Inspect alanine exchange" })
    .click();
  await page
    .getByRole("tablist", { name: "Researcher detail" })
    .getByRole("tab", { name: "Experiments" })
    .click();
  await page
    .getByRole("button", { name: /Open living tissue/ })
    .click({ timeout: 15000 });
  const ready = async () => {
    await page.waitForFunction(() => Boolean((window as any).tissueReview));
    await page.evaluate(() => (window as any).tissueReview.ready());
  };
  const dir =
    process.env.TISSUE_CAPTURES || `${process.env.E2E_RUN_DIR}/tissue-review`;
  mkdirSync(dir, { recursive: true });
  await ready();
  await page.getByRole("button", { name: "Watch agent actions" }).click();
  await page.getByLabel("Agent action timeline").fill("1");
  await ready();
  await expect(page.getByLabel("Simulation time")).toHaveValue("2");
  await expect(page.getByLabel("Section plane")).toHaveValue("0");
  await page.getByLabel("Agent playback speed").selectOption("4");
  await page.getByRole("button", { name: "Return to my view" }).click();
  await ready();
  await expect(page.getByLabel("Simulation time")).toHaveValue("0");
  await expect(page.getByLabel("Section plane")).toHaveValue("160");
  for (const size of [
    { width: 1600, height: 1000 },
    { width: 1920, height: 1080 },
  ]) {
    await page.setViewportSize(size);
    for (const preset of ["Exterior", "Core"]) {
      await page.getByRole("button", { name: preset, exact: true }).click();
      await ready();
      await page.screenshot({ path: `${dir}/${size.width}-${preset}.png` });
    }
  }
  await page.getByLabel("Simulation time").fill("2");
  await page.getByLabel("Paired comparison").check();
  await ready();
  await page.screenshot({ path: `${dir}/1920-Comparison.png` });
  await page.getByLabel("Selected cell").selectOption("10");
  await ready();
  await expect(page.locator(".tissue-inspection")).toContainText("Tumor #10", {
    ignoreCase: true,
  });
  await page.evaluate(() => (document.documentElement.dataset.theme = "light"));
  await ready();
  await page.screenshot({ path: `${dir}/light.png` });
  await page.evaluate(() => (document.documentElement.dataset.theme = "dark"));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.getByLabel("Paired comparison").uncheck();
  await ready();
  await page.screenshot({ path: `${dir}/mobile.png` });
  await page.locator('.tissue-canvas canvas').first().evaluate(el=>{
    const gl=(el as HTMLCanvasElement).getContext('webgl2')!;
    gl.getExtension('WEBGL_lose_context')!.loseContext();
  });
  await expect(page.getByRole('button',{name:'Restore tissue scene'})).toBeVisible();
  await page.getByRole('button',{name:'Restore tissue scene'}).click();
  await ready();
  await page.getByRole("button", { name: "Return to experiment" }).click();
  const pickFixture=structuredClone(tissue);
  for(const condition of pickFixture.conditions)for(const frame of condition.frames){
    frame.cells=[{id:73,position:[0,0,0],radius:20,type:'tumor',state:'alive',parent_id:null,alanine:.125}];
    frame.field={dimensions:[2,2,2],values:Array(8).fill(.125)};
  }
  await page.route('**/api/runtime/**/blob/**',route=>route.fulfill({json:pickFixture}));
  await page.reload();
  await page.getByRole('button',{name:'Inspect Inspect alanine exchange'}).click();
  await page.getByRole('tablist',{name:'Researcher detail'}).getByRole('tab',{name:'Experiments'}).click();
  await page.getByRole('button',{name:/Open living tissue/}).click();await ready();
  const canvas=page.locator('.tissue-canvas canvas').first();const box=await canvas.boundingBox();
  await canvas.click({position:{x:box!.width/2,y:box!.height/2}});
  await expect(page.getByLabel('Selected cell')).toHaveValue('73');
  await expect(page.locator('.tissue-inspection')).toContainText('0.1250 mM');
  await page.getByRole('button',{name:'Return to experiment'}).click();
  await page.getByLabel("Activity playback position").fill("2");
  await expect(
    page.getByRole("button", { name: /Open living tissue/ }),
  ).toHaveCount(0);
  expect(errors).toEqual([]);
});
