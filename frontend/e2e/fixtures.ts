// Synthetic contract fixtures ONLY for browser tests. Never imported by application code.
import type { Page } from "@playwright/test";
export const project = {
  id: "ion-channels",
  name: "Ion-channel mechanisms",
  description:
    "Functional evidence for neuronal ion-channel variants and their downstream effects.",
  status: "ready",
  has_kg: true,
  kg_db: "/fixture/kg.duckdb",
  adopted: false,
  n_claims: 842,
  spec: {
    scope: "Mechanisms of neuronal ion-channel dysfunction",
    theme:
      "Functional evidence from electrophysiology and genetic perturbation",
    queries: ["SCN2A AND electrophysiology", "KCNT1 AND functional"],
    seed_dois: [],
    n_papers: 120,
    exclude_terms: [],
    full_text_only: false,
    concurrency: 8,
  },
  built: { stale: true, n_papers: 96, n_claims: 842, scope: "Ion channels" },
  chat: [],
};
const root = "channels-20260905";
const titles = [
  "Ion-channel mechanisms",
  "Sodium-channel excitability",
  "Potassium-channel regulation",
  "Challenge the mechanism",
  "Variant-specific effects",
  "Independent cohort validation",
];
const ids = [
  root,
  `${root}~1`,
  `${root}~2`,
  `${root}~3`,
  `${root}~1~1`,
  `${root}~1~2`,
];
export const runs = ids.map((run_id, i) => ({
  run_id,
  root,
  parent: i === 0 ? null : i > 3 ? ids[1] : root,
  depth: i === 0 ? 0 : i > 3 ? 2 : 1,
  steps: 6 + i,
  last_action: i === 4 ? "run_experiments" : i === 5 ? "search_papers" : "done",
  active: i >= 4,
  updated_at: 1788643800 + i,
  project: project.id,
  beam:
    i === 0
      ? null
      : {
          angle: titles[i],
          adversarial: i === 3,
          kept: i === 3 ? false : true,
          rank: i,
          reason:
            i === 3
              ? "The alternative did not explain the observed direction of effect."
              : "Continue testing the mechanism against independent evidence.",
        },
}));
export const investigation = {
  root,
  goal: "Which mechanisms explain altered neuronal excitability?",
  runs,
  active: true,
  last_action: "done",
  updated_at: 1788643800,
  n_runs: 6,
  n_branches: 5,
};
export const steps = [
  {
    step: 1,
    action: "search_papers",
    ts: 1788643700,
    dt_s: 4,
    reasoning:
      "Compare functional evidence for gain- and loss-of-function mechanisms across independent studies.",
    observation: "Relevant electrophysiology papers were retrieved.",
    args: { query: "SCN2A electrophysiology" },
  },
  {
    step: 2,
    action: "run_experiments",
    ts: 1788643750,
    dt_s: 24,
    reasoning:
      "Test whether the observed shift in channel activity is consistent across independent samples. Keep uncertain effects separate from supported mechanisms.",
    observation: "Analysis recorded. Awaiting the robustness check.",
    args: { experiments: [{ method: "regression" }] },
  },
];
export const experiments = runs.flatMap((r, i) =>
  i === 0
    ? []
    : [
        {
          entry_id: i,
          run_id: r.run_id,
          kind: "experiment",
          title: [
            "",
            "Channel activity differs across variant groups",
            "Dependency patterns across cell lines",
            "Alternative explanation test",
            "Functional effect of channel variants",
            "Cross-cohort consistency",
          ][i],
          body: "Compare the reported effect across independent experimental units.",
          stage: i === 3 ? "killed" : i === 1 ? "candidate" : "open",
          status: "open",
          method: "regression",
          effect: i === 1 ? 0.42 : null,
          p_null: i === 1 ? 0.018 : null,
          n_units: i === 1 ? 48 : null,
          robust: i === 1 ? true : null,
          code: "result = fit_model(independent_samples)",
          result: i === 1 ? { effect: 0.42, p_null: 0.018, n_units: 48 } : {},
          provenance: { dataset: "Synthetic browser-test fixture" },
          verdict: i === 3 ? "inconclusive" : null,
        },
      ],
);
export const tree = {
  root,
  lanes: runs.map((r) => ({ ...r, n_experiments: r.depth ? 1 : 0 })),
  nodes: experiments,
  forks: [],
  fans: [],
  orphans: [],
  unverified_submissions: [],
  db_unreadable: "",
  counts: { experiments: 5, submitted: 1, candidates: 1, killed: 1, failed: 0 },
};
export const events = {
  root,
  events: runs.flatMap((r, i) =>
    steps.map((s, j) => ({
      ...s,
      type: "step",
      run_id: r.run_id,
      t: 1788643700 + i * 20 + j,
      u: i * 20 + j,
    })),
  ),
  active: true,
};
export async function mockApi(page: Page) {
  const writes: { path: string; body: any }[] = [];
  let list = [project];
  let decisions: Record<string, any> = {};
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (route.request().method() === "POST") {
      const body = route.request().headers()["content-type"]?.includes("json")
        ? route.request().postDataJSON()
        : {};
      writes.push({ path, body });
      if (path === "/api/projects") {
        const p = {
          ...project,
          ...body,
          id: "new-project",
          has_kg: false,
          kg_db: null,
        };
        list = [...list, p as typeof project];
        return route.fulfill({ json: p });
      }
      if (path === "/api/review/promotion") {
        decisions[String(body.test_id)] = {
          decision: body.decision,
          note: body.note,
        };
        return route.fulfill({ json: { ok: true } });
      }
      if (path.endsWith("/chat"))
        return route.fulfill({
          json: {
            chat: [
              { role: "user", content: body.message },
              {
                role: "assistant",
                content:
                  "I suggest focusing the collection on functional assays.",
                patch: { theme: "Functional assays" },
              },
            ],
          },
        });
      if (path.endsWith("/apply"))
        return route.fulfill({
          json: { promoted: 1, rejected: 0, skipped: 0 },
        });
      if (path.endsWith("/run"))
        return route.fulfill({ json: { run_id: root, id: "job1" } });
      return route.fulfill({ json: project });
    }
    if (path === "/api/projects")
      return route.fulfill({ json: { projects: list } });
    if (path === "/api/investigations")
      return route.fulfill({
        json:
          url.searchParams.get("project") === "other" ? [] : [investigation],
      });
    if (path.startsWith("/api/tree/")) return route.fulfill({ json: tree });
    if (path.startsWith("/api/events/")) return route.fulfill({ json: events });
    if (path.endsWith("/stream"))
      return route.fulfill({
        contentType: "text/event-stream",
        body: 'id: 3\nevent: step\ndata: {"step":3,"action":"reflect","reasoning":"Live update: robustness check has completed."}\n\nevent: end\ndata: {}\n\n',
      });
    if (path.startsWith("/api/runs/")) {
      const r = runs.find(
        (r) => r.run_id === decodeURIComponent(path.split("/")[3]),
      )!;
      return route.fulfill({
        json: {
          ...r,
          steps,
          n_steps: 2,
          resume_line: 2,
          tests: [],
          tallies: {},
        },
      });
    }
    if (path === "/api/kg")
      return route.fulfill({
        json: {
          source: project.id,
          sources: [project.id],
          nodes: [
            { id: "SCN2A", label: "SCN2A", degree: 2 },
            { id: "excitability", label: "Neuronal excitability", degree: 1 },
            { id: "sodium", label: "Sodium transport", degree: 1 },
          ],
          edges: [
            {
              source: "SCN2A",
              target: "excitability",
              predicate: "regulates",
              status: "disputed",
              n_sources: 3,
            },
            {
              source: "SCN2A",
              target: "sodium",
              predicate: "enables",
              status: "reported",
              n_sources: 2,
            },
          ],
          shown: 2,
          total_claims: 842,
        },
      });
    if (path === "/api/review")
      return route.fulfill({
        json: {
          candidates: [
            {
              test_id: 1,
              subject: "SCN2A",
              object: "excitability",
              hypothesis: "Channel variants alter neuronal excitability",
              method: "regression",
              effect: 0.42,
              p_null: 0.018,
              novelty_verdict: "novel",
            },
          ],
          promo_decided: decisions,
        },
      });
    if (path.endsWith("/kg"))
      return route.fulfill({
        json: {
          exists: true,
          papers: { n: 96, full_text: 72 },
          claims: { n: 842, entities: 213, evidence: 1102 },
          disputed: 24,
        },
      });
    if (path.endsWith("/attachments"))
      return route.fulfill({ json: { attachments: [] } });
    if (path.endsWith("/jobs"))
      return route.fulfill({
        json: {
          jobs: [
            {
              id: "job1",
              kind: "build",
              status: "running",
              started: 1788643700,
            },
          ],
        },
      });
    if (path.endsWith("/log"))
      return route.fulfill({ json: { log: "Collection build running" } });
    if (path.includes("/jobs/"))
      return route.fulfill({
        json: {
          job: { id: "job1", status: "running" },
          events: [{ stage: "discover", msg: "Finding matching papers" }],
        },
      });
    return route.fulfill({ json: project });
  });
  return writes;
}
