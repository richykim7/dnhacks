/* ============================================================================
   dnhacksbio console — vanilla JS, no build step.
   Views: Workflow (architecture, lit up), Runs (live), Knowledge graph, Review. Hash router.
   ========================================================================== */
"use strict";

const $ = (s, r = document) => r.querySelector(s);
const main = $("#main");

function el(tag, attrs = {}, children = []) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) n.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    if (c == null) continue;
    n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return n;
}
const esc = (s) => (s == null ? "" : String(s).replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])));

// Every view is scoped to the active project: an analysis owns its corpus, and a run belongs to the
// corpus it reasoned over. `scopeURL` is the one place that rule is applied to an outbound request, so
// "which analysis am I looking at" cannot mean different things in two tabs.
// Endpoints that are inherently project-scoped by their path (/api/projects/...) are left alone.
const SCOPED_ENDPOINTS = ["/api/runs", "/api/investigations"];

function scopeURL(url) {
  const pid = state.project;
  if (!pid || !SCOPED_ENDPOINTS.some((p) => url === p || url.startsWith(p + "?"))) return url;
  return url + (url.includes("?") ? "&" : "?") + "project=" + encodeURIComponent(pid);
}

async function getJSON(url) {
  const r = await fetch(scopeURL(url));
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
  return r.json();
}

async function postJSON(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
                               body: JSON.stringify(body || {}) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}
function agoTime(ts) {
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 60) return `${Math.floor(s)}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}
function fmtDur(s) {
  if (s == null || isNaN(s)) return "—";
  if (s < 1) return `${Math.round(s * 1000)}ms`;
  if (s < 60) return `${s.toFixed(1)}s`;
  if (s < 3600) { const m = Math.floor(s / 60), r = Math.round(s % 60); return `${m}m${r ? " " + r + "s" : ""}`; }
  if (s < 86400) { const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60); return `${h}h${m ? " " + m + "m" : ""}`; }
  const d = Math.floor(s / 86400), h = Math.round((s % 86400) / 3600);
  return `${d}d${h ? " " + h + "h" : ""}`;
}
const round1 = (x) => Math.round(x * 10) / 10;
const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const state = { view: "runs", runId: null, sse: null, project: null, projects: [] };

// Views owned by projects.js (the analysis profile, its onboarding and its corpus page) register
// themselves here.
const EXTRA_VIEWS = {};

function setActiveNav(view) {
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.view === view));
}
function closeStream() { if (state.sse) { state.sse.close(); state.sse = null; } }

async function route() {
  const hash = location.hash.replace(/^#/, "") || "runs";
  const [view, arg] = hash.split("/");
  state.view = view; setActiveNav(view); closeStream(); closeWorkflow();
  if (typeof closeProjectViews === "function") closeProjectViews();
  // A link to a specific run must WORK, whatever analysis you happen to be in. Scoping is there to
  // reduce noise, not to make a URL you were sent resolve to the wrong thing — or to nothing.
  if (arg && ["workflow", "tree", "runs"].includes(view) && typeof ensureScopeForRun === "function")
    await ensureScopeForRun(arg);
  if (EXTRA_VIEWS[view]) EXTRA_VIEWS[view](arg || null);
  else if (view === "graph") renderGraph();
  else if (view === "review") renderReview();
  else if (view === "workflow") renderWorkflow(arg || null);
  else if (view === "tree") renderTree(arg || null);
  else renderRuns(arg || null);
}
window.addEventListener("hashchange", route);

// ============================================================================
// RUNS
// ============================================================================
async function renderRuns(runId) {
  main.innerHTML = "";
  const layout = el("div", { class: "runs-layout" });
  const listCol = el("div", { class: "run-list" }, [el("div", { class: "loading" }, "Loading runs…")]);
  const streamCol = el("div", { class: "stream-wrap" });
  const vitalsCol = el("div", { class: "vitals" });
  layout.append(listCol, streamCol, vitalsCol);
  main.appendChild(layout);

  let trees;
  try { trees = await getJSON("/api/investigations"); }
  catch (e) { listCol.innerHTML = ""; listCol.appendChild(el("div", { class: "empty" }, e.message)); return; }
  if (!trees.length) { listCol.innerHTML = ""; listCol.appendChild(el("div", { class: "empty" }, "No runs yet")); return; }

  const allRuns = trees.flatMap((t) => t.runs);
  const active = runId && allRuns.find((r) => r.run_id === runId)
    ? runId : ((trees[0].root_run || trees[0].runs[0]).run_id);
  state.runId = active;

  // Each investigation is a tree: root run + its forked branches, indented by fork depth.
  listCol.innerHTML = "";
  for (const t of trees) {
    const grp = el("div", { class: "inv-group" });
    if (t.has_forks)
      grp.appendChild(el("div", { class: "inv-head" }, [
        el("span", { class: "ih-icon" }, "⑃"),
        el("span", {}, `${t.n_branches} branch${t.n_branches === 1 ? "" : "es"}`),
      ]));
    for (const r of t.runs) grp.appendChild(runRow(r, active));
    listCol.appendChild(grp);
  }
  await loadRun(active, streamCol, vitalsCol);
}

async function loadRun(runId, streamCol, vitalsCol) {
  streamCol.innerHTML = ""; streamCol.appendChild(el("div", { class: "loading" }, `Loading ${runId}…`));
  let run;
  try { run = await getJSON(`/api/runs/${encodeURIComponent(runId)}`); }
  catch (e) { streamCol.innerHTML = ""; streamCol.appendChild(el("div", { class: "empty" }, e.message)); return; }

  streamCol.innerHTML = "";
  const head = el("div", { class: "stream-head" }, [
    el("span", { class: "rid" }, run.run_id),
    ...beamBadges(run.beam),
    run.parent
      ? el("span", { class: "parent-link", title: "go to parent branch",
          onclick: () => { location.hash = `runs/${encodeURIComponent(run.parent)}`; } }, `↰ ${run.parent}`)
      : null,
    // "Complete" is a claim the trace has to earn: an agent says `done` when it finishes. A run that is
    // merely quiet has not finished; a forking parent blocks for as long as its whole subtree runs.
    run.active
      ? el("span", { class: "badge live" }, [el("span", { class: "tick" }), "Streaming"])
      : run.last_action === "done"
        ? el("span", { class: "badge" }, "Complete")
        : el("span", { class: "badge idle", title: "no `done` in the trace — the agent stopped writing "
                       + "without finishing, or is blocked forking its subtree" }, "Idle"),
    el("span", { class: "grow" }),
    el("span", { class: "count", id: "stepcount" }, `${run.n_steps} steps`),
  ]);
  const stream = el("div", { class: "stream" });
  streamCol.append(head, stream);
  for (const s of run.steps) stream.appendChild(stepEl(s));
  renderVitals(vitalsCol, run);

  closeStream();
  if (!run.active) return;
  const es = new EventSource(`/api/runs/${encodeURIComponent(runId)}/stream?from=${run.resume_line || 0}`);
  state.sse = es;
  const live = { ...run.tallies };
  let count = run.n_steps;
  let firstTs = (run.steps.find((x) => typeof x.ts === "number") || {}).ts;
  es.addEventListener("step", (ev) => {
    const s = JSON.parse(ev.data);
    if (!s) return;
    count += 1;
    if (typeof s.dt_s === "number") {
      live.has_timing = true;
      live.busy_s = round1((live.busy_s || 0) + s.dt_s);
      live.slowest_s = Math.max(live.slowest_s || 0, s.dt_s);
    }
    if (typeof s.ts === "number") { if (firstTs == null) firstTs = s.ts; live.wall_s = round1(s.ts - firstTs); }
    live.steps = (live.steps || 0) + 1;
    live.by_family = live.by_family || {};
    live.by_family[s.family] = (live.by_family[s.family] || 0) + 1;
    if (s.action === "run_experiments") live.experiments = (live.experiments || 0) + 1;
    if (s.action === "submit") live.submissions = (live.submissions || 0) + 1;
    if (s.family === "retrieve") live.retrievals = (live.retrievals || 0) + 1;
    const node = stepEl(s, true);
    stream.appendChild(node);
    node.scrollIntoView({ behavior: "smooth", block: "end" });
    renderVitals(vitalsCol, { ...run, tallies: live });
    const sc = $("#stepcount"); if (sc) sc.textContent = `${count} steps`;
  });
  es.addEventListener("end", () => es.close());
  es.onerror = () => {};
}

const PHASE_LABEL = { retrieve: "Retrieve", execute: "Execute", falsify: "Falsify",
  fork: "Fork", generate: "Generate", grade: "Grade", note: "Note" };

// Beam badges for a forked branch (from its parent's recorded fork metadata).
function beamBadges(beam) {
  if (!beam) return [];
  const out = [];
  if (beam.adversarial)
    out.push(el("span", { class: "bchip adv", title: "mandated adversarial red-team branch — its job was to falsify the leading hypothesis" }, "ADV"));
  out.push(el("span", { class: "bchip " + (beam.kept ? "kept" : "pruned"),
    title: beam.reason || (beam.kept ? "deepened" : "pruned") }, beam.kept ? "deepened" : "pruned"));
  if (beam.rank != null) out.push(el("span", { class: "bchip rank", title: "promise rank" }, "#" + beam.rank));
  return out;
}

function runRow(r, active) {
  const isRoot = r.depth === 0;
  const label = isRoot ? r.run_id : "~" + r.run_id.split("~").slice(1).join("~");
  return el("div", {
    class: "run-item" + (r.run_id === active ? " active" : "") + (isRoot ? " root" : " branch"),
    style: `padding-left:${10 + r.depth * 15}px`,
    onclick: () => { location.hash = `runs/${encodeURIComponent(r.run_id)}`; },
  }, [
    el("div", { class: "rid" }, [
      r.depth ? el("span", { class: "tw" }, "└ ") : null,
      el("span", {}, label),
      ...beamBadges(r.beam),
    ]),
    el("div", { class: "rmeta" }, [
      r.active ? el("span", { class: "badge live" }, [el("span", { class: "tick" }), "Live"]) : null,
      el("span", { class: "num" }, `${r.steps} steps`),
      el("span", {}, "·"),
      el("span", {}, agoTime(r.updated_at)),
    ]),
  ]);
}

function stepEl(s, fresh = false) {
  const fam = s.family || "note";
  const body = [];
  body.push(el("div", { class: "shead" }, [
    el("span", { class: "phase" }, [el("span", { class: `pd ${fam}` }), PHASE_LABEL[fam] || s.phase || "Step"]),
    el("span", { class: "chip" }, s.action || "—"),
    el("span", { class: "grow" }),
    el("span", { class: "stepno" }, `#${s.step ?? ""}`),
    s.dt_s != null ? el("span", { class: "lat", title: "step wall-clock" }, fmtDur(s.dt_s)) : null,
  ]));
  if (s.reasoning) body.push(el("div", { class: "reasoning" }, s.reasoning));

  if (s.args && Object.keys(s.args).length) {
    const parts = [];
    for (const [k, v] of Object.entries(s.args)) {
      const val = typeof v === "object" ? JSON.stringify(v) : String(v);
      parts.push(`<span class="k">${esc(k)}:</span> ${esc(val.slice(0, 300))}`);
    }
    body.push(el("div", { class: "args", html: parts.join("&nbsp;&nbsp;") }));
  }
  if (s.fork && s.fork.children && s.fork.children.length) {
    body.push(beamPanel(s.fork));
  }
  if (s.observation) {
    const obs = String(s.observation);
    body.push(el("div", { class: "obs" }, obs.length > 1400 ? obs.slice(0, 1400) + "\n…" : obs));
  }
  if (s.thinking) {
    const think = el("div", { class: "thinking", style: "display:none" }, s.thinking);
    const tog = el("div", { class: "disclose" }, "Show thinking");
    tog.addEventListener("click", () => {
      const open = think.style.display === "none";
      think.style.display = open ? "block" : "none";
      tog.textContent = open ? "Hide thinking" : "Show thinking";
    });
    body.push(tog, think);
  }
  return el("div", { class: `step${fresh ? " fresh" : ""}` }, body);
}

// The beam a fork produced: expand → judge → prune/deepen. Each child row shows its angle, whether it was
// the mandated adversary, deepened vs pruned, promise rank, and top result. Clicking a child opens it.
function beamPanel(f) {
  const rows = (f.children || []).map((c) => {
    const top = c.top;
    return el("div", { class: "beam-row " + (c.kept ? "kept" : "pruned") }, [
      el("span", { class: "bchip " + (c.kept ? "kept" : "pruned") }, c.kept ? "deepened" : "pruned"),
      c.adversarial ? el("span", { class: "bchip adv" }, "ADV") : null,
      el("span", { class: "brid", title: "open this branch",
        onclick: (e) => { e.stopPropagation(); location.hash = `runs/${encodeURIComponent(c.run_id)}`; } },
        c.run_id),
      el("span", { class: "bangle" }, c.angle || ""),
      el("span", { class: "grow" }),
      top ? el("span", { class: "btop", title: "top result" },
        `${top.label || "?"} eff ${fmtE(top.effect)}`) : null,
      c.n_submitted ? el("span", { class: "bsub" }, `${c.n_submitted} sub`) : null,
      c.rank != null ? el("span", { class: "brank" }, "#" + c.rank) : null,
    ]);
  });
  return el("div", { class: "beam" }, [
    el("div", { class: "beam-head" },
      `beam · ${f.n_leaves} branch${f.n_leaves === 1 ? "" : "es"} · deepened ${f.n_deepened} · ` +
      `budget ${f.budget_remaining} left`),
    ...rows,
  ]);
}

function fmtE(x) {
  if (x == null) return "—";
  if (x >= 1000 || (x > 0 && x < 0.01)) return x.toExponential(1);
  return String(Math.round(x * 100) / 100);
}

function renderVitals(col, run) {
  const t = run.tallies || {};
  const fam = t.by_family || {};
  col.innerHTML = "";

  col.appendChild(el("div", { class: "sec" }, "Activity"));
  col.appendChild(el("div", { class: "tiles" }, [
    tile(t.steps || 0, "steps"),
    tile(t.experiments || 0, "experiments"),
    tile(t.submissions || 0, "submitted"),
    tile(t.retrievals || 0, "retrievals"),
  ]));

  if (t.has_timing) {
    col.appendChild(el("div", { class: "sec" }, "Timing"));
    col.appendChild(el("div", { class: "tiles" }, [
      tile(fmtDur(t.wall_s), "wall time"),
      tile(fmtDur(t.busy_s), "compute"),
      tile(fmtDur(t.slowest_s), "slowest step"),
      tile(t.steps ? fmtDur((t.busy_s || 0) / t.steps) : "—", "avg / step"),
    ]));
  }

  const order = ["retrieve", "execute", "falsify", "fork", "generate", "grade", "note"];
  const shown = order.filter((f) => fam[f]);
  if (shown.length) {
    const max = Math.max(1, ...shown.map((f) => fam[f]));
    col.appendChild(el("div", { class: "sec" }, "Phase mix"));
    col.appendChild(el("div", { class: "mix" }, shown.map((f) =>
      el("div", { class: "mix-row" }, [
        el("div", { class: "ml" }, f),
        el("div", { class: "track" }, [el("div", { class: `bar ${f}`, style: `width:${(fam[f] / max) * 100}%` })]),
        el("div", { class: "mc" }, String(fam[f])),
      ]))));
  }

  const tests = run.tests || [];
  if (tests.length) {
    col.appendChild(el("div", { class: "sec" }, `Verdicts · ${tests.length}`));
    for (const v of tests) col.appendChild(verdictEl(v));
  }
}
function tile(v, l) {
  return el("div", { class: "tile" }, [el("div", { class: "v" }, String(v)), el("div", { class: "l" }, l)]);
}
// A kill's KIND is its status. Only `refuted` is a claim about the hypothesis; the rest are statements
// about the test, and they are amber.
const KILL_LABELS = {
  refuted: ["danger", "Refuted"],            // the data went the other way — a result
  invalid: ["warn", "Invalid"],              // nothing was measured; fix and re-run
  underpowered: ["warn", "Underpowered"],    // could not decide; needs more units
  inconclusive: ["warn", "Inconclusive"],    // ran, found nothing; not evidence of absence
  killed: ["warn", "Killed"],                // kind unknown
};
function verdictKind(v) {
  const st = (v.status || "").toLowerCase();
  if (v.human_review === "validated") return ["good", "Validated"];
  if (KILL_LABELS[st]) return KILL_LABELS[st];
  if (st === "candidate") return ["", "Candidate"];
  return ["", st || "—"];
}
function verdictEl(v) {
  const [cls, label] = verdictKind(v);
  const nums = [];
  if (v.effect != null) nums.push(`eff ${(+v.effect).toFixed(3)}`);
  if (v.p_null != null) nums.push(`p ${(+v.p_null).toExponential(1)}`);
  return el("div", { class: "verdict" }, [
    el("div", { class: "vt" }, [
      el("span", { class: `badge ${cls}` }, label),
      el("span", { class: "rel" }, `${v.subject} → ${v.object}`),
      el("span", { class: "grow" }),
      v.run_id && v.run_id.includes("~")
        ? el("span", { class: "vbranch", title: "forked branch that produced this verdict",
            onclick: () => { location.hash = `runs/${encodeURIComponent(v.run_id)}`; } },
            "~" + v.run_id.split("~").slice(1).join("~"))
        : null,
    ]),
    v.verdict_note ? el("div", { class: "vn" }, v.verdict_note) : null,
    nums.length ? el("div", { class: "nums" }, nums.join("  ·  ")) : null,
  ]);
}

// ============================================================================
// KNOWLEDGE GRAPH
// ============================================================================
async function renderGraph() {
  main.innerHTML = "";
  const head = el("div", { class: "page-head" }, [el("h1", {}, "Knowledge graph")]);
  main.appendChild(head);
  // A project with no graph yet has nothing to draw, and a force-layout of zero nodes is a blank
  // rectangle that looks like a bug. Hand those cases to the corpus page, which can actually explain
  // what is missing and offer the build that fixes it.
  if (state.project && typeof kgEmptyState === "function") {
    const stand_in = await kgEmptyState(main, head);
    if (stand_in) return;
  }
  const layout = el("div", { class: "graph-layout" });
  const wrap = el("div", { class: "graph-canvas-wrap" });
  const canvas = el("canvas", { id: "kg-canvas" });
  const controls = el("div", { class: "graph-controls" });
  wrap.append(canvas, controls);
  const side = el("div", { class: "graph-side" }, [el("div", { class: "loading" }, "Loading graph…")]);
  layout.append(wrap, side);
  main.appendChild(layout);

  let sources;
  try { sources = (await getJSON("/api/kg?limit=10")).sources || []; }
  catch (e) { side.innerHTML = ""; side.appendChild(el("div", { class: "empty" }, e.message)); return; }

  // The active project is a source key (webui/data.kg_sources), so the graph shown by default is the
  // graph of the current analysis, never another corpus.
  const picked = state.project && sources.includes(state.project) ? state.project : sources[0];
  const sourceSel = el("select", { class: "select" }, sources.map((s) =>
    el("option", { value: s, ...(s === picked ? { selected: "selected" } : {}) }, s)));
  sourceSel.value = picked || "";
  const statusSel = el("select", { class: "select" }, [
    el("option", { value: "" }, "All claims"),
    el("option", { value: "disputed" }, "Disputed only"),
    el("option", { value: "established" }, "Established only"),
  ]);
  const limitSel = el("select", { class: "select" }, ["120", "220", "400", "600"].map((n) =>
    el("option", { value: n, ...(n === "220" ? { selected: "selected" } : {}) }, `${n} edges`)));
  controls.append(sourceSel, statusSel, limitSel);

  const draw = async () => {
    side.innerHTML = ""; side.appendChild(el("div", { class: "loading" }, "Loading…"));
    let g;
    try {
      const p = new URLSearchParams({ source: sourceSel.value, limit: limitSel.value });
      if (statusSel.value) p.set("status", statusSel.value);
      g = await getJSON(`/api/kg?${p}`);
    } catch (e) { side.innerHTML = ""; side.appendChild(el("div", { class: "empty" }, e.message)); return; }
    renderGraphSide(side, g);
    startForce(canvas, g);
  };
  sourceSel.onchange = statusSel.onchange = limitSel.onchange = draw;
  await draw();
}

function renderGraphSide(side, g) {
  side.innerHTML = "";
  side.appendChild(el("div", { class: "sec" }, "Corpus"));
  side.appendChild(el("div", { class: "tiles" }, [
    tile(g.total_claims.toLocaleString(), "total claims"),
    tile(g.nodes.length, "entities"),
    tile(g.shown, "edges shown"),
    tile(g.status_counts.disputed || 0, "disputed"),
  ]));
  side.appendChild(el("div", { class: "sec" }, "Edges"));
  const leg = [
    [cssVar("--good"), "Activates / positive"],
    [cssVar("--danger"), "Represses / negative"],
    [cssVar("--warn"), "Disputed (contradiction)"],
    [cssVar("--muted"), "Neutral / other"],
  ];
  for (const [c, t] of leg)
    side.appendChild(el("div", { class: "legend-row" }, [el("span", { class: "sw", style: `background:${c}` }), t]));
  side.appendChild(el("div", { class: "sec" }, "Selection"));
  side.appendChild(el("div", { id: "kg-detail", class: "empty", style: "padding:8px 0;text-align:left" },
    "Click a node to inspect its edges"));
}

let kgAnim = null;
function startForce(canvas, g) {
  if (kgAnim) cancelAnimationFrame(kgAnim);
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  function resize() {
    const w = Math.round(canvas.clientWidth * dpr), h = Math.round(canvas.clientHeight * dpr);
    if (w && h && (canvas.width !== w || canvas.height !== h)) {
      canvas.width = w; canvas.height = h; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
  }
  resize(); window.onresize = resize;
  const W = () => canvas.clientWidth, H = () => canvas.clientHeight;

  const nodes = g.nodes.map((n, i) => ({
    ...n, x: W() / 2 + Math.cos(i) * (40 + i % 130), y: H() / 2 + Math.sin(i * 1.3) * (40 + i % 90), vx: 0, vy: 0,
  }));
  const idx = new Map(nodes.map((n) => [n.id, n]));
  const edges = g.edges.map((e) => ({ ...e, s: idx.get(e.source), t: idx.get(e.target) })).filter((e) => e.s && e.t);

  const view = { x: 0, y: 0, k: 1 };
  let selected = null, hovered = null, alpha = 1;
  let dragging = null, panning = false, last = null, userMoved = false;

  const colors = () => ({
    good: cssVar("--good"), danger: cssVar("--danger"), warn: cssVar("--warn"),
    muted: cssVar("--muted"), accent: cssVar("--accent"), accentInk: cssVar("--accent-ink"),
    card: cssVar("--card"), ink: cssVar("--ink"), ink2: cssVar("--ink-2"),
  });
  const edgeColor = (e, C) => e.status === "disputed" ? C.warn : e.polarity > 0 ? C.good : e.polarity < 0 ? C.danger : C.muted;
  const nodeR = (n) => 3 + Math.min(10, Math.sqrt(n.degree) * 1.7);

  function tick() {
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j];
        let dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy || 0.01;
        const rep = 2600 / d2, d = Math.sqrt(d2), fx = (dx / d) * rep, fy = (dy / d) * rep;
        a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
      }
    }
    for (const e of edges) {
      let dx = e.t.x - e.s.x, dy = e.t.y - e.s.y, d = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const f = (d - 70) * 0.015, fx = (dx / d) * f, fy = (dy / d) * f;
      e.s.vx += fx; e.s.vy += fy; e.t.vx -= fx; e.t.vy -= fy;
    }
    const cx = W() / 2, cy = H() / 2;
    for (const n of nodes) {
      n.vx += (cx - n.x) * 0.002; n.vy += (cy - n.y) * 0.002; n.vx *= 0.86; n.vy *= 0.86;
      if (n !== dragging) { n.x += n.vx * alpha; n.y += n.vy * alpha; }
    }
    alpha = Math.max(0.02, alpha * 0.994);
  }
  function fitCamera() {
    if (userMoved || !nodes.length) return;
    let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
    for (const n of nodes) { if (n.x < minx) minx = n.x; if (n.x > maxx) maxx = n.x; if (n.y < miny) miny = n.y; if (n.y > maxy) maxy = n.y; }
    const pad = 70, gw = Math.max(1, maxx - minx), gh = Math.max(1, maxy - miny);
    const tk = Math.min((W() - 2 * pad) / gw, (H() - 2 * pad) / gh, 2.2);
    const cx = (minx + maxx) / 2, cy = (miny + maxy) / 2;
    view.k += (tk - view.k) * 0.12;
    view.x += (W() / 2 - cx * tk - view.x) * 0.12;
    view.y += (H() / 2 - cy * tk - view.y) * 0.12;
  }
  const toScreen = (n) => ({ x: n.x * view.k + view.x, y: n.y * view.k + view.y });

  function draw() {
    const C = colors();
    ctx.clearRect(0, 0, W(), H());
    const neigh = new Set();
    if (selected) for (const e of edges) { if (e.s === selected) neigh.add(e.t); if (e.t === selected) neigh.add(e.s); }
    for (const e of edges) {
      const dim = selected && !(e.s === selected || e.t === selected);
      const s = toScreen(e.s), t = toScreen(e.t);
      ctx.strokeStyle = edgeColor(e, C);
      ctx.globalAlpha = dim ? 0.05 : (e.status === "disputed" ? 0.8 : 0.45);
      ctx.lineWidth = (e.status === "disputed" ? 1.6 : 0.8) * view.k;
      ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(t.x, t.y); ctx.stroke();
    }
    ctx.globalAlpha = 1;
    for (const n of nodes) {
      const p = toScreen(n), r = nodeR(n) * view.k;
      const isSel = n === selected, isHi = selected && neigh.has(n);
      ctx.globalAlpha = selected && !isSel && !isHi ? 0.22 : 1;
      ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      ctx.fillStyle = isSel ? C.accentInk : C.accent; ctx.fill();
      ctx.lineWidth = 1.5; ctx.strokeStyle = C.card; ctx.stroke();
      if (n.degree >= 3 || isSel || isHi || n === hovered) {
        ctx.globalAlpha = selected && !isSel && !isHi ? 0.3 : 1;
        ctx.fillStyle = isSel ? C.ink : C.ink2;
        ctx.font = `${isSel ? 600 : 400} ${isSel ? 12.5 : 11}px "Source Sans 3", sans-serif`;
        ctx.fillText(n.label, p.x + r + 4, p.y + 3.5);
      }
    }
    ctx.globalAlpha = 1;
  }
  function loop() { resize(); tick(); fitCamera(); draw(); kgAnim = requestAnimationFrame(loop); }
  loop();

  const pick = (mx, my) => {
    for (let i = nodes.length - 1; i >= 0; i--) {
      const p = toScreen(nodes[i]), r = nodeR(nodes[i]) * view.k + 3;
      if ((mx - p.x) ** 2 + (my - p.y) ** 2 <= r * r) return nodes[i];
    }
    return null;
  };
  canvas.onmousedown = (e) => {
    const hit = pick(e.offsetX, e.offsetY);
    if (hit) { dragging = hit; selected = hit; alpha = Math.max(alpha, 0.4); showDetail(hit); }
    else { panning = true; userMoved = true; }
    last = { x: e.clientX, y: e.clientY };
  };
  window.addEventListener("mousemove", (e) => {
    if (dragging) { dragging.x = (e.offsetX - view.x) / view.k; dragging.y = (e.offsetY - view.y) / view.k; }
    else if (panning && last) { view.x += e.clientX - last.x; view.y += e.clientY - last.y; last = { x: e.clientX, y: e.clientY }; }
  });
  window.addEventListener("mouseup", () => { dragging = null; panning = false; });
  canvas.onmousemove = (e) => { hovered = pick(e.offsetX, e.offsetY); canvas.style.cursor = hovered ? "pointer" : "grab"; };
  canvas.onwheel = (e) => {
    e.preventDefault(); userMoved = true;
    const f = e.deltaY < 0 ? 1.1 : 0.9, mx = e.offsetX, my = e.offsetY;
    view.x = mx - (mx - view.x) * f; view.y = my - (my - view.y) * f; view.k *= f;
  };
  function showDetail(n) {
    const box = $("#kg-detail"); if (!box) return;
    const C = colors();
    const inbound = edges.filter((e) => e.t === n), outbound = edges.filter((e) => e.s === n);
    box.className = ""; box.style.textAlign = "left";
    box.innerHTML = `<div style="font-family:var(--mono);font-size:var(--t-md);font-weight:600;margin-bottom:4px">${esc(n.label)}</div>
      <div style="color:var(--muted);font-size:var(--t-xs);margin-bottom:10px">${n.degree} edges${n.function ? " · " + esc(n.function) : ""}</div>`;
    const list = el("div", {});
    for (const e of outbound.slice(0, 14)) list.appendChild(edgeLine(n.label, e.predicate, e.t.label, e, C));
    for (const e of inbound.slice(0, 14)) list.appendChild(edgeLine(e.s.label, e.predicate, n.label, e, C));
    box.appendChild(list);
  }
  function edgeLine(a, pred, b, e, C) {
    return el("div", { style: "font-family:var(--mono);font-size:var(--t-xs);padding:5px 0;border-bottom:1px solid var(--line);color:var(--ink-2)" }, [
      el("span", { style: "color:var(--ink)" }, a),
      el("span", { style: `color:${edgeColor(e, C)};padding:0 5px` }, ` ${pred} `),
      el("span", { style: "color:var(--ink)" }, b),
      e.status === "disputed" ? el("span", { style: "color:var(--warn-ink)" }, "  ⚠") : null,
    ]);
  }
}

// ============================================================================
// REVIEW
// ============================================================================
async function renderReview() {
  main.innerHTML = "";
  main.appendChild(el("div", { class: "page-head" }, [el("h1", {}, "Review")]));
  const scroll = el("div", { class: "review-scroll" }, [el("div", { class: "loading" }, "Loading queue…")]);
  main.appendChild(scroll);

  let q;
  try { q = await getJSON("/api/review" + (state.project ? `?project=${encodeURIComponent(state.project)}` : "")); }
  catch (e) { scroll.innerHTML = ""; scroll.appendChild(el("div", { class: "empty" }, e.message)); return; }
  scroll.innerHTML = "";

  // --- promotion gate ---
  const decided = { ...(q.promo_decided || {}) };
  scroll.appendChild(el("div", { class: "sec" },
    `Promotion gate · ${q.candidates.length} candidate${q.candidates.length === 1 ? "" : "s"} awaiting sign-off`));

  const applyBtn = el("button", { class: "btn primary", onclick: applyDecisions });
  const applyCount = el("span", { class: "apply-count" });
  const applyErr = el("div", { class: "promo-err", style: "display:none;width:100%" });
  const applyBar = el("div", { class: "apply-bar" }, [applyCount, el("span", { class: "grow" }), applyBtn, applyErr]);
  function refreshApplyBar() {
    const n = Object.keys(decided).length;
    applyCount.textContent = n
      ? `${n} decision${n === 1 ? "" : "s"} recorded, not yet applied`
      : "No decisions recorded yet";
    applyBtn.textContent = n ? `Apply ${n} → master graph` : "Apply → master graph";
    applyBtn.disabled = !n;
  }
  async function applyDecisions() {
    applyBtn.disabled = true; applyBtn.textContent = "Applying…"; applyErr.style.display = "none";
    try {
      const r = await fetch("/api/review/promotion/apply", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project: state.project }) });
      const s = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(s.error || r.statusText);
      applyBar.replaceChildren(el("span", { class: "decided ok" },
        `✓ Applied — promoted ${s.promoted || 0} · rejected ${s.rejected || 0} · skipped ${s.skipped || 0}`));
      setTimeout(renderReview, 1000);
    } catch (err) {
      refreshApplyBar(); applyErr.textContent = "⚠ " + err.message; applyErr.style.display = "block";
    }
  }
  refreshApplyBar();
  if (q.candidates.length) scroll.appendChild(applyBar);
  else scroll.appendChild(el("div", { class: "empty", style: "text-align:left;padding:8px 0" },
    "No candidates awaiting review. Surviving hypotheses land here after an engine run."));
  for (const c of q.candidates) scroll.appendChild(candidateCard(c, decided, refreshApplyBar));
}

function candidateCard(c, decided, refreshApplyBar) {
  const tid = String(c.test_id);
  const nums = [];
  if (c.effect != null) nums.push(["effect", (+c.effect).toFixed(3)]);
  if (c.effect_size != null) nums.push(["|effect|", (+c.effect_size).toFixed(3)]);
  if (c.p_null != null) nums.push(["p(null)", (+c.p_null).toExponential(2)]);
  if (c.expected_sign != null && c.observed_sign != null)
    nums.push(["sign", `${c.expected_sign > 0 ? "+" : "−"} exp / ${c.observed_sign > 0 ? "+" : "−"} obs`]);

  const recChip = el("span", {});
  function paintChip() {
    const d = decided[tid];
    if (!d) { recChip.className = ""; recChip.textContent = ""; recChip.style.display = "none"; return; }
    recChip.style.display = "inline-flex";
    recChip.className = "rec-chip " + (d.decision === "validated" ? "ok" : "no");
    recChip.textContent = d.decision === "validated" ? "✓ Validated" : "✕ Rejected";
  }
  paintChip();

  const kids = [el("div", { class: "ch" }, [
    el("span", { class: "badge" }, "candidate"),
    el("span", { class: "rel" }, `${c.subject} ~ ${c.object}`),
    c.method ? el("span", { class: "chip trunc", title: c.method },
      c.method.length > 42 ? c.method.slice(0, 42) + "…" : c.method) : null,
    c.novelty_verdict ? el("span", { class: "badge" }, `novelty: ${c.novelty_verdict}`) : null,
    el("span", { class: "grow" }), recChip,
  ])];

  if (c.recommended_action)
    kids.push(el("div", { class: "recommend" }, [el("span", { class: "rk" }, "Suggested"), c.recommended_action]));
  if (c.hypothesis) kids.push(el("div", { class: "hyp" }, c.hypothesis));
  if (nums.length) kids.push(el("div", { class: "stat-line" }, nums.map(([k, v]) =>
    el("span", { class: "kv" }, [el("span", { class: "k" }, k), el("b", {}, v)]))));

  if (c.literature && c.literature.claim) {
    const cl = c.literature.claim;
    const rel = cl.polarity > 0 ? "activates" : cl.polarity < 0 ? "represses" : "relates to";
    kids.push(el("div", { class: "lit" }, [
      el("div", { class: "lit-h" }, [el("span", {}, "Literature claim"),
        cl.status ? el("span", { class: "chip" }, cl.status) : null]),
      el("div", { class: "lit-claim" }, `${cl.subject_label} ${cl.predicate || rel} ${cl.object_label}`),
      ...((c.literature.quotes || []).map((qt) => el("div", { class: "quote" }, `“${qt}”`))),
    ]));
  }

  // required note + verdict buttons
  const note = el("textarea", { class: "note-input", rows: "2",
    placeholder: "Why? — required for both. A validation's note is its provenance; a rejection's note is fed back to the engine as a correction." });
  if (decided[tid]) note.value = decided[tid].note || "";
  const vBtn = el("button", { class: "btn primary" }, "Validate & promote");
  const rBtn = el("button", { class: "btn danger" }, "Reject");
  const err = el("div", { class: "promo-err", style: "display:none" });
  const sync = () => { const ok = note.value.trim().length > 0; vBtn.disabled = rBtn.disabled = !ok; };
  note.addEventListener("input", sync); sync();

  async function decide(decision) {
    const n = note.value.trim(); if (!n) return;
    vBtn.disabled = rBtn.disabled = true; err.style.display = "none";
    try {
      const r = await fetch("/api/review/promotion", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ test_id: c.test_id, decision, note: n, project: state.project }) });
      const b = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(b.error || r.statusText);
      decided[tid] = { decision, note: n };
      paintChip(); refreshApplyBar(); sync();
    } catch (e2) { err.textContent = "⚠ " + e2.message; err.style.display = "block"; sync(); }
  }
  vBtn.addEventListener("click", () => decide("validated"));
  rBtn.addEventListener("click", () => decide("rejected"));

  kids.push(el("div", { class: "note-row" }, [note]));
  kids.push(el("div", { class: "actions" }, [vBtn, rBtn]));
  kids.push(err);
  return el("div", { class: "card" }, kids);
}

// ============================================================================
// theme + boot
// ============================================================================
const SUN = `<circle cx="12" cy="12" r="4.5"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>`;
const MOON = `<path d="M20 14.5A8 8 0 1 1 9.5 4 6.2 6.2 0 0 0 20 14.5Z"/>`;
const themeBtn = $("#theme-toggle");
function applyTheme(t) {
  document.documentElement.setAttribute("data-theme", t);
  $("#theme-label").textContent = t === "dark" ? "Dark" : "Light";
  $("#theme-icon").innerHTML = t === "dark" ? MOON : SUN;
  try { localStorage.setItem("dnhacksbio-theme", t); } catch {}
}
themeBtn.addEventListener("click", () => {
  applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark");
  // Re-route the workflow view so its canvases rebuild against the new theme.
  if (state.view === "workflow") route();
});
const urlTheme = new URLSearchParams(location.search).get("theme");
const savedTheme = (() => { try { return localStorage.getItem("dnhacksbio-theme"); } catch { return null; } })();
applyTheme(urlTheme === "light" || urlTheme === "dark" ? urlTheme : (savedTheme || "light"));

document.querySelectorAll("#nav a").forEach((a) =>
  a.addEventListener("click", () => { location.hash = a.dataset.view; }));

// NOTE: the first route() call lives at the very BOTTOM of this file, not here. Views defined below use
// module-level `let`/`const`, which are in the temporal dead zone until their declaration executes —
// routing to one of them mid-file throws "cannot access X before initialization".

// ============================================================================
// WORKFLOW — the engine's shape, driven by what actually happened
//
// Two views of one event stream (/api/events/<run>), sharing one playhead:
//
//   * the FLOWCHART is the hero. It answers "what are the stages and what feeds
//     what" — the question anyone new to the engine asks first — and it ANIMATES:
//     stages pulse as their events fire, submissions travel the verification
//     band, counters tick. Its layout is three bands (architecture.py `_POS`), so
//     every edge is either a straight hop to the next box in its band or one
//     deliberate elbow. No router: a layout where routing is trivial.
//
//   * the STRIP is history, compressed to ~70px: a faint density trace of every
//     step per branch, with milestones drawn on top. You scrub on it.
//
// Replay and live-follow are the same path — both only move the playhead.
// ============================================================================

const SPEEDS = [1, 2, 4, 8, 16, 60];
const STRIP_MAX_H = 96, STRIP_PAD = 6, STRIP_ROW_MIN = 5, STRIP_ROW_MAX = 11;
// The strip is history compressed, not a chart: it should be exactly as tall as it needs, so a
// single-branch run gets a thin ribbon instead of 70px of empty box.
const stripHeight = (rows) =>
  Math.round(STRIP_PAD * 2 + Math.min(STRIP_MAX_H - STRIP_PAD * 2,
             Math.max(STRIP_ROW_MIN, Math.min(STRIP_ROW_MAX, 44 / Math.max(1, rows))) * rows));
// The events worth a distinct mark. Everything else is density.
const MILESTONE = {
  fork:       { mark: "dia",  label: "forked" },
  experiment: { mark: "bar",  label: "ran code" },
  submit:     { mark: "chev", label: "submitted" },
  verdict:    { mark: "sq",   label: "verdict" },
  review:     { mark: "star", label: "reviewed" },
};
// Where a submission SITS, mapped to the box that shows it. `tested` and `novelty` have no boxes of their
// own (writes/annotations, not decisions), so both resolve to the falsifier's output side.
const STATION_OF = { queued: "queue", verified: "falsifier", tested: "falsifier",
                     novelty: "falsifier", review: "promote", master: "master" };

const wf = { model: null, arch: null, u: 0, playing: false, speed: 4, follow: true,
             raf: null, last: 0, strip: null, sctx: null, poll: null, retry: null,
             runId: null, boxes: {}, tokens: {}, onResize: null };

// --- state derivation (pure: everything shown is a function of playhead) -----
function stateAt(model, u) {
  const lanes = {}, subs = {}, pulse = {};
  const counts = { steps: 0, experiments: 0, killed: 0, candidates: 0, promoted: 0 };
  for (const l of model.lanes) {
    lanes[l.run_id] = { ...l, open: l.u_start != null && l.u_start <= u, pruned: false };
  }
  let current = null;
  const touch = (id, uu) => { pulse[id] = Math.max(pulse[id] || 0, uu); };
  for (const e of model.events) {
    if (e.u > u) break;
    const lane = lanes[e.run_id];
    switch (e.type) {
      case "step":
        counts.steps++;
        if (lane) lane.open = true;
        current = e;
        touch("explorer", e.u);
        if (e.action === "search_kg" || e.action === "neighbors" || e.action === "subgraph"
            || e.action === "path") touch("kg", e.u);
        if (e.action === "read_paper" || e.action === "search_papers") touch("papers", e.u);
        if (e.action === "get_skill" || e.action === "search_skills") touch("skills", e.u);
        if (e.action === "recall" || e.action === "log" || e.action === "reflect") touch("explog", e.u);
        break;
      case "experiment": counts.experiments += e.n || 1; touch("sandbox", e.u); break;
      case "fork":
        touch("fork", e.u);
        for (const c of e.children) if (lanes[c.run_id]) lanes[c.run_id].open = true;
        break;
      case "judged":
        for (const c of e.children) {
          const cl = lanes[c.run_id];
          if (cl) cl.pruned = !c.kept;
        }
        touch("fork", e.u);
        break;
      case "submit":
        touch("queue", e.u);
        subs[e.id] = { id: e.id, run_id: e.run_id, station: "queued",
                       label: `#${e.id}`,
                       hypothesis: `${e.subject || "?"} ~ ${e.object || "?"}`
                                   + (e.hypothesis ? `\n\n${e.hypothesis}` : "") };
        break;
      case "verdict":
        touch("falsifier", e.u);
        if (subs[e.id]) subs[e.id].station = "verified";
        break;
      case "tested":
        touch("writeback", e.u);
        if (subs[e.id]) { subs[e.id].station = "tested"; subs[e.id].status = e.status; }
        if (e.status && e.status !== "candidate") counts.killed++; else counts.candidates++;
        break;
      case "novelty": touch("novelty", e.u); if (subs[e.id]) subs[e.id].station = "novelty"; break;
      case "review":
        touch("promote", e.u);
        if (subs[e.id]) subs[e.id].station = e.decision === "validated" ? "master" : "review";
        if (e.decision === "validated") { counts.promoted++; touch("master", e.u); }
        break;
    }
  }
  return { lanes, subs, counts, current, pulse };
}

// --- the flowchart ----------------------------------------------------------
function flowchartEl(arch) {
  const strip = arch.nodes.filter((n) => n.strip);
  const band = (b) => arch.nodes.filter((n) => n.band === b).sort((x, y) => x.order - y.order);
  const mk = (n, cls) => {
    const box = el("div", { class: `fc-box ${cls}${n.lane === "human" ? " fc-human" : ""}`,
                            "data-id": n.id, tabindex: "0" }, [
      el("div", { class: "fc-name" }, n.label.split("  ")[0].trim()),
      el("div", { class: "fc-stat" }, "—"),
    ]);
    const open = () => openNodeDetail(n);
    box.addEventListener("click", open);
    box.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
    wf.boxes[n.id] = box;
    return box;
  };
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "fc-edges");

  // --- Knowledge graph: built offline, so it is collapsed unless something is actively building it.
  // It is context for the engine, not part of the live loop, and it should not compete for attention.
  const kgBoxes = band(1).map((n) => mk(n, ""));
  const kgBody = el("div", { class: "fc-band fc-band-kg" }, kgBoxes);
  const kgWrap = el("section", { class: "fc-sec fc-sec-kg collapsed" }, [
    el("div", { class: "fc-sec-head" }, [
      el("span", { class: "fc-caret" }, "▸"),
      el("h3", {}, "Knowledge graph"),
    ]),
    kgBody,
  ]);
  kgWrap.querySelector(".fc-sec-head").addEventListener("click", () => {
    kgWrap.classList.toggle("collapsed");
    kgWrap.querySelector(".fc-caret").textContent = kgWrap.classList.contains("collapsed") ? "▸" : "▾";
    requestAnimationFrame(() => drawFlowEdges(document.querySelector(".fc")));
  });
  wf.kgSection = kgWrap;

  // --- Engine: the live search tree, not stages. N agents run concurrently, each in its own state, so
  // "roam -> write -> execute" is a sequence inside one agent's step and never across the engine.
  const tree = el("div", { class: "fc-tree" }, [el("div", { class: "dim small" }, "waiting for a step…")]);
  wf.treeEl = tree;
  const engineWrap = el("section", { class: "fc-sec fc-sec-engine" }, [
    el("div", { class: "fc-sec-head static" }, [el("h3", {}, "Engine")]),
    tree,
  ]);

  // --- VERIFICATION: a buffer, one machine gate, one human gate, one destination.
  const vBoxes = band(2).map((n) => {
    const box = mk(n, "fc-station");
    box.appendChild(el("div", { class: "fc-slot", "data-station": n.id }));
    return box;
  });
  const verifyWrap = el("section", { class: "fc-sec fc-sec-verify" }, [
    el("div", { class: "fc-sec-head static" }, [el("h3", {}, "Verification")]),
    el("div", { class: "fc-band fc-band-verify" }, vBoxes),
  ]);

  return el("div", { class: "fc" }, [
    svg,
    el("div", { class: "fc-reads" }, [
      el("span", { class: "fc-reads-label" }, "reads"),
      ...strip.map((n) => {
        const chip = el("div", { class: "fc-chip", "data-id": n.id, tabindex: "0",
                                 onclick: () => openNodeDetail(n) },
          [el("b", {}, n.label.split("  ")[0].trim()), el("span", { class: "fc-stat" }, "—")]);
        wf.boxes[n.id] = chip;
        return chip;
      }),
    ]),
    kgWrap, engineWrap, verifyWrap,
  ]);
}

// The Engine section: a top-down search tree that BUILDS as the run replays. Compact by design — the
// Search tree tab carries the words (hypothesis, numbers, verdict); here a node is a dot, and what you
// read is the SHAPE: when it forked, how wide, what survived, what died.
const STAGE_DOT = { candidate: "ok", killed: "bad", verifying: "wait", submitted: "wait" };

function renderLiveTree(uNow) {
  const host = wf.treeEl, m = wf.model;
  if (!host || !m) return;
  const seen = new Set(), forks = [], ran = {};
  for (const e of m.events) {
    if (e.u > uNow) break;
    if (e.type === "step") seen.add(e.run_id);
    if (e.type === "experiment") ran[e.run_id] = (ran[e.run_id] || 0) + (e.n || 1);
    if (e.type === "fork") forks.push(e);
  }
  const forksOf = {};
  forks.forEach((f) => { (forksOf[f.run_id] ||= []).push(f); });
  // every experiment this branch ran, in order, with the outcome it ended up with
  const expOf = {};
  ((wf.tree && wf.tree.nodes) || []).forEach((n) => {
    if (n.kind === "experiment") (expOf[n.run_id] ||= []).push(n);
  });

  // Branches that are revealed but that no fork record names: the normal state of a LIVE fork, since the
  // parent writes its record only once the whole subtree is over. The run_id is path-encoded, so the
  // parent is recoverable from the id itself; place them there and mark them.
  const named = new Set();
  forks.forEach((f) => f.children.forEach((c) => named.add(c.run_id)));
  const unrecorded = {};
  [...seen].filter((r) => r !== m.root && !named.has(r) && r.includes("~"))
    .sort()
    .forEach((r) => { (unrecorded[r.slice(0, r.lastIndexOf("~"))] ||= []).push(r); });

  const drawn = new Set();
  const branch = (rid, meta) => {
    drawn.add(rid);
    const c = meta || {};
    const cls = ["lt-node"];
    if (c.adversarial) cls.push("adv");
    else if (c.kept) cls.push("kept");
    else if (meta && !c.unlinked) cls.push("pruned");
    if (c.unlinked) cls.push("unlinked");
    if (!seen.has(rid)) cls.push("pending");
    // What distinguishes a branch is its role and rank; the path-encoded id goes small underneath as
    // the thing you grep for. The adversary's outcome (rank, deepened or pruned) is shown, not just
    // the word "adversary".
    const role = c.unlinked ? "unlinked"
               : c.adversarial ? `adv${c.rank ? " #" + c.rank : ""} · ${c.kept ? "deepened" : "pruned"}`
               : (c.rank ? `#${c.rank}${c.kept ? " · deepened" : " · pruned"}` : "root");
    const node = el("div", { class: cls.join(" "),
                             title: `${rid}${c.angle ? "\n\n" + c.angle : ""}${c.reason ? "\n\njudge: " + c.reason : ""}` }, [
      el("div", { class: "lt-role" }, role),
      // the root shows the investigation id; a branch shows its `~` suffix
      el("div", { class: "lt-id" }, rid.includes("~") ? rid.slice(rid.indexOf("~")) : rid),
    ]);
    const wrap = el("div", { class: "lt-branch" }, [node]);

    // Experiments as nodes, revealed in order as the run replays and coloured by how each ended up.
    const all = expOf[rid] || [];
    const shown = all.slice(0, ran[rid] || 0);
    if (shown.length) {
      wrap.appendChild(el("div", { class: "lt-exps" }, shown.map((x) =>
        // `failed` means "reported no RESULT", not "the code failed": most RESULT-less experiments are
        // probes that ran fine and printed diagnostics. `raised` is the field that means a crash.
        el("div", { class: `lt-exp ${x.raised ? "fail" : x.failed ? "noresult" : (STAGE_DOT[x.stage] || "")}`,
                    title: `entry #${x.entry_id} · ${x.stage}`
                           + (x.raised ? " · code raised" : x.failed ? " · ran, no RESULT (probe)" : "")
                           + `\n${x.title || ""}` }))));
    }
    const gens = forksOf[rid] || [];
    if (gens.length) {
      // Each fork is a separate split from this node, laid side by side. A split needs no caption; only
      // a node with more than one split is numbered, since that is what the geometry cannot show.
      wrap.appendChild(el("div", { class: `lt-gens${gens.length > 1 ? " multi" : ""}` },
        gens.map((f, i) => {
          const kids = [...f.children].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));
          return el("div", { class: "lt-gen" }, [
            ...(gens.length > 1 ? [el("div", { class: "lt-forklabel" }, `split ${i + 1}`)] : []),
            el("div", { class: "lt-kids" }, kids.map((k) => branch(k.run_id, k))),
          ]);
        })));
    }
    // Children the records do not name yet, hung off the parent their id points at. Captioned, because
    // a branch placed by lineage carries no rank, angle or judge reason yet.
    const pending = unrecorded[rid] || [];
    if (pending.length) {
      wrap.appendChild(el("div", { class: "lt-gens" }, [
        el("div", { class: "lt-gen" }, [
          el("div", { class: "lt-forklabel unrecorded" }, "no fork record yet · placed by run_id"),
          el("div", { class: "lt-kids" }, pending.map((k) => branch(k, { unlinked: true }))),
        ]),
      ]));
    }
    return wrap;
  };

  host.innerHTML = "";
  if (!seen.size) { host.appendChild(el("div", { class: "dim small" }, "waiting for a step…")); return; }
  host.appendChild(branch(m.root, null));
  // Last resort: a branch whose lineage parent was never revealed either. Shallowest first, since
  // drawing a stranded parent recurses into the children it does name.
  const orphans = [...seen].filter((r) => !drawn.has(r))
    .sort((a, b) => (a.match(/~/g) || []).length - (b.match(/~/g) || []).length);
  const subtrees = [];
  for (const rid of orphans) {
    if (drawn.has(rid)) continue;           // already drawn under an earlier orphan, which DOES name it
    subtrees.push(branch(rid, { unlinked: true }));
  }
  if (subtrees.length) {
    host.appendChild(el("div", { class: "lt-unlinked" }, [
      el("b", {}, "UNLINKED"),
      el("span", {}, `${orphans.length} branch(es) with a trace but no fork record — `
                     + "position in the tree unknown"),
    ]));
    host.appendChild(el("div", { class: "lt-orphans" }, subtrees));
  }
  // Depth of what has been revealed, not of the finished tree.
  const depth = Math.max(0, ...[...seen].map((r) => (r.match(/~/g) || []).length));
  // Split points, not fork events: the record is written only when a fork completes, and a node splits
  // once, so the set of parents is the count in both worlds, recorded and still-running.
  const forkers = new Set([...forks.map((f) => f.run_id), ...Object.keys(unrecorded)]);
  host.appendChild(el("div", { class: "lt-key" }, [
    el("span", {}, `${seen.size} agents`), el("span", {}, `${forkers.size} forks`),
    el("span", {}, `${Object.values(ran).reduce((a, b) => a + b, 0)} experiments`),
    el("i", {}, "·"),
    el("span", { class: "k sq kept" }, "deepened"), el("span", { class: "k sq pruned" }, "pruned"),
    el("span", { class: "k sq adv" }, "adversary"),
    el("i", {}, "·"),
    el("span", { class: "k dot ok" }, "candidate"), el("span", { class: "k dot bad" }, "killed"),
    el("span", { class: "k dot fail" }, "code raised"),
    el("span", { class: "k dot noresult" }, "no result (probe)"),
    el("span", { class: "k dot" }, "logged only"),
    // State the shape in both directions. Depth >= 2 is the only evidence that a survivor split its own line.
    forkers.size ? el("b", { class: `lt-flag${depth >= 2 ? " ok" : ""}` },
      depth >= 2
        ? `· depth ${depth} · ${forkers.size} agents forked`
        : `· depth 1 · every branch came from the root — ${forkers.size} round(s) of beam search, `
          + `not a recursive tree`) : null,
  ].filter(Boolean)));
}

// Edges are drawn from the laid-out boxes; banding guarantees each is a straight hop.
function drawFlowEdges(container) {
  const svg = container.querySelector(".fc-edges");
  if (!svg) return;
  // An edge touching a VIRTUAL node (the engine, rendered as the live tree) has no box to anchor to.
  const drawable = (e) => wf.boxes[e.from] && wf.boxes[e.to];
  const cr = container.getBoundingClientRect();
  svg.setAttribute("viewBox", `0 0 ${cr.width} ${cr.height}`);
  svg.setAttribute("width", cr.width); svg.setAttribute("height", cr.height);
  svg.innerHTML = "";
  const NS = "http://www.w3.org/2000/svg";
  const defs = document.createElementNS(NS, "defs");
  for (const k of ["flow", "back", "feed"]) {
    const m = document.createElementNS(NS, "marker");
    m.setAttribute("id", `fa-${k}`); m.setAttribute("viewBox", "0 0 10 10");
    m.setAttribute("refX", "9"); m.setAttribute("refY", "5");
    m.setAttribute("markerWidth", "5"); m.setAttribute("markerHeight", "5");
    m.setAttribute("orient", "auto");
    const pa = document.createElementNS(NS, "path");
    pa.setAttribute("d", "M 0 1 L 10 5 L 0 9 z"); pa.setAttribute("class", `fc-arrow k-${k}`);
    m.appendChild(pa); defs.appendChild(m);
  }
  svg.appendChild(defs);

  const R = (id) => {
    const b = wf.boxes[id];
    // A collapsed section clips its children but does not resize them, so ask the section, not the box.
    if (!b || b.closest(".fc-sec.collapsed")) return null;
    const r = b.getBoundingClientRect();
    return { l: r.left - cr.left, r: r.right - cr.left, t: r.top - cr.top, b: r.bottom - cr.top,
             cx: r.left + r.width / 2 - cr.left, cy: r.top + r.height / 2 - cr.top };
  };
  const add = (d, kind, label) => {
    const pa = document.createElementNS(NS, "path");
    pa.setAttribute("d", d); pa.setAttribute("class", `fc-edge k-${kind}`);
    pa.setAttribute("marker-end", `url(#fa-${kind})`);
    if (label) { const ti = document.createElementNS(NS, "title"); ti.textContent = label; pa.appendChild(ti); }
    svg.appendChild(pa);
  };

  // straight hops along each band
  for (const b of [1, 2]) {
    const ids = wf.arch.nodes.filter((n) => n.band === b).sort((x, y) => x.order - y.order).map((n) => n.id);
    for (let i = 0; i < ids.length - 1; i++) {
      const a = R(ids[i]), z = R(ids[i + 1]);
      if (!a || !z) continue;
      add(`M ${a.r} ${a.cy} L ${z.l - 2} ${z.cy}`, "flow");
    }
  }
  // The cross-section relations (graph -> engine -> queue, and both gates returning) are not drawn as
  // arrows: the engine is a live tree with no box to anchor to. The section headers state them in words.
}

// --- the scrubber strip -----------------------------------------------------
function drawStrip(model, st, u) {
  const cv = wf.strip, ctx = wf.sctx;
  if (!cv || !ctx) return;
  const dpr = window.devicePixelRatio || 1, W = cv.clientWidth;
  const H = stripHeight(model.lanes.length);
  if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) {
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    cv.style.height = H + "px";
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  const x0 = 4, x1 = W - 4, span = Math.max(0.001, model.playback);
  const X = (uu) => x0 + (Math.min(uu, span) / span) * (x1 - x0);
  const css = (n) => cssVar(n) || "#888";
  const rows = model.lanes.length;
  const rowH = (H - STRIP_PAD * 2) / Math.max(1, rows);
  const yOf = (i) => STRIP_PAD + i * rowH + rowH / 2;
  const idx = Object.fromEntries(model.lanes.map((l, i) => [l.run_id, i]));

  // faint density: every step, one neutral tick. Busy-ness stays legible without a colour vocabulary.
  ctx.fillStyle = css("--ink-2");
  for (const e of model.events) {
    if (e.u > u) break;
    if (e.type !== "step") continue;
    const i = idx[e.run_id];
    if (i == null) continue;
    ctx.globalAlpha = (st.lanes[e.run_id] || {}).pruned ? 0.14 : 0.3;
    ctx.fillRect(X(e.u), yOf(i) - rowH * 0.34, 1, rowH * 0.68);
  }
  ctx.globalAlpha = 1;

  // lane baselines for branches that exist yet
  ctx.strokeStyle = css("--line-2"); ctx.lineWidth = 1;
  model.lanes.forEach((l, i) => {
    if (!(st.lanes[l.run_id] || {}).open) return;
    const y = yOf(i);
    ctx.beginPath(); ctx.moveTo(X(l.u_start ?? 0), y); ctx.lineTo(X(Math.min(l.u_end ?? span, u)), y);
    ctx.stroke();
  });

  // milestones on top — the only marks that need naming
  const COL = { fork: css("--p-fork"), experiment: css("--p-execute"), submit: css("--p-falsify"),
                verdict: css("--p-grade"), review: css("--accent") };
  wf.hits = [];
  for (const e of model.events) {
    if (e.u > u) break;
    const m = MILESTONE[e.type];
    if (!m) continue;
    const i = idx[e.run_id];
    if (i == null) continue;
    const x = X(e.u), y = yOf(i);
    ctx.fillStyle = COL[e.type] || css("--ink");
    const s = Math.max(2.6, rowH * 0.42);
    if (m.mark === "dia") { ctx.beginPath(); ctx.moveTo(x, y - s); ctx.lineTo(x + s, y);
                            ctx.lineTo(x, y + s); ctx.lineTo(x - s, y); ctx.closePath(); ctx.fill(); }
    else if (m.mark === "chev") { ctx.beginPath(); ctx.moveTo(x, y - s); ctx.lineTo(x + s, y + s);
                                  ctx.lineTo(x - s, y + s); ctx.closePath(); ctx.fill(); }
    else if (m.mark === "bar") ctx.fillRect(x - 1, y - s * 1.35, 2.4, s * 2.7);
    else ctx.fillRect(x - s * 0.8, y - s * 0.8, s * 1.6, s * 1.6);
    wf.hits.push({ x, y, e, label: m.label });
  }

  const px = X(u);
  ctx.strokeStyle = css("--accent"); ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(px, 2); ctx.lineTo(px, H - 2); ctx.stroke();
  ctx.fillStyle = css("--accent");
  ctx.beginPath(); ctx.arc(px, 4, 3, 0, Math.PI * 2); ctx.fill();
}

// --- painting ---------------------------------------------------------------
function paintFlow(model, st, u) {
  const fmt = (n) => (n == null ? "—" : String(n));
  const set = (id, text) => {
    const b = wf.boxes[id];
    if (!b) return;
    const s = b.querySelector(".fc-stat");
    if (s && s.textContent !== text) s.textContent = text;
    // "hot" = this node did something in the last moment of playback, which is what makes the chart move
    const hot = (st.pulse[id] != null) && (u - st.pulse[id] < 0.6);
    b.classList.toggle("hot", hot);
  };
  const c = st.counts;
  set("corpus_card", "loaded");
  set("kg", model.kg_claims ? `${model.kg_claims.toLocaleString()} claims` : "—");
  set("papers", model.papers ? `${model.papers.toLocaleString()} papers` : "—");
  set("explog", `${c.steps} steps logged`);
  set("skills", `${(wf.arch.nodes.find((n) => n.id === "skills") || {}).detail?.[0] || ""}`
      .match(/^\d+/)?.[0] ? `${(wf.arch.nodes.find((n) => n.id === "skills").detail[0].match(/^\d+/))[0]} guides` : "guides");
  set("sandbox", `${c.experiments} experiments`);
  const at = (station) => Object.values(st.subs).filter((s) => s.station === station).length;
  set("queue", `${at("queued")} waiting`);
  // The falsifier is the only machine gate, so it owns both of its outcomes.
  set("falsifier", `${c.candidates} candidate${c.candidates === 1 ? "" : "s"} · ${c.killed} killed`);
  // What awaits you: everything that survived and has not been human-reviewed.
  set("promote", `${Math.max(0, c.candidates - c.promoted)} awaiting you`);
  set("master", `${c.promoted} promoted`);

  for (const s of Object.values(st.subs)) {
    let tok = wf.tokens[s.id];
    if (!tok) { tok = el("div", { class: "fc-token", title: s.hypothesis || s.label }, s.label);
                wf.tokens[s.id] = tok; }
    // A verdict moves the submission on: a candidate is now waiting on the human, a refuted one is
    // terminal at the gate that killed it.
    const station = (s.station === "tested" || s.station === "novelty")
      ? (s.status === "candidate" ? "review" : "verified")
      : s.station;
    const host = wf.boxes[STATION_OF[station]];
    const slot = host && host.querySelector(".fc-slot");
    if (slot && tok.parentElement !== slot) slot.appendChild(tok);
    tok.className = "fc-token" + (s.status && s.status !== "candidate" ? " is-killed" : "")
                  + (s.status === "candidate" ? " is-candidate" : "");
  }
  for (const [id, tok] of Object.entries(wf.tokens)) {
    if (!st.subs[id] && tok.parentElement) tok.remove();
  }
}

function renderNow(model, st) {
  const now = $(".wf-now");
  if (!now) return;
  const e = st.current;
  const lane = st.lanes[e ? e.run_id : ""] || {};
  now.querySelector(".wf-now-run").textContent =
    (e ? e.run_id : "—") + (lane.adversarial ? "  (adversary)" : "");
  const act = now.querySelector(".wf-now-action");
  act.textContent = e ? `${e.phase || ""} · ${e.action || ""}` : "not started";
  act.dataset.family = e ? e.family : "note";
  now.querySelector(".wf-now-text").textContent = e ? (e.reasoning || e.observation || "") : "";
}

function wfRender() {
  if (!wf.model) return;
  const st = stateAt(wf.model, wf.u);
  drawStrip(wf.model, st, wf.u);
  paintFlow(wf.model, st, wf.u);
  // The tree grows as the run replays, which moves every box below it; redraw the edges only when the
  // tree's shape actually changed, not per frame.
  renderLiveTree(wf.u);          // the Engine section: the search tree building as it replays
  const sig = wf.treeEl ? wf.treeEl.childElementCount + ":" + wf.treeEl.querySelectorAll(".lt-node").length : "";
  if (sig !== wf.treeSig) {
    wf.treeSig = sig;
    requestAnimationFrame(() => { const fc = document.querySelector(".fc"); if (fc) drawFlowEdges(fc); });
  }
  renderNow(wf.model, st);
  const clock = $(".wf-clock");
  if (clock) {
    // Real engine time, taken from the event at the playhead (gaps are compressed unevenly).
    let at = wf.model.t0;
    for (const e of wf.model.events) { if (e.u > wf.u) break; at = e.t; }
    clock.textContent = `${fmtDur(at - wf.model.t0)} into a ${fmtDur(wf.model.duration)} run`;
  }
}
window.__wfRender = () => wfRender();

function wfTick(ts) {
  if (!wf.playing) { wf.raf = null; return; }
  const dt = wf.last ? Math.min(0.25, (ts - wf.last) / 1000) : 0;
  wf.last = ts;
  wf.u = Math.min(wf.model.playback, wf.u + dt * wf.speed);
  if (wf.u >= wf.model.playback) { wf.playing = false; syncTransport(); }
  wfRender();
  wf.raf = wf.playing ? requestAnimationFrame(wfTick) : null;
}
function wfPlay(on) {
  wf.playing = on;
  if (on && wf.u >= wf.model.playback) wf.u = 0;
  wf.last = 0;
  if (on && !wf.raf) wf.raf = requestAnimationFrame(wfTick);
  syncTransport();
}
function syncTransport() {
  const b = $(".wf-play");
  if (b) { b.textContent = wf.playing ? "❚❚" : "▶"; b.title = wf.playing ? "pause" : "play"; }
  document.querySelectorAll(".wf-speed").forEach((s) =>
    s.classList.toggle("on", Number(s.dataset.speed) === wf.speed));
  const f = $(".wf-follow");
  if (f) f.classList.toggle("on", wf.follow);
}

async function renderWorkflow(runId) {
  main.innerHTML = "";
  closeWorkflow();
  // Runs are scoped to the active analysis (scopeURL): the investigation picker below must offer
  // this corpus's investigations only, never another analysis's.
  const runs = await getJSON("/api/runs").catch(() => []);
  const picked = runId || (runs.find((r) => r.active) || runs[0] || {}).run_id || null;
  wf.runId = picked;
  if (!picked) {
    // No runs yet is the NORMAL state for a freshly built corpus, so say what to do rather than
    // reporting an absence. The knowledge-graph half of this view still has something to show.
    if (typeof workflowNoRuns === "function") return workflowNoRuns(main);
    main.appendChild(el("div", { class: "empty" }, "No runs on disk yet."));
    return;
  }

  let model, arch;
  try {
    [model, arch, wf.tree] = await Promise.all([
      getJSON(`/api/events/${encodeURIComponent(picked)}`),
      getJSON("/api/architecture"),
      // Per-experiment outcomes: the live tree draws each experiment as its own node rather than a
      // count ticking up inside a branch.
      getJSON(`/api/tree/${encodeURIComponent(picked)}`).catch(() => null),
    ]);
  } catch (e) {
    // A run that has been launched but has not written its first step yet 404s. Wait for it.
    main.appendChild(el("div", { class: "empty" }, [
      el("h3", {}, `Waiting for ${picked} to write its first step…`),
      el("p", { class: "dim" }, String(e.message || e)),
    ]));
    wf.retry = setTimeout(() => { if (state.view === "workflow") renderWorkflow(runId); }, 3000);
    return;
  }
  wf.model = model; wf.arch = arch; wf.boxes = {}; wf.tokens = {};
  wf.u = model.active ? model.playback : 0;
  wf.follow = !!model.active;

  const strip = el("canvas", { class: "wf-strip" });
  wf.strip = strip; wf.sctx = strip.getContext("2d");
  const tip = el("div", { class: "wf-tip" });
  const scrubTo = (clientX) => {
    const r = strip.getBoundingClientRect();
    const f = (clientX - r.left - 4) / Math.max(1, r.width - 8);
    wf.follow = false; wf.u = Math.max(0, Math.min(1, f)) * wf.model.playback;
    syncTransport(); wfRender();
  };
  let dragging = false;
  strip.addEventListener("mousedown", (e) => { dragging = true; scrubTo(e.clientX); });
  window.addEventListener("mouseup", () => { dragging = false; });
  strip.addEventListener("mousemove", (e) => {
    if (dragging) { scrubTo(e.clientX); return; }
    const r = strip.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    let best = null, bd = 9e9;
    for (const h of wf.hits || []) {
      const d = Math.abs(h.x - mx) + Math.abs(h.y - my) * 2;
      if (d < bd) { bd = d; best = h; }
    }
    if (best && bd < 18) {
      tip.textContent = `${best.e.run_id} · ${best.label}`
        + (best.e.subject ? ` · ${best.e.subject}` : "")
        + (best.e.verdict ? ` · ${best.e.verdict}` : "");
      tip.style.left = Math.min(mx + 12, r.width - 300) + "px";
      tip.classList.add("on");
    } else tip.classList.remove("on");
  });
  strip.addEventListener("mouseleave", () => tip.classList.remove("on"));

  const transport = el("div", { class: "wf-transport" }, [
    el("button", { class: "wf-play", onclick: () => wfPlay(!wf.playing) }, "▶"),
    el("button", { class: "wf-btn", title: "back to start",
                   onclick: () => { wf.u = 0; wf.follow = false; wfRender(); } }, "|<"),
    el("div", { class: "wf-speeds" }, SPEEDS.map((s) =>
      el("button", { class: "wf-speed", "data-speed": s,
                     onclick: () => { wf.speed = s; syncTransport(); } }, `${s}×`))),
    el("span", { class: "wf-clock" }, "—"),
    model.active ? el("button", { class: "wf-follow on", onclick: () => {
      wf.follow = !wf.follow; if (wf.follow) wf.u = wf.model.playback; syncTransport(); wfRender();
    } }, "follow live") : null,
  ]);

  const notes = [];
  if (model.clock_fixed_runs.length) notes.push(`${model.clock_fixed_runs.length} branch(es) shifted to `
    + "start at their fork — their clocks were shifted to align");

  main.appendChild(el("div", { class: "wf-wrap" }, [
    el("div", { class: "wf-head" }, [
      el("h2", {}, "Engine workflow"),
      runPicker(runs, picked),
    ]),
    transport,
    el("div", { class: "wf-strip-wrap" }, [strip, tip]),
    el("div", { class: "wf-strip-key" }, Object.entries(MILESTONE).map(([k, m]) =>
      el("span", { class: "wf-key" }, [el("i", { class: `wf-mark m-${m.mark} e-${k}` }), m.label]))),
    flowchartEl(arch),
    el("div", { class: "wf-now" }, [
      el("div", { class: "wf-now-head" }, [
        el("span", { class: "wf-now-run" }, "—"),
        el("span", { class: "wf-now-action", "data-family": "note" }, ""),
      ]),
      el("div", { class: "wf-now-text" }, ""),
    ]),
    notes.length ? el("ul", { class: "wf-notes" }, notes.map((n) => el("li", {}, n))) : null,
  ]));

  // The knowledge-graph lane is not driven by the run event stream; it is driven by the corpus this
  // analysis built. paintKGLane (projects.js) fills those boxes with real counts, and keeps them live
  // while a build is running.
  if (typeof paintKGLane === "function") paintKGLane();

  const redraw = () => { drawFlowEdges($(".fc")); wfRender(); };
  requestAnimationFrame(redraw);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => requestAnimationFrame(redraw));
  setTimeout(redraw, 350);
  wf.onResize = redraw;
  window.addEventListener("resize", wf.onResize);

  syncTransport();
  if (model.active) startLivePoll(picked); else wfPlay(true);
}

function openNodeDetail(n) {
  const existing = $(".wf-detail");
  if (existing) existing.remove();
  const panel = el("aside", { class: "wf-detail" }, [
    el("button", { class: "wf-detail-x", onclick: () => panel.remove() }, "×"),
    el("h3", {}, n.label),
    el("code", { class: "wf-detail-src" }, n.source),
    el("ul", { class: "wf-detail-list" }, n.detail.map((d) => el("li", {}, d))),
  ]);
  $(".wf-wrap").appendChild(panel);
}

function runPicker(runs, picked) {
  const sel = el("select", { class: "wf-run-select",
    onchange: (e) => { location.hash = `workflow/${e.target.value}`; } });
  for (const r of runs) {
    const o = el("option", { value: r.run_id },
      `${r.run_id}  ·  ${r.steps} steps${r.active ? "  · LIVE" : ""}`);
    if (r.run_id === picked) o.setAttribute("selected", "selected");
    sel.appendChild(o);
  }
  return el("div", { class: "wf-picker" }, [el("label", {}, "Investigation"), sel]);
}

function startLivePoll(runId) {
  // Poll until it has been both inactive and unchanged for a long while.
  let quiet = 0, ticks = 0;
  // The engine tree draws its experiment squares from /api/tree, so refresh that too, at a slower cadence
  // than the events: /api/tree opens the run's database, which a live run holds write-locked.
  const TREE_EVERY = 5;                       // ~15s, against the 3s event poll
  const tick = async () => {
    let m;
    try { m = await getJSON(`/api/events/${encodeURIComponent(runId)}`); } catch { m = null; }
    if (m) {
      const grew = m.events.length > (wf.model ? wf.model.events.length : 0);
      wf.model = m;
      // Latch the staleness: growth is a single edge and must not have to coincide with the slow tick.
      if (grew) wf.treeStale = true;
      if (wf.treeStale && ticks % TREE_EVERY === 0) {
        // Keep the previous tree on failure: a stale square is better than a square that vanishes.
        const t = await getJSON(`/api/tree/${encodeURIComponent(runId)}`).catch(() => null);
        if (t) { wf.tree = t; wf.treeStale = false; }
      }
      ticks += 1;
      if (wf.follow) wf.u = m.playback;
      if (grew || wf.follow) wfRender();
      quiet = (grew || m.active) ? 0 : quiet + 1;
      const badge = $(".wf-follow");
      if (badge) badge.classList.toggle("waiting", !m.active && wf.follow);
      if (quiet > 60) { wf.poll = null; return; }
    }
    wf.poll = setTimeout(tick, 3000);
  };
  wf.poll = setTimeout(tick, 3000);
}

function closeWorkflow() {
  if (wf.retry) { clearTimeout(wf.retry); wf.retry = null; }
  if (wf.raf) { cancelAnimationFrame(wf.raf); wf.raf = null; }
  if (wf.poll) { clearTimeout(wf.poll); wf.poll = null; }
  if (wf.onResize) { window.removeEventListener("resize", wf.onResize); wf.onResize = null; }
  wf.playing = false; wf.model = null; wf.strip = null; wf.sctx = null;
  wf.boxes = {}; wf.tokens = {};
}

// ============================================================================
// Search tree: the investigation as experiments, not as stages
//
// Two branchings, both real and both drawn: a FAN is one `run_experiments` step opening N sibling
// experiments; a FORK is one agent opening N child agents. Everything else is a property of a card.
// ============================================================================
const STAGE_LABEL = { open: "logged", promising: "has result", submitted: "submitted",
                      verifying: "verifying", candidate: "CANDIDATE", killed: "killed",
                      reviewed: "reviewed" };
const tstate = { data: null, collapsed: {} };

const fmtNum = (x, d = 3) =>
  (x === null || x === undefined || Number.isNaN(x)) ? "—"
    : (Math.abs(x) >= 1e4 || (Math.abs(x) > 0 && Math.abs(x) < 1e-3) ? Number(x).toExponential(1)
                                                                     : String(round(Number(x), d)));
const round = (x, d) => Math.round(x * 10 ** d) / 10 ** d;

async function renderTree(runId) {
  main.innerHTML = "";
  const wrap = el("div", { class: "tree-wrap" }, [el("div", { class: "loading" }, "Loading…")]);
  main.appendChild(wrap);

  let trees;
  try { trees = await getJSON("/api/investigations"); }
  catch (e) { wrap.innerHTML = ""; wrap.appendChild(el("div", { class: "empty" }, e.message)); return; }
  if (!trees.length) { wrap.innerHTML = ""; wrap.appendChild(el("div", { class: "empty" }, "No runs yet")); return; }
  const roots = trees.map((t) => (t.root_run || t.runs[0]).run_id);
  const active = runId && roots.includes(runId) ? runId : roots[0];

  let d;
  try { d = await getJSON(`/api/tree/${encodeURIComponent(active)}`); }
  catch (e) { wrap.innerHTML = ""; wrap.appendChild(el("div", { class: "empty" }, e.message)); return; }
  tstate.data = d;
  wrap.innerHTML = "";
  wrap.append(treeHeader(d, roots, active), treeBody(d));
}

function treeHeader(d, roots, active) {
  const c = d.counts;
  const pick = el("select", { class: "tree-pick" },
    roots.map((r) => el("option", { value: r, ...(r === active ? { selected: "" } : {}) }, r)));
  pick.addEventListener("change", () => { location.hash = `#tree/${pick.value}`; });

  // The funnel is the story: many experiments, few submissions, fewer survivors.
  const stat = (n, label, cls = "") => el("div", { class: `tstat ${cls}` },
    [el("b", {}, String(n)), el("span", {}, label)]);
  // DEPTH is the stat that says whether this is a tree or a flat beam: depth 1 means every branch came
  // from the root, so N forks are N rounds of the same one split. Only depth >= 2 is recursion.
  const maxDepth = Math.max(0, ...d.lanes.map((l) => l.depth));
  const splits = splitPoints(d);
  const bar = el("div", { class: "tree-stats" }, [
    stat(d.lanes.length, "agents"), stat(maxDepth, "depth", maxDepth >= 2 ? "ok" : ""),
    stat(splits.size, "forks"), stat(c.experiments, "experiments"),
    stat(c.failed, "failed", c.failed ? "warn" : ""), stat(c.submitted, "submitted"),
    stat(c.candidates, "candidates", "ok"), stat(c.killed, "killed", "bad"),
  ]);

  // Say which shape the search took, in both directions. Kept out of `notes`, which is for problems.
  let shape = null;
  if (splits.size) {
    shape = maxDepth >= 2
      ? { ok: true, text: `recursed to depth ${maxDepth} · ${splits.size} agents forked` }
      : { ok: false, text: `depth 1 · every branch came from the root — ${splits.size} round(s) of `
                           + `beam search, not a recursive tree` };
  }

  const notes = [];
  // "0 experiments" is a claim about the run; it must not be what an unreadable database looks like.
  if (d.db_unreadable)
    notes.push(`could not open this run's database (${d.db_unreadable}) — experiment counts below are `
               + "not the run's, they are what could be read");
  if (d.unverified_submissions.length)
    notes.push(`${d.unverified_submissions.length} submission(s) still unverified`);
  if (d.orphans.length) notes.push(`${d.orphans.length} broken link(s)`);
  // Collapsing every agent is what makes the shape legible; expanded is the default.
  const fold = el("button", { class: "tree-fold" }, "Collapse all");
  fold.addEventListener("click", () => {
    const collapse = fold.textContent === "Collapse all";
    document.querySelectorAll(".agent").forEach((a) => a.classList.toggle("collapsed", collapse));
    tstate.data.lanes.forEach((l) => { tstate.collapsed[l.run_id] = collapse; });
    fold.textContent = collapse ? "Expand all" : "Collapse all";
  });
  const head = el("div", { class: "tree-head" }, [
    el("div", { class: "tree-head-row" }, [el("h2", {}, "Search tree"), pick, fold]),
    bar,
  ]);
  if (shape) head.appendChild(el("div", { class: `tree-shape${shape.ok ? " ok" : ""}` }, shape.text));
  // Broken links are shown, never dropped.
  if (notes.length) head.appendChild(el("div", { class: "tree-warn" }, notes.join(" · ")));
  return head;
}

// Branches no fork record names, grouped under the parent their run_id points at. A running fork has
// written no record yet, so every live branch lands here; the path-encoded id gives the exact parent.
function unrecordedChildren(d) {
  const named = new Set(d.forks.flatMap((f) => f.children.map((c) => c.run_id)));
  const out = {};
  d.lanes.filter((l) => l.parent && !named.has(l.run_id))
    .forEach((l) => { (out[l.parent] ||= []).push(l.run_id); });
  Object.values(out).forEach((v) => v.sort());
  return out;
}

// Where the search actually split: recorded forks plus running ones, which have no record yet.
function splitPoints(d) {
  return new Set([...d.forks.map((f) => f.parent), ...Object.keys(unrecordedChildren(d))]);
}

function treeBody(d) {
  const byRun = {};
  d.nodes.forEach((n) => { (byRun[n.run_id] ||= []).push(n); });
  const forkOf = {};
  d.forks.forEach((f) => f.children.forEach((c) => { forkOf[c.run_id] = { ...c, parent: f.parent }; }));
  const unrecorded = unrecordedChildren(d);
  // Forks by parent, in the order they happened.
  const forksOf = {};
  d.forks.forEach((f) => { (forksOf[f.parent] ||= []).push(f); });
  Object.values(forksOf).forEach((l) => l.sort((a, b) => (a.step ?? 0) - (b.step ?? 0)));

  // Which lanes the walk can reach: a branch is drawn under the fork record that names it, and a lane
  // no record names (a lost parent trace, a run killed mid-fork) is drawn on the UNLINKED rail below.
  const drawn = new Set();
  const walk = (runId, depth) => {
    drawn.add(runId);
    const node = el("div", { class: "tnode" },
      [agentBlock(runId, depth, byRun[runId] || [], forkOf[runId], d)]);
    (forksOf[runId] || []).forEach((f, i) => {
      // the fork EVENT is its own node — where the search actually split
      const kids = el("div", { class: "children" });
      const ranked = [...f.children].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));
      ranked.forEach((c) => kids.appendChild(walk(c.run_id, depth + 1)));
      node.append(forkHeader(f, (forksOf[runId] || []).length > 1 ? i + 1 : 0, ranked), kids);
    });
    // ...and the children whose record has not been written yet, captioned: no rank, angle or judge
    // reason yet.
    const pending = (unrecorded[runId] || []).filter((r) => !drawn.has(r));
    if (pending.length) {
      const kids = el("div", { class: "children" });
      pending.forEach((r) => kids.appendChild(walk(r, depth + 1)));
      node.append(el("div", { class: "fork-head unrecorded" }, [
        el("span", { class: "fork-n" }, "no record yet"),
        el("span", { class: "muted" }, `${pending.length} branch(es) placed by run_id; a fork record is `
                   + "written only when the fork completes, so a running fork has none"),
      ]), kids);
    }
    return node;
  };
  const body = el("div", { class: "tree-body" }, [walk(d.root, 0)]);

  const stranded = d.lanes.filter((l) => !drawn.has(l.run_id));
  if (stranded.length) {
    body.appendChild(el("div", { class: "fork-head stranded" }, [
      el("span", { class: "fork-n" }, "UNLINKED"),
      el("span", { class: "muted" },
        `${stranded.length} branch(es) with a trace but no fork record — position in the tree unknown`),
    ]));
    const kids = el("div", { class: "children" });
    stranded.sort((a, b) => a.depth - b.depth || a.run_id.localeCompare(b.run_id))
      .forEach((l) => kids.appendChild(
        el("div", { class: "tnode" }, [agentBlock(l.run_id, l.depth, byRun[l.run_id] || [], null, d)])));
    body.appendChild(kids);
  }
  return body;
}

// `n` is the split index, or 0 when this node split exactly once (a node splits once; survivors carry
// their lines forward). Only a node with several splits gets them numbered.
function forkHeader(f, n, ranked) {
  const kept = ranked.filter((c) => c.kept).length;
  const bits = [
    // No "FORK" caption: the spine and indent already say a split happened.
    ...(n ? [el("span", { class: "fork-n" }, `SPLIT ${n}`)] : []),
    el("span", { class: "muted" }, `step ${f.step ?? "?"} · ${ranked.length} branches · judge kept ${kept}`),
  ];
  if (f.budget_remaining !== null && f.budget_remaining !== undefined)
    bits.push(el("span", { class: `tag ${f.budget_remaining ? "" : "pruned"}` },
      `budget ${f.budget_remaining} left`));
  return el("div", { class: "fork-head" }, bits);
}

function agentBlock(runId, depth, nodes, meta, d) {
  const lane = d.lanes.find((l) => l.run_id === runId) || {};
  const isAdv = meta && meta.adversarial;
  const block = el("div", { class: `agent${isAdv ? " adversarial" : ""}` });

  // --- the agent's own header: who it is, what angle it was given, how the judge ranked it -------------
  const tags = [];
  if (isAdv) tags.push(el("span", { class: "tag adv" }, "ADVERSARY"));
  if (meta && meta.rank) tags.push(el("span", { class: `tag ${meta.kept ? "kept" : "pruned"}` },
    `rank ${meta.rank} · ${meta.kept ? "deepened" : "pruned"}`));
  const head = el("div", { class: "agent-head" }, [
    el("code", { class: "rid" }, runId),
    el("span", { class: "muted" }, `depth ${depth} · ${lane.n_experiments || 0} experiments`),
    ...tags,
  ]);
  head.addEventListener("click", () => {
    tstate.collapsed[runId] = !tstate.collapsed[runId];
    block.classList.toggle("collapsed", tstate.collapsed[runId]);
  });
  block.appendChild(head);
  if (meta && meta.angle) block.appendChild(el("div", { class: "angle" }, meta.angle));
  // The judge's REASON is the only cross-branch reasoning the engine produces — show it verbatim.
  if (meta && meta.reason) block.appendChild(el("div", { class: "judge" },
    [el("b", {}, "judge: "), meta.reason]));

  // --- the cards, grouped by the step that fanned them -------------------------------------------------
  const exps = nodes.filter((n) => n.kind === "experiment");
  const groups = new Map();
  exps.forEach((n) => {
    // (session, step), not step alone.
    const key = `${n.session ?? "?"}:${n.step ?? "?"}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(n);
  });
  const cards = el("div", { class: "cards" });
  [...groups.entries()].forEach(([key, list]) => {
    const [, step] = key.split(":");
    const fan = el("div", { class: `fan${list.length > 1 ? " multi" : ""}` });
    fan.appendChild(el("div", { class: "fan-label" },
      step === "?" ? "no recorded step" : `step ${step}${list.length > 1 ? ` — fan of ${list.length}` : ""}`));
    list.forEach((n) => fan.appendChild(expCard(n)));
    cards.appendChild(fan);
  });
  if (!exps.length) cards.appendChild(el("div", { class: "empty small" },
    nodes.length ? "no experiments — notes only" : "dead branch: produced nothing"));
  block.appendChild(cards);
  if (tstate.collapsed[runId]) block.classList.add("collapsed");
  return block;
}

function expCard(n) {
  const cls = `card st-${n.stage}${n.failed ? " failed" : ""}`;
  const card = el("div", { class: cls });
  const ids = [`entry #${n.entry_id}`];
  if (n.submission_id) ids.push(`sub #${n.submission_id}`);
  if (n.test_id) ids.push(`test #${n.test_id}`);
  card.appendChild(el("div", { class: "card-top" }, [
    el("span", { class: `stage ${n.stage}` }, STAGE_LABEL[n.stage] || n.stage),
    n.attempt > 1 ? el("span", { class: "tag retry" }, `attempt ${n.attempt}`) : null,
    // Provenance, copyable: every id here is greppable in the trace or the DB.
    el("code", { class: "prov", title: "click to copy" }, ids.join(" · ")),
  ].filter(Boolean)));
  card.querySelector(".prov").addEventListener("click", (e) => {
    e.stopPropagation();
    navigator.clipboard?.writeText(ids.join(" ")).catch(() => {});
  });
  card.appendChild(el("div", { class: "card-title" }, n.title || "(untitled)"));
  if (n.subject || n.object)
    card.appendChild(el("div", { class: "pair" }, `${n.subject || "?"} ~ ${n.object || "?"}`));

  if (n.failed) {
    // "no RESULT" and "the code raised" are different events; most RESULT-less experiments are probes.
    card.appendChild(el("div", { class: "nums fail" },
      n.raised ? "no result — the code raised" : "ran, but reported no RESULT (probe or diagnostic)"));
  } else if (n.p_null !== null && n.p_null !== undefined) {
    // A p outside [0,1] is a malformed contract, not a weak result. Say so rather than print it as a p.
    const badP = !(n.p_null >= 0 && n.p_null <= 1);
    card.appendChild(el("div", { class: "nums" }, [
      el("span", {}, `effect ${fmtNum(n.effect)}`),
      el("span", { class: badP ? "bad" : "" },
         badP ? `p ${fmtNum(n.p_null)} — not a probability` : `p ${fmtNum(n.p_null)}`),
      n.n_units ? el("span", { class: "muted" }, `n=${n.n_units}`) : null,
      n.robust === false ? el("span", { class: "warn" }, "not robust") : null,
    ].filter(Boolean)));
    // effect present but unrenderable = it was NaN on disk and the server mapped it to null (valid JSON).
    if (n.effect === null && n.p_null !== null)
      card.appendChild(el("div", { class: "vnote" }, "effect was not a finite number when recorded"));
  }
  if (n.kill_reason) card.appendChild(el("div", { class: "kill" }, `killed: ${n.kill_reason}`));
  if (n.verdict_note) card.appendChild(el("div", { class: "vnote" }, n.verdict_note));
  return card;
}

// Boot. Must be last: every view's module-level bindings are initialized by the time this runs.
// Deferred one tick past DOMContentLoaded so projects.js (loaded after this file) has registered its
// views and resolved the active project first; routing before that renders a view scoped to nothing.
window.addEventListener("DOMContentLoaded", () => {
  const ready = typeof bootProjects === "function" ? bootProjects() : Promise.resolve();
  ready.then(route, route);
});
