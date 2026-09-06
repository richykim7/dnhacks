import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { mockApi, investigation } from "./fixtures";
import type { RuntimeEvent } from "../src/lib/runtime";

// Synthetic execution fixture; molecular coordinates are experimental reference 1CRN from RCSB.
// https://files.rcsb.org/download/1CRN.pdb — no generated predictions or measured runtime claims.
const pdb = readFileSync(new URL("./1crn.pdb", import.meta.url), "utf8");
const root = investigation.root;
const child = `${root}~1`;
function history(): RuntimeEvent[] {
  const raw: any[] = [
    [
      root,
      "attempt.started",
      {
        original_question: investigation.goal,
        branch_objective: "Investigate channel structure",
        lifecycle: "running",
      },
    ],
    [
      child,
      "attempt.started",
      {
        original_question: investigation.goal,
        branch_objective: "Inspect the experimental fold",
        parent_run_id: root,
      },
    ],
    [
      child,
      "intent",
      {
        intent:
          "Inspect the reference fold before choosing a structural experiment.",
      },
    ],
    [
      child,
      "tool.started",
      {
        phase: "tool",
        action: "run_experiments",
        label: "Running structural experiment",
      },
    ],
    [
      child,
      "experiment.queued",
      {
        title: "Reference fold inspection",
        status: "queued",
        method: "Structure inspection",
      },
      "exp1",
    ],
    [child, "experiment.started", { status: "running" }, "exp1"],
    [
      child,
      "experiment.output",
      { text: "Reading atomic coordinates…", stream: "stdout", offset: 0 },
      "exp1",
    ],
    [
      child,
      "experiment.finished",
      { status: "completed", exploratory: true },
      "exp1",
    ],
    [
      child,
      "artifact",
      {
        artifact_id: "1crn",
        name: "1CRN.pdb",
        kind: "molecular_structure",
        format: "pdb",
        status: "available",
        atom_count: 327,
        storage_key: "molecule",
        provenance: {
          category: "experimental_reference",
          source_ids: ["PDB:1CRN"],
          tool: "RCSB",
          tool_version: "reference",
        },
      },
      "exp1",
    ],
    [child, "tool.ended", {}],
    [child, "heartbeat", {}],
  ];
  return raw.map(([run_id, kind, payload, experiment_id], i) => ({
    schema_version: 1,
    sequence: i + 1,
    run_id,
    attempt_id: "fixture",
    event_id: `fixture-${i}`,
    kind,
    payload,
    experiment_id,
    producer: kind === "intent" ? "agent" : "runner",
    recorded_at: Date.now() / 1000,
  }));
}
async function fixture(page: Page, invalid = false, reviewed = false, inhibitor = false) {
  await mockApi(page);
  let terminalReads = 0,
    artifactReads = 0;
  const events = history();
  if (inhibitor) {
    const artifact = events.find(e => e.kind === 'artifact')!;
    artifact.payload = {...artifact.payload, name:'3VQU.cif', format:'cif', provenance:{category:'experimental_reference',source_ids:['PDB:3VQU']}};
  }
  if (reviewed) {
    for (const [kind, payload] of [
      ["experiment.reviewed", { verification: "CANDIDATE" }],
      [
        "experiment.human_reviewed",
        {
          human_review: "validated",
          human_review_note: "Checked independent controls",
        },
      ],
    ] as const) {
      events.push({
        ...events[0],
        sequence: events.length + 1,
        event_id: `review-${events.length}`,
        run_id: child,
        experiment_id: "exp1",
        kind,
        payload,
      });
    }
  }
  await page.route("**/api/investigations**", (r) =>
    r.fulfill({ json: [{ ...investigation, runtime: true }] }),
  );
  await page.route("**/api/runtime/**", (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/events"))
      return route.fulfill({
        json: {
          events: events.filter(
            (e) => e.sequence > Number(url.searchParams.get("after") || 0),
          ),
        },
      });
    if (url.pathname.endsWith("/stream"))
      return route.fulfill({
        contentType: "text/event-stream",
        body: ": connected\n\n",
      });
    if (url.pathname.endsWith("/terminal")) {
      terminalReads++;
      return route.fulfill({
        json: {
          available: false,
          reason: "Terminal unavailable for this agent.",
        },
      });
    }
    if (url.pathname.includes("/blob/")) {
      artifactReads++;
      return route.fulfill({
        contentType: "text/plain",
        body: invalid ? "not a structure" : inhibitor ? readFileSync(new URL('./inhibitor/3vqu.cif', import.meta.url), 'utf8') : pdb,
      });
    }
    return route.fulfill({ status: 404, json: { error: "Not in fixture" } });
  });
  return {
    terminalReads: () => terminalReads,
    artifactReads: () => artifactReads,
  };
}
test("node execution, opt-in terminal, inline real geometry and replay boundary", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const reads = await fixture(page);
  await page.goto("/");
  await expect(page.locator(".agent-node")).toHaveCount(2);
  expect(reads.artifactReads()).toBe(0);
  await page
    .getByRole("button", { name: "Inspect Inspect the experimental fold" })
    .click();
  await expect(page.locator(".current-work")).toContainText(
    "Inspect the reference fold",
  );
  expect(reads.terminalReads()).toBe(0);
  await page.getByRole("button", { name: "Show terminal" }).click();
  await expect(
    page.getByText("Terminal unavailable for this agent."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Hide terminal" }).click();
  await page
    .getByRole("tablist", { name: "Researcher detail" })
    .getByRole("tab", { name: "Experiments" })
    .click();
  await expect(page.locator(".artifact-canvas canvas")).toBeVisible({
    timeout: 20000,
  });
  await expect(page.getByText("Preparing experiment structure")).toHaveCount(0);
  await page.waitForTimeout(700);
  await page.screenshot({ path: test.info().outputPath("dn-runtime-molecule-dark.png") });
  await page.getByRole("tab", { name: "Surface", exact: true }).click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: test.info().outputPath("dn-runtime-surface.png") });
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await page.getByRole("tab", { name: "Ribbon", exact: true }).click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: test.info().outputPath("dn-runtime-molecule-light.png") });
  await page.getByLabel("Activity playback position").fill("7");
  await expect(page.locator(".artifact-viewer")).toHaveCount(0);
  await expect(page.locator(".experiment-detail")).toContainText("Running");
  await expect(
    page.getByRole("button", { name: "Show terminal" }),
  ).toBeDisabled();
  await page.getByLabel("Activity playback position").fill("1");
  await expect(page.locator(".agent-node")).toHaveCount(1);
  await expect(page.locator(".detail-panel")).toHaveCount(0);
  expect(errors).toEqual([]);
});
test("inhibitor workbench opens from its owning experiment", async ({ page }) => {
  const clockStart = new Date('2026-09-06T09:00:00Z');
  await page.clock.install({time: clockStart});
  test.setTimeout(60000);
  await fixture(page, false, false, true);
  const geometry = JSON.parse(readFileSync(new URL('./inhibitor/geometry.json', import.meta.url), 'utf8'));
  const recipe={schema_version:1,source_hash:geometry.source_hash,revision:1,style:'matte',shot:'arrival',
    ligand:geometry.residues.filter((r:any)=>r.kind==='ligand').sort((a:any,b:any)=>b.atoms.length-a.atoms.length)[0].id,
    model:0,clip:false,selected:[],frame:0,pose:'reference',compare:false,prepared:false};
  const scenes=[{sequence:10,recorded_at:1,actor:'agent',note:'Locate target',recipe},
    {sequence:11,recorded_at:1.2,actor:'agent',note:'Inspect pocket',recipe:{...recipe,revision:2,shot:'pocket',clip:true}}];
  const timeline=[...scenes.map(s=>({...s,kind:'scene.changed'})),
    {sequence:12,recorded_at:1.4,actor:'agent',kind:'scene.vision',note:'Inspected scene pixels',recipe:scenes[1].recipe,details:{observation:'Check the visible ligand against canonical geometry.'}}];
  let writes=0;
  await page.route('**/inhibitor/**',route=>{if(route.request().method()==='POST')writes++;return route.fulfill({json:{jobs:[],bundles:[],scenes,timeline}})});
  await page.route('**/geometry/**', route => {
    const operation = new URL(route.request().url()).searchParams.get('operation');
    return route.fulfill({ json: operation === 'contacts' ? {contacts: []} : operation === 'preparation' ? {status:'blocked', reason:'Fixture: no preparation protocol', retained:{waters:0,alternate_atoms:0,hydrogens:0}} : geometry });
  });
  await page.goto('/?sceneReview=1');
  await page.getByRole('button', {name:'Inspect Inspect the experimental fold'}).click();
  await page.getByRole('tablist', {name:'Researcher detail'}).getByRole('tab', {name:'Experiments'}).click();
  await page.getByRole('button', {name:'Open inhibitor workbench'}).click();
  await expect(page.getByRole('dialog', {name:'Inhibitor workbench'})).toBeVisible();
  await expect(page.locator('.pocket-stage canvas')).toBeVisible();
  await page.waitForFunction(() => Boolean(window.sceneReview));
  await page.evaluate(() => window.sceneReview!.ready());
  await page.getByLabel('Playback speed').selectOption('8');
  await page.getByRole('button',{name:'Play',exact:true}).click();
  await expect.poll(()=>page.evaluate(()=>window.inhibitorScene!.recipe()!.revision)).toBe(2);
  await expect(page.getByLabel('Interaction mode')).toHaveValue('replay');
  await page.getByRole('button',{name:'oblique',exact:true}).click();
  await expect(page.getByLabel('Interaction mode')).toHaveValue('explore');
  await page.waitForTimeout(1700); // one refresh: user camera must not be overwritten
  expect(await page.evaluate(()=>window.inhibitorScene!.recipe()!.shot)).toBe('oblique');
  const ownView=await page.evaluate(()=>window.inhibitorScene!.recipe());
  await page.getByLabel('Interaction mode').selectOption('follow');
  await expect.poll(()=>page.evaluate(()=>window.inhibitorScene!.recipe()!.shot)).toBe('pocket');
  await page.getByLabel('Interaction mode').selectOption('explore');
  expect(await page.evaluate(()=>window.inhibitorScene!.recipe())).toEqual(ownView);
  await page.getByRole('button',{name:'Previous action',exact:true}).click();
  await expect(page.getByLabel('Interaction mode')).toHaveValue('replay');
  await page.getByText('Activity & evidence · 3 recorded operations', {exact:true}).click();
  await page.getByRole('button',{name:/Inspected scene pixels/}).click();
  await expect(page.getByText('Check the visible ligand against canonical geometry.')).toBeVisible();
  // At 8× the last operation lasts only 0.5s. Real-time locator dispatch can
  // arrive after completion, when this same toggle has become Play again.
  await page.clock.pauseAt(new Date(clockStart.getTime()+300_000));
  await page.getByRole('button',{name:'Play',exact:true}).click();
  await expect(page.getByRole('button',{name:'Pause',exact:true})).toBeVisible();
  await page.clock.runFor(160);
  await expect(page.locator('.pocket-clock')).toHaveText('6 / 9s');
  await page.getByRole('button',{name:'Pause',exact:true}).click();
  await expect(page.getByRole('button',{name:'Play',exact:true})).toBeVisible();
  const paused=await page.getByLabel('Agent scene action').inputValue();
  await page.clock.runFor(1000); // would exceed the end of the recording if still playing
  await expect(page.getByLabel('Agent scene action')).toHaveValue(paused);
  await expect(page.locator('.pocket-clock')).toHaveText('6 / 9s');
  await page.clock.resume();
  expect(writes).toBe(0);
  await page.screenshot({path:test.info().outputPath('dn-inhibitor-desktop.png')});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:test.info().outputPath('dn-inhibitor-mobile.png')});
  await page.getByRole('button', {name:'Return to experiment'}).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test("malformed experiment structure is an explicit error", async ({
  page,
}) => {
  await fixture(page, true);
  await page.goto("/");
  await page
    .getByRole("button", { name: "Inspect Inspect the experimental fold" })
    .click();
  await page
    .getByRole("tablist", { name: "Researcher detail" })
    .getByRole("tab", { name: "Experiments" })
    .click();
  await expect(page.getByRole("alert")).toContainText("No atoms could be read");
});
test("human review status follows the playback cursor", async ({ page }) => {
  await fixture(page, false, true);
  await page.goto("/");
  await page
    .getByRole("button", { name: "Inspect Inspect the experimental fold" })
    .click();
  await page
    .getByRole("tablist", { name: "Researcher detail" })
    .getByRole("tab", { name: "Experiments" })
    .click();
  await expect(page.getByText("Accepted by human review")).toBeVisible();
  await expect(page.getByText("Checked independent controls")).toBeVisible();
  await page.getByLabel("Activity playback position").fill("12");
  await expect(page.getByText("Accepted by human review")).toHaveCount(0);
  await expect(page.getByText("Checked independent controls")).toHaveCount(0);
  await expect(page.locator(".experiment-detail")).toContainText(
    "awaiting human review",
  );
});
test("experiment list opens its owning experiment and navigation preserves investigation", async ({
  page,
}) => {
  await fixture(page);
  await page.goto(`/#investigations/${root}`);
  await page
    .getByRole("tablist", { name: "Investigation view" })
    .getByRole("tab", { name: "Experiments" })
    .click();
  await page.getByRole("button", { name: /Reference fold inspection/ }).click();
  await expect(
    page
      .getByRole("tablist", { name: "Researcher detail" })
      .getByRole("tab", { name: "Experiments" }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.locator('[data-experiment-id="exp1"]')).toBeVisible();
  await page.getByRole("link", { name: "Library", exact: true }).click();
  await page.getByRole("link", { name: "Investigations", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`#investigations/${root}$`));
});
test("mobile node-specific geometry remains usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fixture(page);
  await page.goto("/");
  await page
    .getByRole("button", { name: "Inspect Inspect the experimental fold" })
    .click();
  await page
    .getByRole("tablist", { name: "Researcher detail" })
    .getByRole("tab", { name: "Experiments" })
    .click();
  await expect(page.locator(".artifact-canvas canvas")).toBeVisible({
    timeout: 20000,
  });
  await page.locator(".artifact-canvas").scrollIntoViewIfNeeded();
  await page.waitForTimeout(700);
  await page.screenshot({ path: test.info().outputPath("dn-runtime-mobile.png") });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
