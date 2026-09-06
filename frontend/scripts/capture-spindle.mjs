// Render the actual owning experiment in a private browser context. No fixture/API substitution.
import { createHash } from "node:crypto";
import { chromium } from "@playwright/test";
import { readFile, writeFile, mkdtemp, rm } from "node:fs/promises";
import { tmpdir, cpus, platform, arch, loadavg } from "node:os";
import { join, isAbsolute } from "node:path";
import { spawnSync } from "node:child_process";
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
  const experimentSelector = await page.evaluate(id => `[data-experiment-id="${CSS.escape(id)}"]`, request.recipe.scope.experiment_id);
  const selected = page.locator(experimentSelector).locator(`.spindle-observatory[data-bundle-sha256="${request.recipe.bundle_sha256}"]`).first();
  await selected.waitFor({ state:"visible" });
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
  state.capture_script_sha256=createHash("sha256").update(await readFile(new URL(import.meta.url))).digest("hex");
  state.adapter_sha256=createHash("sha256").update(JSON.stringify(state.served_assets)).digest("hex");
  let movie = null;
  if (request.movie) {
    const { frames, fps } = request.movie;
    if (!Array.isArray(frames) || frames.length < 2 || frames.length > 120 || !Number.isInteger(fps) || fps < 1 || fps > 30 || frames.some((f,i) => !Number.isInteger(f) || f < 0 || (i && f <= frames[i-1]))) throw Error("Invalid bounded movie sequence");
    const ffmpeg = process.env.SPINDLE_FFMPEG_BIN;
    if (!ffmpeg || !isAbsolute(ffmpeg)) throw Error("Operator SPINDLE_FFMPEG_BIN is required for movie export");
    const directory = await mkdtemp(join(tmpdir(), "spindle-movie-"));
    try {
      const shots = [], renderTimes = [], updateTimes = [];
      const frozen = { ...request.recipe.view, camera: state.camera };
      for (let warmup = 0; warmup < 3; warmup++) {
        await stage.evaluate(async (el, view) => { await el.spindleController.apply(view); await el.spindleController.ready(); }, frozen);
      }
      const started = performance.now();
      for (let i=0; i<frames.length; i++) {
        const updateStarted = performance.now();
        await stage.evaluate(async (el, view) => { await el.spindleController.apply(view); await el.spindleController.ready(); }, { ...frozen, frame: frames[i] });
        updateTimes.push(performance.now()-updateStarted);
        const actual = await stage.evaluate(el => el.spindleController.inspect());
        const file = join(directory, String(i).padStart(4,"0") + ".png");
        const bytes = await stage.screenshot({ path: file, animations: "disabled" });
        shots.push({ frame: frames[i], presentation_time_s: i/fps, image_sha256: createHash("sha256").update(bytes).digest("hex"), state: actual });
        renderTimes.push(actual.frame_render_ms);
      }
      const captureMs = performance.now() - started;
      const target = join(directory, "spindle.webm");
      const encodeStarted = performance.now();
      const encoded = spawnSync(ffmpeg, ["-hide_banner","-loglevel","error","-framerate",String(fps),"-i",join(directory,"%04d.png"),"-vf","pad=ceil(iw/2)*2:ceil(ih/2)*2","-fflags","+bitexact","-flags:v","+bitexact","-map_metadata","-1","-c:v","libvpx-vp9","-crf","32","-b:v","0","-pix_fmt","yuv420p","-threads","2","-an",target], { timeout:120000, maxBuffer:2*1024*1024 });
      if (encoded.error || encoded.status !== 0) throw Error("Movie encoder failed: " + (encoded.error?.message || encoded.stderr.toString().slice(-500)));
      const bytes = await readFile(target);
      if (bytes.length > 8*1024*1024) throw Error("Movie exceeds artifact budget");
      const sorted = renderTimes.toSorted((a,b)=>a-b);
      movie = { bytes: bytes.toString("base64"), frames:shots, fps, codec:"VP9/WebM", interpolation:"none", camera:state.camera,
        duration_s:frames.length/fps, capture_ms:captureMs, encode_ms:performance.now()-encodeStarted,
        render_p95_ms:sorted[Math.ceil(sorted.length*.95)-1], render_samples_ms:renderTimes,
        update_p95_ms:updateTimes.toSorted((a,b)=>a-b)[Math.ceil(updateTimes.length*.95)-1], update_samples_ms:updateTimes,
        timing_scope:"render: synchronous WebGL draw+finish only; update: saved frame apply/readiness including browser automation transport; capture/encoding separate",
        hardware:{ cpu:cpus()[0]?.model, logical_cpus:cpus().length, load_average:loadavg(), platform:platform(), arch:arch(), rendering:"Chromium ANGLE SwiftShader software; viewport emulation is not physical mobile hardware" },
        encoder_sha256:createHash("sha256").update(await readFile(ffmpeg)).digest("hex"),
        encoder_version:spawnSync(ffmpeg,["-version"],{timeout:10000}).stdout.toString().split("\n")[0],
      };
    } finally { await rm(directory, { recursive:true, force:true }); }
  }
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
    JSON.stringify({ png: png.toString("base64"), state, picked, movie }),
  );
} finally {
  await browser.close();
}
