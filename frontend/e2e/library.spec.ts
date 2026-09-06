import { test, expect, type Page } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";

// Opt-in review against a read-only snapshot of an existing corpus. No literature
// or local data paths are checked in. The normal harness still owns all servers.
// LIBRARY_REVIEW_SNAPSHOT=/tmp/library-review.json npm run e2e -- e2e/library.spec.ts
const snapshotPath = process.env.LIBRARY_REVIEW_SNAPSHOT;
const snapshot = snapshotPath
  ? JSON.parse(readFileSync(snapshotPath, "utf8"))
  : null;

test.skip(
  !snapshot,
  "Set LIBRARY_REVIEW_SNAPSHOT to a real read-only corpus snapshot",
);

async function serveSnapshot(
  page: Page,
  state: "ready" | "empty" | "error" = "ready",
) {
  const writes: string[] = [];
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() !== "GET") {
      writes.push(`${request.method()} ${path}`);
      return route.fulfill({
        status: 405,
        json: { error: "Read-only review" },
      });
    }
    const base = `/api/projects/${snapshot.project.id}`;
    if (path === "/api/projects")
      return route.fulfill({ json: { projects: [snapshot.project] } });
    if (path === base) return route.fulfill({ json: snapshot.project });
    if (path === `${base}/papers`) {
      if (state === "error")
        return route.fulfill({
          status: 503,
          json: { error: "Corpus could not be read" },
        });
      return route.fulfill({
        json: state === "empty" ? { papers: [], total: 0 } : snapshot.list,
      });
    }
    if (snapshot.assets?.[path])
      return route.fulfill({ path: snapshot.assets[path] });
    if (path.startsWith(`${base}/papers/`)) {
      const paperId = decodeURIComponent(path.slice(`${base}/papers/`.length));
      return route.fulfill({ json: snapshot.details[paperId] });
    }
    if (path.endsWith("/kg"))
      return route.fulfill({
        json: { n_papers: snapshot.list.total, n_claims: 0 },
      });
    if (path.endsWith("/documents"))
      return route.fulfill({ json: { documents: [] } });
    return route.fulfill({ json: [] });
  });
  await page.goto(
    `/?project=${encodeURIComponent(snapshot.project.id)}#library`,
  );
  return writes;
}

test("real corpus browser, search, year filter, reader and responsive review", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const writes = await serveSnapshot(page);
  const rows = page.locator(".paper-row");
  await expect(rows).toHaveCount(snapshot.list.total);
  await page.evaluate(() => document.fonts.ready);
  const fontDiagnostics = await page.evaluate(() => ({
    html: getComputedStyle(document.documentElement).fontFamily,
    body: getComputedStyle(document.body).fontFamily,
    row: getComputedStyle(document.querySelector(".paper-row")!).fontFamily,
    faces: [...document.fonts].map((font) => ({
      family: font.family,
      status: font.status,
    })),
  }));
  writeFileSync(
    test.info().outputPath("font-diagnostics.json"),
    JSON.stringify(fontDiagnostics, null, 2),
  );
  await expect(page.getByRole("button", { name: "Save settings" })).toHaveCount(
    0,
  );
  await page.screenshot({
    path: test.info().outputPath("library-100-dark.png"),
    fullPage: true,
  });
  await rows.last().scrollIntoViewIfNeeded();
  await expect(rows.last()).toBeVisible();
  const first = snapshot.list.papers[0];
  await page.getByLabel("Search papers", { exact: true }).fill(first.title);
  await expect(rows).toHaveCount(1);
  await page
    .getByLabel("Search papers", { exact: true })
    .fill("unmatched-paper-query-xyz");
  await expect(rows).toHaveCount(0);
  await page.screenshot({
    path: test.info().outputPath("library-search-empty.png"),
    fullPage: true,
  });
  await page.getByLabel("Search papers", { exact: true }).fill("");
  const year = String(first.year);
  await page
    .getByRole("combobox", { name: "Publication year" })
    .selectOption(year);
  await expect(rows).toHaveCount(
    snapshot.list.papers.filter((paper: any) => String(paper.year) === year)
      .length,
  );
  await page
    .getByRole("combobox", { name: "Publication year" })
    .selectOption({ index: 0 });
  await page
    .getByRole("combobox", { name: "Topic" })
    .selectOption(first.category);
  await expect(rows).toHaveCount(
    snapshot.list.papers.filter(
      (paper: any) => paper.category === first.category,
    ).length,
  );
  await page
    .getByRole("combobox", { name: "Topic" })
    .selectOption({ index: 0 });
  await page
    .getByRole("combobox", { name: "Text availability" })
    .selectOption("full");
  await expect(rows).toHaveCount(
    snapshot.list.papers.filter(
      (paper: any) => paper.has_text && paper.is_full_text,
    ).length,
  );
  await page
    .getByRole("combobox", { name: "Text availability" })
    .selectOption("figures");
  await expect(rows).toHaveCount(
    snapshot.list.papers.filter((paper: any) => paper.figure_count > 0).length,
  );
  await page
    .getByRole("combobox", { name: "Text availability" })
    .selectOption({ index: 0 });
  await page
    .getByRole("combobox", { name: "Sort papers" })
    .selectOption("title");
  const alphabetical = [...snapshot.list.papers].sort((a: any, b: any) =>
    a.title.localeCompare(b.title),
  );
  await expect(rows.first().locator("strong")).toHaveText(
    alphabetical[0].title,
  );
  await page
    .getByRole("combobox", { name: "Sort papers" })
    .selectOption("newest");
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await page.screenshot({
    path: test.info().outputPath("library-100-light.png"),
    fullPage: true,
  });
  await rows.filter({ hasText: first.title }).click();
  const reader = page.getByRole("region", { name: "Paper reader" });
  await expect(reader).toBeVisible();
  await expect(
    reader.getByRole("heading", { name: first.title, exact: true }),
  ).toBeVisible();
  await expect(reader.locator(".paper-fulltext")).toBeVisible();
  await page.screenshot({
    path: test.info().outputPath("library-reader-light.png"),
    fullPage: true,
  });
  await reader
    .getByRole("button", { name: "Expand reader", exact: true })
    .click();
  await expect(page.locator(".paper-list")).toBeHidden();
  await reader
    .getByRole("button", { name: "Show paper list", exact: true })
    .click();
  await expect(page.locator(".paper-list")).toBeVisible();
  await reader.press("Escape");
  await expect(rows.filter({ hasText: first.title })).toBeFocused();
  await rows.filter({ hasText: first.title }).click();
  await expect(reader.locator(".paper-fulltext")).toBeVisible();
  const figure = reader.locator(".paper-figures img").first();
  await reader.getByRole("button", { name: /Figures/ }).click();
  await figure.scrollIntoViewIfNeeded();
  await expect(figure).toBeVisible();
  await expect
    .poll(() =>
      figure.evaluate(
        (image: HTMLImageElement) => image.complete && image.naturalWidth > 0,
      ),
    )
    .toBeTruthy();
  await page.screenshot({
    path: test.info().outputPath("library-figure-light.png"),
    fullPage: true,
  });
  await reader.evaluate((element) => (element.scrollTop = 0));
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await page.screenshot({
    path: test.info().outputPath("library-reader-dark.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await reader.evaluate((element) => (element.scrollTop = 0));
  await page.screenshot({
    path: test.info().outputPath("library-reader-mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.getByRole("button", { name: "Back to papers" }).click();
  await page
    .locator(".paper-list")
    .evaluate((element) => (element.scrollTop = 0));
  await page.locator("main").evaluate((element) => (element.scrollTop = 0));
  await page.screenshot({
    path: test.info().outputPath("library-100-mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
  expect(writes).toEqual([]);
});

test("empty collection and unavailable corpus remain distinct", async ({
  page,
}) => {
  await serveSnapshot(page, "empty");
  await expect(
    page.getByRole("heading", { name: "No collected papers yet" }),
  ).toBeVisible();
  await expect(page.locator(".paper-row")).toHaveCount(0);
  await page.screenshot({
    path: test.info().outputPath("library-empty.png"),
    fullPage: true,
  });
  await page.goto("about:blank");
  await page.unroute("**/api/**");
  await serveSnapshot(page, "error");
  await expect(page.getByText(/Corpus could not be read/)).toBeVisible();
  await page.screenshot({
    path: test.info().outputPath("library-error.png"),
    fullPage: true,
  });
  await page.route(`**/api/projects/${snapshot.project.id}/papers`, (route) =>
    route.fulfill({ json: snapshot.list }),
  );
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.locator(".paper-row")).toHaveCount(snapshot.list.total);
});

test("empty workspace creates a collection without starting processing", async ({
  page,
}) => {
  const writes: string[] = [];
  page.on("request", (request) => {
    if (request.method() !== "GET")
      writes.push(new URL(request.url()).pathname);
  });
  await page.goto("/#library");
  await expect(
    page.getByRole("heading", {
      name: "Your research starts with a collection",
    }),
  ).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: test.info().outputPath("library-empty.png"),
    fullPage: true,
  });
  const create = page.getByRole("button", {
    name: "New collection",
    exact: true,
  });
  await expect(create).toHaveClass(/button-primary/);
  await create.click();
  await page
    .getByLabel("Collection name", { exact: true })
    .fill("Cell division literature");
  await page
    .getByLabel("What does this collection cover? (optional)")
    .fill("Mechanisms of cell division and their connection to cancer.");
  await page.screenshot({
    path: test.info().outputPath("library-create.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Create collection", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Cell division literature",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "No collected papers yet" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Add papers", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: test.info().outputPath("library-new.png"),
    fullPage: true,
  });
  expect(writes).toEqual(["/api/projects"]);
  await page.getByRole("button", { name: "Add papers", exact: true }).click();
  await page
    .getByLabel("Paper DOI", { exact: true })
    .fill("10.1074/jbc.M110.121491");
  await page.screenshot({
    path: test.info().outputPath("library-add.png"),
    fullPage: true,
  });
  expect(writes).toEqual(["/api/projects"]);
});

test("paper removal states collection scope before mutation", async ({
  page,
}) => {
  const writes = await serveSnapshot(page);
  await expect(page.locator(".paper-row")).toHaveCount(snapshot.list.total);
  await page
    .getByRole("button", { name: /^Remove paper:/ })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "Claims supported by other papers",
  );
  await expect(page.getByRole("dialog")).toContainText("separate collection");
  await page.screenshot({
    path: test.info().outputPath("library-remove.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Keep paper", exact: true }).click();
  expect(writes).toEqual([]);
});

test("explicit paper addition shows progress and can retry a failed job", async ({
  page,
}) => {
  await serveSnapshot(page);
  const base = `/api/projects/${snapshot.project.id}`;
  let status = "running";
  let submitted: unknown;
  let retried = false;
  await page.route(`**${base}/papers/add`, async (route) => {
    submitted = route.request().postDataJSON();
    return route.fulfill({
      status: 202,
      json: {
        project_id: snapshot.project.id,
        job: { id: "paper-job", kind: "membership" },
      },
    });
  });
  await page.route(`**${base}/jobs/paper-job`, (route) =>
    route.fulfill({
      json: {
        job: { id: "paper-job", kind: "membership", status },
        events: [],
      },
    }),
  );
  await page.route(`**${base}/jobs`, (route) =>
    route.fulfill({
      json: {
        jobs: [
          {
            id: "paper-job",
            kind: "membership",
            status,
            last_event: { msg: "Extracting this paper's claims" },
            error:
              status === "failed"
                ? "Semantic indexing is incomplete; retry reuses saved extraction."
                : "",
          },
        ],
      },
    }),
  );
  await page.route(`**${base}/jobs/paper-job/retry`, (route) => {
    retried = true;
    status = "running";
    return route.fulfill({
      status: 202,
      json: {
        project_id: snapshot.project.id,
        job: { id: "paper-job", kind: "membership" },
      },
    });
  });
  await page.getByRole("button", { name: "Add papers", exact: true }).click();
  await page.getByLabel("Paper DOI", { exact: true }).fill("10.1234/new-paper");
  await page
    .getByRole("button", { name: "Add and process papers", exact: true })
    .click();
  expect(submitted).toEqual({ dois: ["10.1234/new-paper"] });
  await expect(
    page.getByText("Processing added papers", { exact: true }),
  ).toBeVisible();
  status = "failed";
  await expect(
    page.getByText("Paper processing needs attention", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Retry processing", exact: true })
    .click();
  expect(retried).toBe(true);
});
