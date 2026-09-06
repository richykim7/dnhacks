import { createServer } from "vite";
import react from "@vitejs/plugin-react";
import { chromium } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
const root = process.cwd(),
  output = path.join(root, "out/frame-check");
await mkdir(output, { recursive: true });
const server = await createServer({
  configFile: false,
  root,
  plugins: [react()],
  resolve: {
    alias: [
      { find: "@", replacement: path.resolve("../frontend/src") },
      ...[
        "react",
        "react-dom",
        "lucide-react",
        "@radix-ui/react-dialog",
        "@radix-ui/react-slot",
        "class-variance-authority",
        "clsx",
        "tailwind-merge",
      ].map((name) => ({
        find: name,
        replacement: path.resolve("node_modules", name),
      })),
    ],
  },
  server: { host: "127.0.0.1", port: 0, fs: { allow: [path.resolve("..")] } },
});
let browser;
const errors = [];
const results = [];
try {
  await server.listen();
  const address = server.httpServer.address();
  browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  const page = await browser.newPage({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`http://127.0.0.1:${address.port}/check.html`);
  await page.waitForFunction(() => typeof window.seekVideo === "function");
  await page.evaluate(() => document.fonts.ready);
  const times = [
    0.5, 3, 5.6, 7.5, 9.5, 12, 16, 20, 23.8, 26, 29, 33, 38, 41, 43, 47, 52, 57,
    59.5, 61, 65, 69.5, 71, 73, 76, 78, 80, 84, 88, 91, 94, 98, 102, 106, 109,
    113, 118, 121, 125, 129, 131, 135, 137.5,
  ];
  for (const seconds of times) {
    const frame = Math.round(seconds * 30);
    await page.evaluate((f) => window.seekVideo(f), frame);
    await page.waitForFunction((f) => window.videoFrame === f, frame);
    await page.evaluate(
      () =>
        new Promise((r) =>
          requestAnimationFrame(() => requestAnimationFrame(r)),
        ),
    );
    const filename = `frame-${String(frame).padStart(4, "0")}.png`;
    await page.screenshot({ path: path.join(output, filename) });
    const state = await page.evaluate(() => ({
      text: document.body.innerText,
      caption: document.querySelector(".movie-caption")?.textContent,
      nodes: [...document.querySelectorAll(".movie-agent")].filter(
        (el) => +getComputedStyle(el).opacity > 0.5,
      ).length,
      cursor: document.querySelector(".movie-cursor")
        ? (() => {
            const r = document
              .querySelector(".movie-cursor")
              .getBoundingClientRect();
            return { x: r.x, y: r.y };
          })()
        : null,
      overflow: [
        ...document.querySelectorAll(
          ".movie-caption,.movie-modal-title,.field-box,.paper-reveal h2,.research-detail h2",
        ),
      ]
        .filter(
          (el) =>
            el.scrollWidth > el.clientWidth + 2 ||
            el.scrollHeight > el.clientHeight + 2,
        )
        .map((el) => el.className),
    }));
    if (state.overflow.length)
      errors.push(`Frame ${frame} overflows: ${state.overflow.join(",")}`);
    if (
      state.cursor &&
      (state.cursor.x < 0 ||
        state.cursor.x > 1920 ||
        state.cursor.y < 0 ||
        state.cursor.y > 1080)
    )
      errors.push(`Frame ${frame}: cursor outside canvas`);
    results.push({ seconds, frame, filename, ...state });
  }
  const clicks = [
    [162, '.welcome-empty .button', 0],
    [284, '.movie-modal .field-box', 0],
    [391, '.movie-modal .field-box', 1],
    [709, '.movie-modal .button', 0],
    [794, '.movie-heading .button', 0],
    [1207, '.movie-header nav>div', 2],
    [1775, '.graph-top .button', 0],
    [1834, '.movie-modal .field-box', 0],
    [2116, '.movie-modal .button', 0],
    [2215, '.movie-agent', 0],
    [2352, '.movie-agent', 1],
  ];
  const clickResults=[];
  for(const [frame,selector,index] of clicks){
    await page.evaluate(f=>window.seekVideo(f),frame);
    await page.waitForFunction(f=>window.videoFrame===f,frame);
    const target=await page.locator(selector).nth(index).boundingBox();
    const cursor=await page.locator('.movie-cursor').boundingBox();
    const hit=cursor&&target&&cursor.x+4>=target.x&&cursor.x+4<=target.x+target.width&&cursor.y+3>=target.y&&cursor.y+3<=target.y+target.height;
    clickResults.push({frame,selector,index,hit,target,cursor});
    if(!hit)errors.push(`Cursor misses ${selector}[${index}] at frame ${frame}`);
    await page.screenshot({path:path.join(output,`click-${frame}.png`)});
  }
    // Seek backwards and verify the frame is independent of playback history.
  await page.evaluate(() => window.seekVideo(990));
  await page.waitForFunction(() => window.videoFrame === 990);
  await page.evaluate(
    () =>
      new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))),
  );
  const replay = await page.screenshot();
  const { readFile } = await import("node:fs/promises");
  if (!replay.equals(await readFile(path.join(output, "frame-0990.png"))))
    errors.push("Frame 990 changes after backwards seeking");
  await writeFile(
    path.join(output, "report.json"),
    JSON.stringify({ framesChecked: results.length, errors, clickResults, results }, null, 2),
  );
  await writeFile(
    path.join(output, "index.html"),
    `<!doctype html><title>Walkthrough frame review</title><style>body{background:#101914;color:#cde4d4;font:16px sans-serif;padding:24px}main{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}img{width:100%}figure{margin:0}figcaption{padding:8px}</style><h1>${results.length} inspected frames</h1><p>${errors.length} errors</p><main>${results.map((r) => `<figure><a href="${r.filename}"><img src="${r.filename}"></a><figcaption>${r.seconds}s · ${r.caption || "Closing sequence"}</figcaption></figure>`).join("")}</main>`,
  );
  console.log(
    JSON.stringify({ output, framesChecked: results.length, errors }),
  );
  if (errors.length) process.exitCode = 1;
} finally {
  await browser?.close();
  await server.close();
}
