import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const path = process.env.KNOWLEDGE_REVIEW_SNAPSHOT;
const graph = path ? JSON.parse(readFileSync(path, "utf8")) : null;
test.skip(!graph, "Requires local read-only complete corpus snapshot");
test("complete knowledge graph default focus and fit-all visual review", async ({
  page,
}) => {
  test.setTimeout(180000); // Complete-graph traces include thousands of SVG records.
  await page.setViewportSize({ width: 1920, height: 1080 });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/api/**", (route) => {
    const url = new URL(route.request().url());
    expect(route.request().method()).toBe("GET");
    if (url.pathname === "/api/projects")
      return route.fulfill({
        json: {
          projects: [
            {
              id: graph.source,
              name: "Pancreatic cancer",
              status: "ready",
              has_kg: true,
            },
          ],
        },
      });
    if (url.pathname === "/api/kg") {
      const claim = url.searchParams.get("claim");
      if (claim) return route.fulfill({ json: graph._details[claim] });
      expect(url.searchParams.get("complete")).toBe("1");
      expect(url.searchParams.has("limit")).toBe(false);
      const status = url.searchParams.get("status");
      const edges = status
        ? graph.edges.filter((e: any) => e.status === status)
        : graph.edges;
      const ids = new Set(edges.flatMap((e: any) => [e.source, e.target]));
      return route.fulfill({
        json: {
          ...graph,
          edges,
          nodes: graph.nodes.filter((n: any) => ids.has(n.id)),
          shown: edges.length,
          matched: edges.length,
        },
      });
    }
    return route.fulfill({ json: [] });
  });
  await page.goto(`/?project=${graph.source}&sceneReview=1#knowledge`);
  const loaded = () =>
    page.evaluate(() => {
      const review = (window as any).knowledgeReview;
      if (!review) return null;
      return {
        nodes: review.nodes().length,
        edges: review.edges().length,
        uniqueNodes: new Set(review.nodes().map((n: any) => n.id)).size,
        uniqueEdges: new Set(review.edges().map((e: any) => e.id)).size,
      };
    });
  await expect.poll(loaded, { timeout: 30000 }).toEqual({
    nodes: graph.summary.entities,
    edges: graph.total_claims,
    uniqueNodes: graph.summary.entities,
    uniqueEdges: graph.total_claims,
  });
  expect(graph.edges.length).toBe(graph.total_claims);
  await page.waitForTimeout(1200);
  const view = page.locator(".react-flow__viewport");
  if (process.env.KNOWLEDGE_CONNECTED_PREVIEW) {
    const incident = new Map<string, Set<string>>();
    for (const e of graph.edges)
      for (const id of new Set([e.source, e.target])) {
        if (!incident.has(id as string)) incident.set(id as string, new Set());
        incident.get(id as string)!.add(e.claim_id);
      }
    const leaves = new Set(
      [...incident].filter(([, ids]) => ids.size === 1).map(([id]) => id),
    );
    const visibleEdges = graph.edges.filter(
      (e: any) => !leaves.has(e.source) && !leaves.has(e.target),
    );
    await page.screenshot({
      path: test.info().outputPath("knowledge-connected-default.png"),
    });
    await page.getByRole("button", { name: "Fit all", exact: true }).click();
    await page.waitForTimeout(600);
    await expect(page.locator(".react-flow__node")).toHaveCount(
      graph.nodes.length - leaves.size,
    );
    await expect(page.locator(".react-flow__edge")).toHaveCount(
      visibleEdges.length,
    );
    await page.screenshot({
      path: test.info().outputPath("knowledge-connected.png"),
    });
    console.log(
      `Preview: ${graph.nodes.length - leaves.size} entities, ${visibleEdges.length} claims; hidden ${leaves.size} entities, ${graph.edges.length - visibleEdges.length} claims`,
    );
    const threshold = page.getByRole("slider", {
      name: "Minimum connected claims",
      exact: true,
    });
    await threshold.focus();
    await threshold.press("Home");
    await threshold.press("ArrowRight");
    await threshold.press("ArrowRight");
    await expect(threshold).toHaveValue("3");
    const hiddenAtThree = new Set(
      [...incident].filter(([, ids]) => ids.size < 3).map(([id]) => id),
    );
    const edgesAtThree = graph.edges.filter(
      (e: any) => !hiddenAtThree.has(e.source) && !hiddenAtThree.has(e.target),
    );
    await expect
      .poll(() =>
        page.evaluate(
          () =>
            (window as any).knowledgeReview
              .nodes()
              .filter((n: any) => !n.hidden).length,
        ),
      )
      .toBe(graph.nodes.length - hiddenAtThree.size);
    await page.getByRole("button", { name: "Fit all", exact: true }).click();
    await page.waitForTimeout(600);
    await expect(page.locator(".react-flow__node")).toHaveCount(
      graph.nodes.length - hiddenAtThree.size,
    );
    await expect(page.locator(".react-flow__edge")).toHaveCount(
      edgesAtThree.length,
    );
    await page.screenshot({
      path: test.info().outputPath("knowledge-slider.png"),
    });
    console.log(
      `Minimum3: ${graph.nodes.length - hiddenAtThree.size} entities, ${edgesAtThree.length} claims`,
    );
    await page
      .getByRole("spinbutton", { name: "Minimum connected claims value" })
      .fill("1");
    await page.getByRole("button", { name: "Fit all", exact: true }).click();
    await expect(page.locator(".react-flow__node")).toHaveCount(
      graph.nodes.length,
    );
    await expect(page.locator(".react-flow__edge")).toHaveCount(
      graph.edges.length,
    );
    return;
  }
  await page
    .getByRole("spinbutton", { name: "Minimum connected claims value" })
    .fill("1");
  const defaultTransform = await view.getAttribute("style");
  await page.screenshot({ path: test.info().outputPath("knowledge.png") });
  await page.getByRole("button", { name: "Fit all", exact: true }).click();
  await page.waitForTimeout(600);
  expect(await view.getAttribute("style")).not.toBe(defaultTransform);
  await page.screenshot({ path: test.info().outputPath("knowledge-all.png") });
  await expect(page.locator(".react-flow__node")).toHaveCount(
    graph.summary.entities,
    { timeout: 30000 },
  );
  await expect(page.locator(".react-flow__edge")).toHaveCount(
    graph.total_claims,
    { timeout: 30000 },
  );
  // No graph ID is removed by camera motion; bounding boxes all fit after the explicit action.
  const map = await page.locator(".relationship-map").boundingBox();
  const outside = await page.locator(".react-flow__node").evaluateAll(
    (ns, box: any) =>
      ns.filter((n) => {
        const r = n.getBoundingClientRect();
        return (
          r.left < box.x - 1 ||
          r.right > box.x + box.width + 1 ||
          r.top < box.y - 1 ||
          r.bottom > box.y + box.height + 1
        );
      }).length,
    map,
  );
  expect(outside).toBe(0);
  await page
    .getByLabel("Claim status", { exact: true })
    .selectOption("reported");
  await expect
    .poll(async () => (await loaded())?.edges, { timeout: 30000 })
    .toBe(graph.status_counts.reported);
  await page.getByLabel("Claim status", { exact: true }).selectOption("");
  await expect
    .poll(async () => (await loaded())?.edges, { timeout: 30000 })
    .toBe(graph.total_claims);
  await page.getByRole("button", { name: "Fit all", exact: true }).click();
  await expect(page.locator(".react-flow__edge")).toHaveCount(
    graph.total_claims,
    { timeout: 30000 },
  );
  // Open this exact source through its graph edge; list browsing has separate focused coverage.
  await page
    .locator(`.react-flow__edge[data-id="${graph.edges[0].claim_id}"]`)
    .dispatchEvent("click");
  await expect(page.getByLabel("Relationship evidence")).toBeVisible();
  await expect(page.locator(".source-evidence").first()).toBeVisible();
  const scroll = page.locator(".evidence-inspector .detail-scroll");
  await scroll.evaluate((e) => {
    e.scrollTop = e.scrollHeight;
  });
  expect(await scroll.evaluate((e) => e.scrollTop)).toBeGreaterThan(0);
  await page.keyboard.press("Escape");
  await expect(page.getByLabel("Relationship evidence")).toHaveCount(0);
  expect(errors).toEqual([]);
});
