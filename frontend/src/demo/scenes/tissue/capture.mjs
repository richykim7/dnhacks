// Standalone visual capture: private Vite server, no backend and no production data.
import { createServer } from "vite";
import { createServer as createHttpServer } from "node:http";
import { chromium } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { mkdir, readFile } from "node:fs/promises";
const here = dirname(fileURLToPath(import.meta.url));
const out = resolve(here, "assets");
await mkdir(out, { recursive: true });
const server = await createServer({
  configFile: false,
  root: resolve(here, "../../../../"),
  cacheDir: "/tmp/tissue-demo-vite-cache",
  optimizeDeps: { entries: ["src/demo/scenes/tissue/preview.html"] },
  server: { middlewareMode: true, hmr: false },
  logLevel: "error",
});
const http = createHttpServer(server.middlewares);
await new Promise((resolve) => http.listen(0, "127.0.0.1", resolve));
const url = `http://127.0.0.1:${http.address().port}/`;
let browser;
try {
  browser = await chromium.launch({
    headless: true,
    args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
  });
  const page = await browser.newPage({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
  });
  const errors = [];
  page.on("pageerror", (error) => errors.push(String(error)));
  await page.goto(`${url}src/demo/scenes/tissue/preview.html?time=13`);
  await page.waitForSelector("canvas");
  await page.waitForTimeout(1800);
  for (const t of [0, 8, 13, 18]) {
    await page.evaluate((t) => window.setTissueTime(t), t);
    await page.waitForTimeout(250);
    await page.screenshot({ path: resolve(out, `tissue-${t}s.png`) });
  }
  // Exact-time frame sequence can be encoded at 12 fps; rendering speed does not set animation time.
  if (process.argv.includes("--clip")) {
    const frames = resolve(out, "frames");
    await mkdir(frames, { recursive: true });
    for (let frame = 0; frame <= 216; frame++) {
      await page.evaluate((t) => window.setTissueTime(t), frame / 12);
      await page.waitForTimeout(70);
      await page.screenshot({
        path: resolve(frames, `${String(frame).padStart(4, "0")}.png`),
      });
    }
  }
  // Scrubbing backwards must reproduce the same rendered pose.
  await page.evaluate(() => window.setTissueTime(13));
  await page.waitForTimeout(250);
  await page.screenshot({ path: resolve(out, "tissue-repeat.png") });
  const first = await readFile(resolve(out, "tissue-13s.png"));
  const repeat = await readFile(resolve(out, "tissue-repeat.png"));
  if (!first.equals(repeat))
    throw new Error("Backward seek did not reproduce the 13-second image");
  if (errors.length) throw new Error(errors.join("\n"));
  console.log(
    "Captured 1920x1080 keyframes; no browser errors. Renderer: SwiftShader.",
  );
} finally {
  await browser?.close();
  await server.close();
  await new Promise((resolve) => http.close(resolve));
}
