// Render the actual owning experiment in a private browser context. No fixture/API substitution.
import { createHash } from "node:crypto";
import { chromium } from "@playwright/test";
import { readFile, writeFile } from "node:fs/promises";
const [input, output] = process.argv.slice(2);
const request = JSON.parse(await readFile(input, "utf8"));
const url = new URL(request.base_url);
if (
  !["http:", "https:"].includes(url.protocol) ||
  !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname) ||
  url.username ||
  url.password
)
  throw Error("Capture requires the trusted local workspace server");
url.search = new URLSearchParams({
  project: request.recipe.scope.project_id,
  experiment: request.recipe.scope.experiment_id,
  artifact: request.recipe.bundle_sha256,
  sceneTool: "spindle",
  sceneRevision: request.recipe_sha256 || "",
  sceneActor: "agent",
}).toString();
url.hash = "investigations/" + encodeURIComponent(request.investigation_id);
const browser = await chromium.launch({ headless: true, args: ["--use-gl=angle","--use-angle=swiftshader","--disable-dev-shm-usage","--renderer-process-limit=2"] });
try {
  const page = await browser.newPage({
    viewport: { width: request.viewport[0], height: request.viewport[1] },
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
  });
  const assets=[];const pending=[];
  page.on("response",response=>{
    const type=response.headers()["content-type"] || "";
    if(/javascript|text\/css/.test(type))pending.push((async()=>{const bytes=await response.body();assets.push({url:response.url(),sha256:createHash("sha256").update(bytes).digest("hex")});})().catch(()=>{}));
  });
  page.setDefaultTimeout(request.render_seconds * 1000);
  await page.goto(url.href);
  await page
    .getByRole("tablist", { name: "Investigation view" })
    .getByRole("tab", { name: "Experiments", exact: true })
    .click();
  const owner = page.locator(".experiment-row").filter({ visible: true });
  await owner.first().waitFor();
  const row = await owner.evaluateAll(
    (rows, scope) =>
      rows.findIndex(
        (el) =>
          el.dataset.sceneRun === scope.run_id &&
          el.dataset.sceneExperiment === scope.experiment_id,
      ),
    request.recipe.scope,
  );
  if (row < 0) throw Error("Owning experiment is unavailable");
  await owner.nth(row).click();
  await page
    .getByRole("tablist", { name: "Researcher detail" })
    .getByRole("tab", { name: "Experiments", exact: true })
    .click();
  const bench = page
    .locator(".spindle-observatory")
    .filter({ has: page.locator('.spindle-stage') });
  await bench.first().waitFor();
  const matches = await bench.evaluateAll(
    (els, sha) => els.findIndex((el) => el.dataset.bundleSha256 === sha),
    request.recipe.bundle_sha256,
  );
  if (matches < 0) throw Error("Exact spindle artifact unavailable");
  const selected = bench.nth(matches);
  await selected.getByRole("button", { name: "Expand scene" }).click();
  const stage = selected.locator('.spindle-stage');
  await stage.evaluate(async (el, view) => {
    await el.spindleController.apply(view);
    await el.spindleController.ready();
  }, request.recipe.view);
  const state = await stage.evaluate((el) => el.spindleController.inspect());
  const png = await stage.screenshot({ animations: "disabled" });
  await Promise.all(pending);
  state.browser=browser.version();state.served_assets=assets.sort((a,b)=>a.url.localeCompare(b.url));
  state.adapter_sha256=createHash("sha256").update(JSON.stringify(state.served_assets)).digest("hex");
  let picked = null;
  if (request.pick) {
    const box = await stage.boundingBox();
    if (
      Math.abs(box.width - request.image_size[0]) > 1 ||
      Math.abs(box.height - request.image_size[1]) > 1
    )
      throw Error("Capture geometry changed before picking");
    picked = await stage.evaluate(
      (el, xy) => el.spindleController.pick(...xy),
      request.pick,
    );
  }
  await writeFile(
    output,
    JSON.stringify({ png: png.toString("base64"), state, picked }),
  );
} finally {
  await browser.close();
}
