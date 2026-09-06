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
    matched: 2,
    total_claims: 2,
    status_counts: { disputed: 24, established: 400, reported: 418 },
    facets: {
      polarity: [
        { value: 1, n: 500 },
        { value: 0, n: 300 },
        { value: -1, n: 42 },
      ],
      kind: [
        { value: "entity", n: 120 },
        { value: "process", n: 93 },
      ],
      relation_class: [{ value: "causal", n: 700 }],
    },
    summary: {
      claims: 842,
      entities: 213,
      evidence: 1102,
      papers: 96,
      papers_full_text: 72,
      experiments: 40,
      deferrals: 0,
      tests: 5,
      vectors: 842,
    },
    as_of: 1757100000,
    nodes: [
      {
        id: "HGNC:10588",
        label: "SCN2A",
        curie: "HGNC:10588",
        kind: "entity",
        degree: 2,
        n_out: 2,
        n_in: 0,
      },
      {
        id: "GO:0001508",
        label: "Neuronal excitability",
        curie: "GO:0001508",
        kind: "process",
        degree: 1,
        n_out: 0,
        n_in: 1,
      },
      {
        id: "GO:0006814",
        label: "Sodium transport",
        curie: "GO:0006814",
        kind: "process",
        degree: 1,
        n_out: 0,
        n_in: 1,
      },
    ],
    edges: [
      {
        claim_id: "claim-1",
        abstract_key: "q1",
        source: "HGNC:10588",
        target: "GO:0001508",
        predicate: "regulates",
        polarity: 0,
        relation_class: "causal",
        mechanism: "",
        status: "disputed",
        dispute_kind: "opposite_sign",
        n_sources: 1,
        first_year: 2020,
        tested: { n: 2, candidate: 0, validated: 1, rejected: 0, killed: 1 },
      },
      {
        claim_id: "claim-2",
        abstract_key: "q2",
        source: "HGNC:10588",
        target: "GO:0006814",
        predicate: "enables",
        object_function: "transport activity",
        polarity: 1,
        relation_class: "causal",
        status: "reported",
        n_sources: 1,
        tested: null,
      },
    ],
  };
  await page.route("**/api/kg?**", (route) => {
    const url = new URL(route.request().url());
    const claim = url.searchParams.get("claim");
    if (!claim) {
      // The real endpoint runs the search in the database; the fixture mirrors that contract.
      const q = (url.searchParams.get("q") || "").toLowerCase();
      if (!q) return route.fulfill({ json: graph });
      const labels = new Map(graph.nodes.map((n) => [n.id, n.label]));
      const edges = graph.edges.filter((e) =>
        `${labels.get(e.source)} ${e.predicate} ${labels.get(e.target)} ${"object_function" in e ? e.object_function : ""}`
          .toLowerCase()
          .includes(q),
      );
      return route.fulfill({
        json: {
          ...graph,
          edges,
          nodes: graph.nodes.filter((n) =>
            edges.some((e) => e.source === n.id || e.target === n.id),
          ),
          shown: edges.length,
          matched: edges.length,
        },
      });
    }
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
          abstract_key: "q1",
          subject_label: "SCN2A",
          subject_curie: "HGNC:10588",
          subject_kind: "entity",
          subject_form: { state: "mutant", variant: "p.Arg1882Gln" },
          object_label: "Neuronal excitability",
          object_curie: "GO:0001508",
          object_kind: "process",
          predicate: "regulates",
          polarity: 0,
          relation_class: "causal",
          status: "disputed",
          dispute_kind: "opposite_sign",
          n_sources: 1,
          first_year: 2020,
        },
        related:
          claim === "claim-1"
            ? [
                {
                  claim_id: "claim-9",
                  subject_label: "SCN2A",
                  predicate: "decreases",
                  object_label: "Neuronal excitability",
                  polarity: -1,
                  relation_class: "causal",
                  status: "disputed",
                  n_sources: 2,
                },
              ]
            : [],
        tests:
          claim === "claim-1"
            ? [
                {
                  test_id: 4,
                  run_id: "root~1",
                  method: "depmap_dependency",
                  hypothesis: "SCN2A dependency tracks excitability genes",
                  expected_sign: 1,
                  observed_sign: 1,
                  effect: 0.31,
                  p_null: 0.004,
                  status: "candidate",
                  kill_reason: "",
                  human_review: "validated",
                  review_note: "Replicates across lineages.",
                  novelty_verdict: "open",
                },
                {
                  test_id: 5,
                  run_id: "root~2",
                  method: "geo_expression",
                  expected_sign: 1,
                  observed_sign: -1,
                  effect: -0.2,
                  p_null: 0.3,
                  status: "refuted",
                  kill_reason: "direction-wrong",
                  human_review: "",
                },
              ]
            : [],
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
                  attribution_agreed: true,
                  certainty: "hypothesized",
                  quantifier: "most",
                  predicate: "modulates",
                  experiment_id: "exp-1",
                  experiment: {
                    experiment_id: "exp-1",
                    unit: "cells",
                    intervention: "SCN2A knockdown",
                    control: "scrambled siRNA",
                    readout: "firing rate",
                    n: 12,
                    effect: "-1.4 log2FC",
                  },
                  cites: [
                    { sid: "DOI:10.1/prior", marker: "(3)", tier: "doi" },
                  ],
                  study_type: "molecular_experiment",
                  evidence_type: "experimental_own",
                  papers: [
                    {
                      paper_id: "fixture-paper",
                      title: "Functional evidence in neuronal cells",
                      year: 2020,
                      doi: "10.1234/fixture",
                      pmid: "12345",
                      is_full_text: true,
                      license: "cc-by",
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
  await page.getByRole("button", { name: "Browse 2 relationships" }).click();
  await expect(page.locator(".claim-result")).toHaveCount(2);
  await expect(
    page.locator(".edge-label").filter({ hasText: "regulates" }),
  ).toBeVisible();
  await expect(page.getByLabel("Collection summary")).toContainText(
    "1,102 evidence records",
  );
  await expect(
    page.locator(".kg-node").filter({ hasText: "SCN2A" }),
  ).toBeVisible();
  await expect(
    page.locator(".claim-result").filter({ hasText: "regulates" }),
  ).toContainText("tested: 1 accepted, 1 failed");
  await page.locator(".claim-result").filter({ hasText: "regulates" }).click();
  await expect(
    page.locator(".kg-node.selected").filter({ hasText: "SCN2A" }),
  ).toContainText("HGNC:10588");
  await expect(
    page.getByRole("heading", {
      name: "Functional evidence in neuronal cells",
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Human cells were used.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "DOI" })).toHaveAttribute(
    "href",
    "https://doi.org/10.1234/fixture",
  );
  await expect(page.getByRole("link", { name: "PubMed" })).toHaveAttribute(
    "href",
    "https://pubmed.ncbi.nlm.nih.gov/12345/",
  );
  await expect(page.locator(".spine")).toContainText("mutant · p.Arg1882Gln");
  await expect(page.locator(".spine-relation")).toContainText(
    "Undirected · Causal",
  );
  await expect(page.getByRole("link", { name: /GO:0001508/ })).toHaveAttribute(
    "href",
    "https://bioregistry.io/go:0001508",
  );
  await expect(
    page.getByLabel("Other answers to the same question"),
  ).toContainText("SCN2A decreases Neuronal excitability");
  const tests = page.getByLabel("Engine tests");
  await expect(tests).toContainText("Accepted by reviewer");
  await expect(tests).toContainText("Replicates across lineages.");
  await expect(tests).toContainText("Direction opposite to prediction");
  await expect(page.getByText("Reports an experiment")).toBeVisible();
  await expect(page.getByText("SCN2A knockdown")).toBeVisible();
  await expect(page.getByText("DOI:10.1/prior (3)")).toBeVisible();
  await expect(page.getByText("Full text stored")).toBeVisible();
  await expect(page.locator(".source-evidence blockquote")).toContainText(
    "Synthetic source excerpt",
  );
  await expect(page.getByText("Hypothesized", { exact: true })).toBeVisible();
  await expect(page.getByText("This source's own finding")).toBeVisible();
  await expect(page.getByText("model and checker agreed")).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("ux-code-evidence-dark.png") });
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze())
      .violations,
  ).toEqual([]);
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await page.screenshot({
    path: test.info().outputPath("ux-code-evidence-light.png"),
    animations: "disabled",
  });
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze())
      .violations,
  ).toEqual([]);
  await page.getByRole("button", { name: "Back to connections" }).click();
  await page
    .getByRole("textbox", { name: "Find an entity or relationship" })
    .fill("transport activity");
  await page.getByRole("button", { name: "Browse 1 relationship" }).click();
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
    page.getByRole("heading", { name: "No claims match" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Clear search and filters" }).click();
  await page.getByRole("button", { name: "Browse 2 relationships" }).click();
  await expect(page.locator(".claim-result")).toHaveCount(2);
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
  await page.screenshot({ path: test.info().outputPath("ux-code-evidence-mobile.png") });
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
