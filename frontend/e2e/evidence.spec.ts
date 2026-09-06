import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mockApi, project } from "./fixtures";

// Synthetic API responses exercise the actual Knowledge screen, never app imports.
export async function evidenceApi(page: Page) {
  await mockApi(page);
  const graph = {
    source: project.id,
    sources: [project.id],
    shown: 2,
    total_claims: 842,
    nodes: [
      { id: "SCN2A", label: "SCN2A", degree: 2 },
      { id: "excitability", label: "Neuronal excitability", degree: 1 },
      { id: "sodium", label: "Sodium transport", degree: 1 },
    ],
    edges: [
      {
        claim_id: "claim-1",
        source: "SCN2A",
        target: "excitability",
        predicate: "regulates",
        status: "disputed",
        n_sources: 1,
      },
      {
        claim_id: "claim-2",
        source: "SCN2A",
        target: "sodium",
        predicate: "enables",
        object_function: "transport activity",
        status: "reported",
        n_sources: 1,
      },
    ],
  };
  await page.route("**/api/kg?**", (route) => {
    const url = new URL(route.request().url());
    const claim = url.searchParams.get("claim");
    if (!claim) return route.fulfill({ json: graph });
    if (url.searchParams.get("source") !== project.id)
      return route.fulfill({
        status: 404,
        json: { error: "wrong collection" },
      });
    return route.fulfill({
      json: {
        source: project.id,
        evidence_total: claim === "claim-1" ? 1 : 0,
        claim: {
          claim_id: claim,
          subject_label: "SCN2A",
          object_label: "Neuronal excitability",
          predicate: "regulates",
          status: "disputed",
        },
        evidence:
          claim === "claim-1"
            ? [
                {
                  evidence_id: 7,
                  source_ref: 12,
                  source_label: "Functional evidence",
                  section: "Results",
                  quote:
                    "Synthetic source excerpt: the observed response depends on the experimental context.",
                  attribution: "own",
                  certainty: "hypothesized",
                  study_type: "in_vitro",
                  evidence_type: "experimental",
                  papers: [
                    {
                      paper_id: "fixture-paper",
                      title: "Functional evidence in neuronal cells",
                      year: 2020,
                      doi: "10.1234/fixture",
                    },
                  ],
                  contexts: [
                    {
                      ctx_id: 1,
                      slot: "organism",
                      value: "human",
                      label: "Human",
                      provenance: "stated",
                      quote: "Human cells were used.",
                    },
                  ],
                },
              ]
            : [],
      },
    });
  });
}

test("a relationship opens its exact source/context; search and return retain graph scope", async ({
  page,
}) => {
  await evidenceApi(page);
  await page.goto("/?project=ion-channels#knowledge");
  await expect(page.locator(".claim-result")).toHaveCount(2);
  await expect(
    page.locator(".react-flow__edge-text").filter({ hasText: "regulates" }),
  ).toBeVisible();
  await page.locator(".claim-result").filter({ hasText: "regulates" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Functional evidence in neuronal cells",
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Human cells were used.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Open paper" })).toHaveAttribute(
    "href",
    "https://doi.org/10.1234/fixture",
  );
  await expect(page.locator(".source-evidence blockquote")).toContainText(
    "Synthetic source excerpt",
  );
  await expect(
    page.getByText("Source assertion: Hypothesized", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Attributed to this source", { exact: true }),
  ).toBeVisible();
  await page.screenshot({ path: "/tmp/ux-code-evidence-dark.png" });
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze())
      .violations,
  ).toEqual([]);
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await page.screenshot({ path: "/tmp/ux-code-evidence-light.png", animations: "disabled" });
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze())
      .violations,
  ).toEqual([]);
  await page.getByRole("button", { name: "Back to connections" }).click();
  await page
    .getByRole("textbox", { name: "Find an entity or relationship" })
    .fill("transport activity");
  await expect(page.locator(".claim-result")).toHaveCount(1);
  await page.locator(".claim-result").click();
  await expect(
    page.getByText("No quoted evidence is stored for this relationship."),
  ).toBeVisible();
  await expect(page.locator(".source-evidence")).toHaveCount(0);
  await page
    .getByRole("textbox", { name: "Find an entity or relationship" })
    .fill("no match");
  await expect(
    page.getByText(
      "No matching relationships in this view. Try another term or claim filter.",
    ),
  ).toBeVisible();
});

test("claim request errors remain visible and evidence is accessible on a narrow screen", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await evidenceApi(page);
  await page.route("**/api/kg?**claim=claim-1", (route) =>
    route.fulfill({ status: 503, json: { error: "Source store unavailable" } }),
  );
  await page.goto("/?project=ion-channels#evidence");
  await page.getByRole("button", { name: "Browse 2 relationships" }).click();
  await page.locator(".claim-result").filter({ hasText: "regulates" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Source store unavailable",
  );
  await page.unroute("**/api/kg?**claim=claim-1");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.locator(".source-evidence blockquote")).toBeVisible();
  await page.screenshot({ path: "/tmp/ux-code-evidence-mobile.png" });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze())
      .violations,
  ).toEqual([]);
  await page.getByRole("button", { name: "Close entity detail" }).click();
  await expect(
    page.getByRole("button", { name: "Browse 2 relationships" }),
  ).toBeVisible();
});
