// Capture the actual owning experiment through its real scoped HTTP API.
import { chromium } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";
const [inputPath, outputPath] = process.argv.slice(2);
const input = JSON.parse(readFileSync(inputPath, "utf8"));
const base = new URL(input.base_url);
if (
  !["http:", "https:"].includes(base.protocol) ||
  !["127.0.0.1", "localhost", "[::1]"].includes(base.hostname) ||
  base.username ||
  base.password
)
  throw Error("Trusted local renderer origin required");
const scope = input.recipe.scope;
base.search = new URLSearchParams({ project: scope.project_id }).toString();
base.hash = "investigations/" + encodeURIComponent(input.investigation_id);
const browser = await chromium.launch({
  headless: true,
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});
try {
  const page = await browser.newPage({
    viewport: { width: 1600, height: 1000 },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(base.href);
  console.error('Tissue capture: app loaded');
  if (
    /test|smoke|demo|e2e|probe|dummy|sample|scratch|tmp/i.test(
      input.investigation_id,
    )
  )
    await page.getByLabel("Include test runs").check();
  await page
    .getByRole("tablist", { name: "Investigation view" })
    .getByRole("tab", { name: "Experiments", exact: true })
    .click();
  const rows = page.locator(".experiment-row");
  await rows.first().waitFor();
  const index = await rows.evaluateAll(
    (els, scope) =>
      els.findIndex(
        (el) =>
          el.dataset.sceneRun === scope.run_id &&
          el.dataset.sceneExperiment === scope.experiment_id,
      ),
    scope,
  );
  if (index < 0) throw Error("Owning tissue experiment unavailable");
  await rows.nth(index).click();
  console.error('Tissue capture: owning experiment selected');
  await page
    .getByRole("tablist", { name: "Researcher detail" })
    .getByRole("tab", { name: "Experiments", exact: true })
    .click();
  const buttons = page.locator(".tissue-open");
  await buttons.first().waitFor();
  const match = await buttons.evaluateAll(
    (els, key) => els.findIndex((el) => el.dataset.artifactSha256 === key),
    input.recipe.artifact_sha256,
  );
  if (match < 0) throw Error("Exact tissue artifact unavailable");
  await buttons.nth(match).click();
  console.error('Tissue capture: exact artifact opened');
  await page.setViewportSize({
    width: input.viewport[0],
    height: input.viewport[1],
  });
  await page.waitForFunction(() => Boolean(window.tissueReview));
  await page.evaluate(
    (view) => window.tissueReview.apply(view),
    input.recipe.view,
  );
  await page.evaluate(() => window.tissueReview.ready());
  console.error('Tissue capture: exact scene ready');
  const firstMeaningfulMs = await page.evaluate((key) => {
    const resources = performance
      .getEntriesByType("resource")
      .filter((r) => r.name.includes(key));
    return resources.length
      ? performance.now() - Math.min(...resources.map((r) => r.startTime))
      : null;
  }, input.recipe.artifact_sha256);
  const state = await page.evaluate(() => window.tissueReview.capture());
  if (errors.length) throw Error(errors.join("; "));
  const png = await page.screenshot({ animations: "disabled" });
  const canvases = await page
    .locator(".tissue-canvas canvas")
    .evaluateAll((nodes) =>
      nodes.map((n) => n.toDataURL("image/png").split(",")[1]),
    );
  const timing = await page
    .locator(".tissue-canvas canvas")
    .evaluateAll(async (nodes) =>
      Promise.all(nodes.map((n) => n.tissueBenchmark(20))),
    );
  if (timing.some((t) => !t.draw_calls || !t.triangles))
    throw Error("Benchmark did not draw tissue geometry");
  const assets = await page.evaluate(() => ({
    scripts: [...document.scripts].map((s) => s.src),
    styles: [...document.querySelectorAll('link[rel="stylesheet"]')].map(
      (s) => s.href,
    ),
  }));
  writeFileSync(
    outputPath,
    JSON.stringify({
      png: png.toString("base64"),
      canvas_pngs: canvases,
      recipe_sha256: input.recipe_sha256,
      view: state.recipe,
      renderer: {
        browser: browser.version(),
        renderer: "Three.js 0.180.0 / R3F",
        devicePixelRatio: 1,
        viewport: input.viewport,
        timing,
        assets,
        firstMeaningfulMs,
        quality: "SwiftShader;48 volume steps;exact frame",
      },
    }),
  );
} finally {
  await browser.close();
}
