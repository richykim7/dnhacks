import { createServer } from "vite";
import react from "@vitejs/plugin-react";
import { chromium } from "@playwright/test";
import { PNG } from "pngjs";
import { mkdir, writeFile, readFile, realpath } from "node:fs/promises";
import path from "node:path";
const root = process.cwd(),
  output = process.env.FRAME_CHECK_OUTPUT || path.join(root, "out/frame-check");
await mkdir(output, { recursive: true });
const server = await createServer({
  configFile: false,
  root,
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5198,
    fs: {
      allow: [
        path.resolve(".."),
        await realpath(path.join(root, "public/capture")),
      ],
    },
  },
});
const results = [],
  errors = [],
  pixelChecks = [];
let browser;
try {
  await server.listen();
  const port = server.httpServer.address().port;
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
  });
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://127.0.0.1:" + port + "/check.html");
  await page.waitForFunction(() => typeof window.seekVideo === "function");
  const times = [
    0, 3, 5.5, 7.5, 9.5, 12, 16, 20, 22.7, 25.6, 28, 31, 34, 35.5, 36.9, 37,
    37.1, 38, 42, 47, 49.7, 51.9, 52, 52.1, 52.2, 55, 59, 63, 67, 69.5, 72, 76,
    80, 83, 86.2, 88, 91.5, 95.3, 97, 101.5, 104.3, 107, 110, 113, 116, 119,
    122, 124.8, 127.5, 131, 134.7, 137, 139.7, 143, 146.3, 148, 151, 155, 159,
    160.6, 164, 169,
  ];
  for (const t of times) {
    const frame = Math.round(t * 30);
    await page.evaluate((f) => window.seekVideo(f), frame);
    await page.waitForFunction((f) => window.videoFrame === f, frame);
    await page.waitForFunction(() =>
      [...document.images].every((i) => i.complete && i.naturalWidth > 0),
    );
    await page.evaluate(
      () =>
        new Promise((r) =>
          requestAnimationFrame(() => requestAnimationFrame(r)),
        ),
    );
    const file = "frame-" + String(frame).padStart(4, "0") + ".png";
    await page.screenshot({ path: path.join(output, file) });
    const data = await page.evaluate(() => ({
      caption:
        document.querySelector(".capture-caption b")?.textContent ||
        document.querySelector(".paper-heading")?.textContent,
      image: document
        .querySelector(".captured-ui:last-of-type")
        ?.getAttribute("src"),
      overflow: [
        ...document.querySelectorAll(
          ".capture-caption b,.paper-story,.evidence-provenance",
        ),
      ]
        .filter((e) => e.scrollWidth > e.clientWidth + 2)
        .map((e) => e.className),
    }));
    if (data.overflow.length) errors.push("Overflow at " + t);
    results.push({ t, frame, file, ...data });
  }
  // Pixel comparisons prove that the rendered app frame is the captured current UI.
  for (const t of [0, 23, 49.7, 91.5, 101.5, 131, 143]) {
    await page.evaluate((f) => window.seekVideo(f), Math.round(t * 30));
    await page.waitForFunction(
      (f) => window.videoFrame === f,
      Math.round(t * 30),
    );
    await page.waitForFunction(() =>
      [...document.images].every((i) => i.complete && i.naturalWidth > 0),
    );
    const image = page.locator(".captured-ui").last();
    const src = await image.getAttribute("src");
    await page.addStyleTag({
      content: ".capture-pointer{visibility:hidden!important}",
    });
    const actual = PNG.sync.read(
      await page.screenshot({
        clip: { x: 0, y: 0, width: 1920, height: 1000 },
      }),
    );
    const source = PNG.sync.read(
      await readFile(
        path.join(
          root,
          "public",
          decodeURIComponent(new URL(src, "http://x").pathname),
        ),
      ),
    );
    const match = actual.data.equals(source.data);
    pixelChecks.push({ t, src, match });
    if (!match) errors.push("Captured UI pixels differ at " + t);
  }
  // Verify deterministic seeking, including the actual paper asset.
  await page.evaluate(() => window.seekVideo(4530));
  await page.waitForFunction(() => window.videoFrame === 4530);
  await page.waitForFunction(() =>
    [...document.images].every((i) => i.complete && i.naturalWidth > 0),
  );
  const a = await page.screenshot();
  await page.evaluate(() => window.seekVideo(5070));
  await page.waitForFunction(() => window.videoFrame === 5070);
  await page.evaluate(() => window.seekVideo(4530));
  await page.waitForFunction(() => window.videoFrame === 4530);
  await page.waitForFunction(() =>
    [...document.images].every((i) => i.complete && i.naturalWidth > 0),
  );
  if (!a.equals(await page.screenshot()))
    errors.push("Paper reveal changed after backwards seek");
  await writeFile(
    path.join(output, "report.json"),
    JSON.stringify(
      { framesChecked: results.length, pixelChecks, errors, results },
      null,
      2,
    ),
  );
  await writeFile(
    path.join(output, "index.html"),
    "<!doctype html><title>Latent Nature video frames</title><style>body{background:#142019;color:#c5dfce;font:16px sans-serif;padding:24px}main{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}figure{margin:0}img{width:100%}figcaption{padding:8px}</style><h1>Latent Nature: " +
      results.length +
      " frames</h1><main>" +
      results
        .map(
          (r) =>
            '<figure><a href="' +
            r.file +
            '"><img src="' +
            r.file +
            '"></a><figcaption>' +
            r.t +
            "s — " +
            r.caption +
            "</figcaption></figure>",
        )
        .join("") +
      "</main>",
  );
  console.log(
    JSON.stringify({ output, frames: results.length, pixelChecks, errors }),
  );
  if (errors.length) process.exitCode = 1;
} finally {
  await browser?.close();
  await server.close();
}
