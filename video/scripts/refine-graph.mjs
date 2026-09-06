import { chromium } from "@playwright/test";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
const base = process.env.CAPTURE_BASE_URL || "http://127.0.0.1:8765";
const out = process.env.CAPTURE_OUTPUT || path.resolve("public/capture");
const manifest = JSON.parse(
  await readFile(path.join(out, "manifest.json"), "utf8"),
);
const original = structuredClone(manifest);
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: manifest.viewport });
  await page.route("**/api/**", (route) =>
    route.request().method() === "GET"
      ? route.continue()
      : route.fulfill({ status: 409, json: { error: "Read-only capture" } }),
  );
  await page.addInitScript(() => localStorage.setItem("dn-theme", "dark"));
  await page.goto(base + "/?project=pdac-frozen#knowledge");
  await page.locator(".react-flow__node").first().waitFor();
  await page.waitForTimeout(1200);
  const fit = page.getByRole("button", { name: "Fit all", exact: true });
  if (await fit.count()) await fit.click();
  await page.waitForTimeout(800);
  await page.evaluate(() => document.fonts.ready);
  const graph = await (
    await page.request.get(base + "/api/kg?complete=1&source=pdac-frozen")
  ).json();
  const edgeMap = Object.fromEntries(
    graph.edges.map((e) => [
      e.claim_id,
      { source: e.source, target: e.target },
    ]),
  );
  const topology = await page.evaluate((edgeMap) => {
    const nodes = [...document.querySelectorAll(".react-flow__node")];
    const ids = new Set(nodes.map((n) => n.getAttribute("data-id")));
    const adjacency = new Map([...ids].map((id) => [id, new Set()]));
    for (const e of Object.values(edgeMap))
      if (ids.has(e.source) && ids.has(e.target)) {
        adjacency.get(e.source).add(e.target);
        adjacency.get(e.target).add(e.source);
      }
    const order = [],
      seen = new Set(),
      queue = ["LOCALPHENO:centrosome_amplification"];
    while (order.length < ids.size) {
      while (queue.length) {
        const id = queue.shift();
        if (!ids.has(id) || seen.has(id)) continue;
        seen.add(id);
        order.push(id);
        queue.push(...adjacency.get(id));
      }
      const next = [...ids]
        .filter((id) => !seen.has(id))
        .sort((a, b) => adjacency.get(b).size - adjacency.get(a).size)[0];
      if (next) queue.push(next);
    }
    window.graphReveal = { edgeMap, order };
    return {
      nodes: ids.size,
      edges: document.querySelectorAll(".react-flow__edge").length,
    };
  }, edgeMap);
  const shots = [],
    checks = [];
  for (let i = 0; i <= 65; i++) {
    const counts = await page.evaluate((progress) => {
      const { edgeMap, order } = window.graphReveal;
      const opacity = new Map(
        order.map((id, index) => [
          id,
          Math.max(0, Math.min(1, progress * order.length - index)),
        ]),
      );
      document
        .querySelectorAll(".react-flow__node")
        .forEach(
          (n) =>
            (n.style.opacity = String(
              opacity.get(n.getAttribute("data-id")) || 0,
            )),
        );
      let visibleEdges = 0,
        orphanEdges = 0;
      document.querySelectorAll(".react-flow__edge").forEach((el) => {
        const edge = edgeMap[el.getAttribute("data-id")];
        const a = edge ? opacity.get(edge.source) || 0 : 0,
          b = edge ? opacity.get(edge.target) || 0 : 0;
        const value = Math.min(a, b);
        el.style.opacity = String(value);
        if (value > 0) {
          visibleEdges++;
          if (!a || !b) orphanEdges++;
        }
      });
      return {
        visibleNodes: [...opacity.values()].filter((x) => x > 0).length,
        visibleEdges,
        orphanEdges,
      };
    }, i / 65);
    if (counts.orphanEdges)
      throw new Error("Edge appears before its endpoints");
    const file = "kg-connected-" + String(i).padStart(3, "0") + ".png";
    await page.screenshot({ path: path.join(out, file) });
    shots.push({
      t: 52 + i * 0.25,
      file,
      note: "Actual knowledge graph growth",
    });
    checks.push({ t: 52 + i * 0.25, ...counts });
  }
  if (checks.at(-1).visibleEdges !== topology.edges)
    throw new Error("Not all original graph edges were restored");
  manifest.captures = manifest.captures
    .filter((s) => s.t < 52 || s.t >= 69)
    .concat(shots)
    .sort((a, b) => a.t - b.t);
  const outside = (d) =>
    d.captures.filter((s) => s.t < 52 || s.t >= 69).sort((a, b) => a.t - b.t);
  if (JSON.stringify(outside(manifest)) !== JSON.stringify(outside(original)))
    throw new Error("Non-graph captures changed");
  if (JSON.stringify(manifest.cursor) !== JSON.stringify(original.cursor))
    throw new Error("Cursor changed");
  await writeFile(
    path.join(out, "manifest-before-graph.json"),
    JSON.stringify(original, null, 2),
  );
  await writeFile(
    path.join(out, "graph-validation.json"),
    JSON.stringify(
      { topology, checks, otherCapturesUnchanged: true, cursorUnchanged: true },
      null,
      2,
    ),
  );
  await writeFile(
    path.join(out, "manifest.json"),
    JSON.stringify(manifest, null, 2),
  );
  console.log(
    JSON.stringify({ topology, frames: shots.length, orphanEdges: 0 }),
  );
} finally {
  await browser.close();
}
