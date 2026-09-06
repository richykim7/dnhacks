// Capture the deployed application. All writes are fulfilled inside this browser.
import { chromium } from "@playwright/test";
import { mkdir, writeFile, readFile } from "node:fs/promises";
import path from "node:path";
import { PNG } from "pngjs";
const base = process.env.CAPTURE_BASE_URL || "http://127.0.0.1:8765";
const out = process.env.CAPTURE_OUTPUT || path.resolve("video/public/capture");
await mkdir(out, { recursive: true });
let manifest = {
  source: base,
  viewport: { width: 1920, height: 1000 },
  captures: [],
  cursor: [],
  chapters: [],
  provenance:
    "Actual deployed frontend; browser-local staged setup and animated reveals; existing presentation history.",
};
const treeOnly = process.env.CAPTURE_FROM === "tree";
const typingOnly = process.env.CAPTURE_FROM === "typing";
const original = typingOnly
  ? JSON.parse(await readFile(path.join(out, "manifest.json"), "utf8"))
  : null;
if (typingOnly) {
  await writeFile(
    path.join(out, "manifest-before-typing.json"),
    JSON.stringify(original, null, 2),
  );
  manifest = structuredClone(original);
  manifest.captures = manifest.captures.filter(
    (s) => !s.note.includes("Typing") && s.note !== "Completed field",
  );
}
if (treeOnly) {
  manifest = JSON.parse(
    await readFile(path.join(out, "manifest.json"), "utf8"),
  );
  manifest.captures = manifest.captures.filter((c) => c.t < 86);
  manifest.cursor = manifest.cursor.filter((c) => c.t < 86);
}
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: manifest.viewport });
let staged = true,
  created = false,
  paperCount = 0;
const realProject = await (
  await page.request.get(base + "/api/projects/pdac-frozen")
).json();
const realPapers = await (
  await page.request.get(base + "/api/projects/pdac-frozen/papers")
).json();
manifest.health = await (
  await page.request.get(base + "/api/deployment/health")
).json();
page.on("pageerror", (e) => console.error("PAGE ERROR", e.message));
await page.route("**/api/**", async (route) => {
  const req = route.request(),
    u = new URL(req.url()),
    p = u.pathname;
  if (req.method() !== "GET") {
    if (p === "/api/projects") {
      created = true;
      await route.fulfill({
        json: {
          ...realProject,
          id: "pdac-frozen",
          name: "Pancreatic cancer",
          adopted: false,
        },
      });
      return;
    }
    if (p.endsWith("/papers/add")) {
      paperCount = 100;
      await route.fulfill({
        json: { project_id: "pdac-frozen", duplicates: [] },
      });
      return;
    }
    if (p.endsWith("/run")) {
      await route.fulfill({ json: { run_id: "pdac-frozen-investigation-03" } });
      return;
    }
    await route.fulfill({
      status: 409,
      json: { error: "Capture session is read-only" },
    });
    return;
  }
  if (staged && p === "/api/projects") {
    await route.fulfill({
      json: {
        projects: created
          ? [
              {
                ...realProject,
                id: "pdac-frozen",
                name: "Pancreatic cancer",
                has_kg: true,
                adopted: false,
              },
            ]
          : [],
      },
    });
    return;
  }
  if (staged && p === "/api/projects/pdac-frozen") {
    await route.fulfill({
      json: {
        ...realProject,
        name: "Pancreatic cancer",
        adopted: false,
        description:
          "Pancreatic cancer cell survival under abnormal cell division.",
        spec: {
          ...realProject.spec,
          scope:
            "Pancreatic cancer cell survival under abnormal cell division.",
        },
      },
    });
    return;
  }
  if (staged && p === "/api/projects/pdac-frozen/papers") {
    await route.fulfill({
      json: {
        ...realPapers,
        papers: realPapers.papers.slice(0, paperCount),
        total: paperCount,
      },
    });
    return;
  }
  await route.continue();
});
await page.addInitScript(() => {
  localStorage.setItem("dn-theme", "dark");
  localStorage.removeItem("dn-project");
});
const wait = (ms) => page.waitForTimeout(ms);
async function shot(t, note) {
  if (typingOnly) return;
  await page.evaluate(() => document.fonts.ready);
  const file = `app-${String(manifest.captures.length).padStart(4, "0")}.png`;
  await page.screenshot({ path: path.join(out, file) });
  manifest.captures.push({ t, file, note });
  await writeFile(
    path.join(out, "manifest.json"),
    JSON.stringify(manifest, null, 2),
  );
}
async function cursor(t, locator, click = false) {
  const b = await locator.boundingBox();
  if (!b) throw new Error("No cursor target at " + t);
  if (!typingOnly)
    manifest.cursor.push({
      t,
      x: b.x + b.width * 0.5,
      y: b.y + b.height * 0.5,
      click,
      target: await locator.innerText().catch(() => ""),
      bounds: b,
    });
  if (click) await locator.click();
}
async function type(t, duration, locator, text) {
  await cursor(t - 0.2, locator, true);
  const characters = Array.from(text);
  const baseShot = typingOnly ? original.captures.find((s) => s.t === t) : null;
  const originalBounds = typingOnly
    ? original.cursor.find((c) => Math.abs(c.t - (t - 0.2)) < 0.001).bounds
    : null;
  const bounds = await locator.boundingBox();
  if (
    typingOnly &&
    ["x", "y", "width", "height"].some(
      (k) => Math.abs(bounds[k] - originalBounds[k]) > 1,
    )
  ) {
    throw new Error(
      "Typing field layout changed at " +
        t +
        "; refusing to alter surrounding UI.",
    );
  }
  for (let i = 0; i <= characters.length; i++) {
    const prefix = characters.slice(0, i).join("");
    await locator.fill(prefix);
    const time = t + (duration * i) / characters.length;
    if (!typingOnly) {
      await shot(
        time,
        i === characters.length
          ? "Completed field"
          : "Typing in the actual form",
      );
      continue;
    }
    // Replace only the input interior, keeping every surrounding pixel unchanged.
    const clip = {
      x: Math.ceil(bounds.x) + 3,
      y: Math.ceil(bounds.y) + 3,
      width: Math.floor(bounds.width) - 6,
      height: Math.floor(bounds.height) - 6,
    };
    const field = PNG.sync.read(await page.screenshot({ clip, caret: "hide" }));
    const base = PNG.sync.read(await readFile(path.join(out, baseShot.file)));
    PNG.bitblt(field, base, 0, 0, field.width, field.height, clip.x, clip.y);
    const file = "typing-" + t + "-" + String(i).padStart(3, "0") + ".png";
    await writeFile(path.join(out, file), PNG.sync.write(base));
    manifest.captures.push({
      t: time,
      file,
      note:
        i === characters.length
          ? "Completed field"
          : "Typing in the actual form",
      typingStart: t,
      typingDuration: duration,
      typedLength: i,
      typedText: prefix,
      fieldClip: clip,
      baseFile: baseShot.file,
    });
  }
}
async function seek(value) {
  const slider = page.getByRole("slider", {
    name: "Activity playback position",
  });
  await slider.fill(String(Math.round(value)));
  await wait(90);
}
async function fit() {
  await wait(120);
  await page.evaluate(() => {
    const flow = [...document.querySelectorAll(".react-flow")].find(
      (e) => e.getBoundingClientRect().height > 100,
    );
    if (!flow) return;
    const viewport = flow.querySelector(".react-flow__viewport");
    const m = new DOMMatrix(getComputedStyle(viewport).transform),
      vr = viewport.getBoundingClientRect();
    const boxes = [...flow.querySelectorAll(".react-flow__node")]
      .filter((e) => getComputedStyle(e).display !== "none")
      .map((e) => {
        const r = e.getBoundingClientRect();
        return {
          x: (r.x - vr.x) / m.a,
          y: (r.y - vr.y) / m.a,
          w: r.width / m.a,
          h: r.height / m.a,
        };
      });
    if (!boxes.length) return;
    const x = Math.min(...boxes.map((b) => b.x)),
      y = Math.min(...boxes.map((b) => b.y)),
      w = Math.max(...boxes.map((b) => b.x + b.w)) - x,
      h = Math.max(...boxes.map((b) => b.y + b.h)) - y;
    const z = Math.min(
      (flow.clientWidth - 100) / w,
      (flow.clientHeight - 100) / h,
      1,
    );
    const tx = (flow.clientWidth - w * z) / 2 - x * z,
      ty = (flow.clientHeight - h * z) / 2 - y * z;
    viewport.style.transform =
      "translate(" + tx + "px, " + ty + "px) scale(" + z + ")";
  });
}

try {
  if (!treeOnly) {
    await page.goto(base + "/#library");
    await page
      .getByRole("button", { name: "New collection", exact: true })
      .waitFor();
    await wait(250);
    await shot(0, "Actual first-open library");
    await cursor(
      0,
      page.getByRole("button", { name: "New collection", exact: true }),
    );
    await cursor(
      5,
      page.getByRole("button", { name: "New collection", exact: true }),
      true,
    );
    await wait(250);
    await shot(5.4, "Create a literature collection");
    await type(7, 3, page.locator(".modal input").first(), "Pancreatic cancer");
    await type(
      11,
      9,
      page.locator(".modal textarea").first(),
      "Pancreatic cancer cell survival under abnormal cell division: metabolism, cellular stress, and the tumor environment.",
    );
    await cursor(
      22,
      page.getByRole("button", { name: "Create collection", exact: true }),
      true,
    );
    await wait(600);
    await shot(22.5, "Actual empty collection");
    await cursor(
      25,
      page.getByRole("button", { name: "Add papers", exact: true }),
      true,
    );
    await wait(250);
    await shot(25.4, "Add papers by DOI");
    await type(
      27,
      5,
      page.locator(".modal textarea").first(),
      "10.1016/j.devcel.2018.10.026\n10.1038/s41467-023-41840-3\n10.1101/gad.1700908",
    );
    const submit = page.locator('.add-papers-form button[type="submit"]');
    await cursor(34, submit, true);
    await wait(800);

    // The actual rows and their layout stay intact; animation reveals their arrival.
    const rows = page.locator(".paper-entry");
    const total = await rows.count();
    for (let i = 0; i <= 30; i++) {
      await page.evaluate(
        ({ i, total }) => {
          document.querySelectorAll(".paper-entry").forEach((r, j) => {
            r.style.opacity = String(
              Math.max(0, Math.min(1, ((i / 30) * total - j) * 0.6)),
            );
          });
        },
        { i, total },
      );
      await shot(37 + i * 0.38, "Real library rows arriving");
    }
    await page.evaluate(() =>
      document
        .querySelectorAll(".paper-entry")
        .forEach((r) => (r.style.opacity = "1")),
    );
    await cursor(49, page.locator(".paper-row").first(), true);
    await wait(500);
    await shot(49.5, "Read a full-text paper");
    staged = false;
    await page.goto(base + "/?project=pdac-frozen#knowledge");
    await page.locator(".react-flow__node").first().waitFor();
    await wait(1600);
    const fitAll = page.getByRole("button", { name: "Fit all", exact: true });
    if (await fitAll.count()) {
      await fitAll.click();
      await wait(900);
    }
    await shot(52, "Current knowledge graph");
    // Grow the actual rendered graph without inventing topology or node appearance.
    const nodes = await page.locator(".react-flow__node").count();
    const edges = await page.locator(".react-flow__edge").count();
    manifest.kg = { nodes, edges };
    const graphEdges = (
      await (
        await page.request.get(base + "/api/kg?complete=1&source=pdac-frozen")
      ).json()
    ).edges;
    const endpoints = Object.fromEntries(
      graphEdges.map((e) => [
        e.claim_id,
        { source: e.source, target: e.target },
      ]),
    );
    for (let i = 0; i <= 65; i++) {
      await page.evaluate(
        ({ i, nodes, endpoints }) => {
          const opacity = new Map();
          document.querySelectorAll(".react-flow__node").forEach((node, j) => {
            const value = Math.max(0, Math.min(1, (i / 65) * nodes - j));
            opacity.set(node.getAttribute("data-id"), value);
            node.style.opacity = String(value);
          });
          document.querySelectorAll(".react-flow__edge").forEach((edge) => {
            const pair = endpoints[edge.getAttribute("data-id")];
            edge.style.opacity = String(
              pair
                ? Math.min(
                    opacity.get(pair.source) || 0,
                    opacity.get(pair.target) || 0,
                  )
                : 0,
            );
          });
        },
        { i, nodes, endpoints },
      );
      await shot(52 + i * 0.25, "Actual knowledge graph growth");
    }
    await cursor(
      69,
      page
        .getByRole("button", { name: "New investigation", exact: true })
        .first(),
      true,
    );
    await wait(300);
    await shot(69.4, "Actual investigation launch dialog");
    await type(
      71,
      9,
      page.locator(".modal textarea").first(),
      "Which adaptive processes could allow pancreatic cancer cells with extra centrosomes to survive nutrient, stress and division challenges?",
    );
    if (typingOnly) {
      manifest.captures.sort((a, b) => a.t - b.t);
      await writeFile(
        path.join(out, "manifest.json"),
        JSON.stringify(manifest, null, 2),
      );
      await browser.close();
      console.log(
        "Updated single-character captures; all typing durations and other snapshots preserved.",
      );
      process.exit(0);
    }
    await cursor(
      83,
      page.getByRole("button", { name: "Start research", exact: true }),
      true,
    );
    await wait(1500);
  }
  staged = false;
  await page.goto(
    base + "/?project=pdac-frozen#investigations/pdac-frozen-investigation-03",
  );
  await page
    .getByRole("slider", { name: "Activity playback position" })
    .waitFor();
  await wait(900);
  const rail = page.getByRole("button", {
    name: "Collapse investigation list",
    exact: true,
  });
  if (await rail.count()) await rail.click();
  const max = Number(
    await page
      .getByRole("slider", { name: "Activity playback position" })
      .getAttribute("max"),
  );
  manifest.maxSequence = max;
  await seek(4);
  await fit();
  await shot(86, "First researcher");
  const root = page.locator(
    '.react-flow__node[data-id="pdac-frozen-investigation-03"] .agent-button',
  );
  await cursor(87, root, true);
  await wait(750);
  await shot(87.7, "Inspect first researcher");
  await seek(60);
  await wait(350);
  await shot(91, "First researcher evidence");
  const close = page.getByRole("button", {
    name: "Close researcher detail",
    exact: true,
  });
  if (await close.count()) await close.first().click();
  await seek(130);
  await fit();
  await shot(95, "First branches");
  const second = page.locator(
    '.react-flow__node[data-id="pdac-frozen-investigation-03~1"] .agent-button',
  );
  await cursor(96, second, true);
  await wait(750);
  await shot(96.7, "Inspect metabolic researcher");
  await seek(190);
  await wait(350);
  await shot(101, "Metabolic researcher evidence");
  if (await close.count()) await close.first().click();
  for (let i = 0; i <= 90; i++) {
    const progress = i / 90,
      sequence = 190 + (max - 190) * Math.pow(progress, 1.9);
    await seek(sequence);
    await fit();
    await shot(104 + i * 0.23, "Accelerating actual search-tree history");
  }
  await seek(max);
  await fit();
  const target = page.locator(
    '.react-flow__node[data-id="pdac-frozen-investigation-03~1~1~1~1~1~1~1~1~1"] .agent-button',
  );
  await cursor(126, target, true);
  await wait(800);
  await shot(126.8, "HA–CD44 target researcher");
  await shot(131, "HA–CD44 target evidence");
  if (await close.count()) await close.first().click();
  await cursor(
    134,
    page.getByRole("tab", { name: "Candidates", exact: true }),
    true,
  );
  await wait(450);
  await shot(134.5, "Actual candidate list");
  await page.getByRole("button", { name: "Latest state", exact: true }).click();
  await cursor(
    136,
    page
      .locator(".candidate-queue .experiment-row")
      .filter({ hasText: "HA–CD44 supports division tolerance" }),
    true,
  );
  await wait(700);
  await shot(136.7, "Open HA–CD44 candidate record");
  const review = page.getByRole("button", {
    name: "Review candidate",
    exact: true,
  });
  if (await review.count()) {
    await review.scrollIntoViewIfNeeded();
    await cursor(138, review, true);
    await wait(600);
    await page.locator(".candidate-review").scrollIntoViewIfNeeded();
    await shot(139, "HA–CD44 candidate and evidence");
  }
  await shot(141, "Candidates before paper reveal");
  await writeFile(
    path.join(out, "manifest.json"),
    JSON.stringify(manifest, null, 2),
  );
  console.log(
    JSON.stringify({
      out,
      captures: manifest.captures.length,
      kg: manifest.kg,
      max,
    }),
  );
} finally {
  if (!typingOnly)
    await writeFile(
      path.join(out, "manifest.json"),
      JSON.stringify(manifest, null, 2),
    );
  await browser.close();
}
