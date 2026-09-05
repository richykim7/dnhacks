/* ============================================================================
   Projects — the analysis profile, its onboarding, and its corpus page.

   Loaded after app.js and sharing its script scope (classic scripts, one global
   lexical environment), so `el`, `getJSON`, `state` and friends are the same
   functions the rest of the console uses. Views register into EXTRA_VIEWS; the
   router in app.js stays the only router.

   Three views live here:
     #projects   every analysis, and the door to a new one
     #new        the onboarding flow: describe -> refine with the assistant ->
                 attach documents -> review -> build
     #corpus     the active analysis: its spec, documents, builds and graph
   ========================================================================== */
"use strict";

const PROJ_KEY = "dnhacksbio-project";
// Sentinel for "show everything, scope nothing" — a remembered choice, not the absence of one.
const ALL = "__all__";

/* ---------------------------------------------------------------- utilities */

const pnum = (x) => (x == null ? "—" : Number(x).toLocaleString());

function field(label, control, hint) {
  return el("label", { class: "pf" }, [
    el("span", { class: "pf-label" }, label),
    control,
    hint ? el("span", { class: "pf-hint" }, hint) : null,
  ].filter(Boolean));
}

function button(text, kind, onclick, opts = {}) {
  const b = el("button", { class: `pbtn ${kind || ""}`.trim(), type: "button", ...opts }, text);
  b.addEventListener("click", onclick);
  return b;
}

function notice(text, kind = "info") {
  return el("div", { class: `pnotice ${kind}` }, text);
}

/** Run an async action from a button: disable it, show what went wrong in place, always re-enable. */
async function guard(btn, host, fn) {
  const was = btn.textContent;
  btn.disabled = true;
  btn.textContent = "…";
  const old = host && host.querySelector(".pnotice.error");
  if (old) old.remove();
  try {
    return await fn();
  } catch (e) {
    if (host) host.prepend(notice(e.message || String(e), "error"));
    return null;
  } finally {
    btn.disabled = false;
    btn.textContent = was;
  }
}

/* ------------------------------------------------------------ boot + switcher */

/** Resolve the active project before the first route. Called by app.js's boot. */
async function bootProjects() {
  await refreshProjects();
  let want = new URLSearchParams(location.search).get("project");
  if (!want) { try { want = localStorage.getItem(PROJ_KEY); } catch { want = null; } }
  // "unscoped" is a CHOICE, so it has to be remembered like any other. Without a sentinel, picking
  // Everything and reloading would silently snap you back into the first analysis.
  if (want === ALL) return setProject(null, { silent: true });
  const known = state.projects.some((p) => p.id === want);
  setProject(known ? want : (state.projects[0] ? state.projects[0].id : null), { silent: true });
}

async function refreshProjects() {
  state.projectsError = null;
  try {
    const r = await fetch("/api/projects");
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
    state.projects = (await r.json()).projects || [];
  } catch (e) {
    state.projects = [];
    state.projectsError = e.message === "Failed to fetch" ? "stale" : e.message;
  }
  renderSwitcher();
  return state.projects;
}

function activeProject() {
  return state.projects.find((p) => p.id === state.project) || null;
}

function setProject(pid, opts = {}) {
  state.project = pid || null;
  try { localStorage.setItem(PROJ_KEY, pid || ALL); } catch {}
  renderSwitcher();
  if (!opts.silent) {
    // Switching analysis invalidates everything on screen — the runs, the graph, the review queue
    // all belong to the old corpus. Re-route rather than patch, so no stale panel can survive.
    state.runId = null;
    route();
  }
}

function renderSwitcher() {
  const host = document.getElementById("project-switcher");
  if (!host) return;
  host.innerHTML = "";

  // A server too old for the projects API cannot be recovered from in the browser; say what to do.
  if (state.projectsError === "stale") {
    host.appendChild(el("div", { class: "ps-stale" }, [
      el("b", {}, "Server needs a restart"),
      el("span", {}, "The server process is not serving the projects routes, so analyses and the "
                     + "knowledge-graph lane cannot load. Restart it:"),
      el("code", {}, "uv run python scripts/serve_ui.py"),
    ]));
    return;
  }
  if (state.projectsError) {
    host.appendChild(el("div", { class: "ps-stale" }, [
      el("b", {}, "Could not load analyses"),
      el("span", {}, state.projectsError),
    ]));
    return;
  }

  const cur = activeProject();
  const btn = el("button", { class: "ps-button", type: "button", id: "ps-button",
                             "aria-haspopup": "listbox", "aria-expanded": "false" }, [
    el("span", { class: "ps-dot" + (cur && cur.status === "building" ? " building" : "") }),
    el("span", { class: "ps-name" }, cur ? cur.name : "Everything"),
    el("span", { class: "ps-caret" }, "▾"),
  ]);
  const menu = el("div", { class: "ps-menu", role: "listbox" });

  // The escape hatch: scoping every view to one analysis hides runs whose corpus cannot be identified.
  const allRow = el("div", { class: "ps-item ps-action" + (state.project ? "" : " active"),
                             role: "option", tabindex: "0" }, [
    el("span", { class: "ps-dot" }),
    el("span", { class: "ps-item-name" }, "Everything"),
    el("span", { class: "ps-item-meta" }, "no scoping"),
  ]);
  const goAll = () => { close(); setProject(null); };
  allRow.addEventListener("click", goAll);
  allRow.addEventListener("keydown", (e) => { if (e.key === "Enter") goAll(); });
  menu.append(allRow, el("div", { class: "ps-sep" }));

  for (const p of state.projects) {
    const row = el("div", { class: "ps-item" + (p.id === state.project ? " active" : ""),
                            role: "option", tabindex: "0" }, [
      el("span", { class: "ps-dot" + (p.status === "building" ? " building" : "") }),
      el("span", { class: "ps-item-name" }, p.name),
      el("span", { class: "ps-item-meta" },
         p.adopted ? "existing corpus" : (p.n_claims ? `${pnum(p.n_claims)} claims` : p.status)),
    ]);
    const pick = () => { close(); setProject(p.id); };
    row.addEventListener("click", pick);
    row.addEventListener("keydown", (e) => { if (e.key === "Enter") pick(); });
    menu.appendChild(row);
  }
  if (!state.projects.length)
    menu.appendChild(el("div", { class: "ps-empty" }, "No analyses yet"));

  menu.appendChild(el("div", { class: "ps-sep" }));
  const mk = (label, hash) => {
    const it = el("div", { class: "ps-item ps-action", role: "option", tabindex: "0" }, label);
    const go = () => { close(); location.hash = hash; };
    it.addEventListener("click", go);
    it.addEventListener("keydown", (e) => { if (e.key === "Enter") go(); });
    return it;
  };
  menu.appendChild(mk("+  New analysis", "new"));
  menu.appendChild(mk("Manage analyses…", "projects"));

  function close() { host.classList.remove("open"); btn.setAttribute("aria-expanded", "false"); }
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    host.classList.toggle("open");
    btn.setAttribute("aria-expanded", host.classList.contains("open") ? "true" : "false");
  });
  // Click-outside-to-close is bound to the DOCUMENT, which outlives this render. Registering it
  // per render would stack one dead listener per re-render — and the switcher re-renders on every
  // project refresh — so it is bound once and reads the switcher's live class instead.
  if (!renderSwitcher._bound) {
    document.addEventListener("click", () => {
      const h = document.getElementById("project-switcher");
      if (!h) return;
      h.classList.remove("open");
      const b = h.querySelector(".ps-button");
      if (b) b.setAttribute("aria-expanded", "false");
    });
    renderSwitcher._bound = true;
  }

  host.append(btn, menu);
}

/* --------------------------------------------------------- teardown between views */

let projStreams = [];
function closeProjectViews() {
  for (const s of projStreams) { try { s.close(); } catch {} }
  projStreams = [];
}

/* ============================================================================
   #projects — every analysis
   ========================================================================== */

EXTRA_VIEWS.projects = async function renderProjects() {
  main.innerHTML = "";
  const head = el("div", { class: "page-head" }, [
    el("h1", {}, "Analyses"),
    el("span", { class: "grow" }),
    button("+ New analysis", "primary", () => { location.hash = "new"; }),
  ]);
  main.appendChild(head);
  const body = el("div", { class: "pscroll" });
  main.appendChild(body);

  await refreshProjects();
  if (!state.projects.length) {
    body.appendChild(el("div", { class: "empty" }, "No analyses yet — create one to get started."));
    return;
  }
  const grid = el("div", { class: "pcards" });
  for (const p of state.projects) {
    const card = el("div", { class: "pcard" + (p.id === state.project ? " current" : "") }, [
      el("div", { class: "pcard-top" }, [
        el("div", { class: "pcard-name" }, p.name),
        el("span", { class: `pstatus ${p.status}` }, p.adopted ? "existing" : p.status),
      ]),
      el("div", { class: "pcard-meta" }, [
        el("span", {}, p.has_kg ? `${pnum(p.n_claims || 0)} claims` : "no graph yet"),
        el("span", {}, p.n_attachments ? `${p.n_attachments} document(s)` : ""),
        el("span", {}, p.updated ? agoTime(p.updated) : ""),
      ].filter((n) => n.textContent)),
      el("div", { class: "pcard-actions" }, [
        button(p.id === state.project ? "Current" : "Open", "", () => {
          setProject(p.id);
          location.hash = "corpus";
        }, p.id === state.project ? { disabled: "disabled" } : {}),
        button("Corpus", "ghost", () => { setProject(p.id, { silent: true }); location.hash = "corpus"; }),
      ]),
    ]);
    grid.appendChild(card);
  }
  body.appendChild(grid);
};

/* ============================================================================
   #new — the onboarding flow
   ========================================================================== */

// Uploading documents is part of Refine, not its own step.
const STEPS = [
  { id: "describe", label: "Describe" },
  { id: "refine", label: "Refine" },
  { id: "review", label: "Review" },
  { id: "build", label: "Build" },
];

const wiz = { pid: null, step: 0, rec: null };

EXTRA_VIEWS.new = async function renderNew(arg) {
  closeProjectViews();
  main.innerHTML = "";
  if (arg && arg !== wiz.pid) { wiz.pid = arg; wiz.step = 1; }
  if (!arg) { wiz.pid = null; wiz.step = 0; wiz.rec = null; }
  await drawWizard();
};

async function drawWizard() {
  main.innerHTML = "";
  main.appendChild(el("div", { class: "page-head" }, [
    el("h1", {}, "New analysis"),
    el("span", { class: "grow" }),
    wiz.pid ? el("span", { class: "page-sub" }, wiz.rec ? wiz.rec.name : wiz.pid) : null,
  ].filter(Boolean)));

  const stepper = el("div", { class: "stepper" }, STEPS.map((s, i) =>
    el("div", { class: "stp" + (i === wiz.step ? " on" : (i < wiz.step ? " done" : "")) }, [
      el("span", { class: "stp-n" }, i < wiz.step ? "✓" : String(i + 1)),
      el("span", {}, s.label),
    ])));
  main.appendChild(stepper);

  const body = el("div", { class: "pscroll" });
  main.appendChild(body);

  if (wiz.pid && !wiz.rec) {
    try { wiz.rec = await getJSON(`/api/projects/${encodeURIComponent(wiz.pid)}`); }
    catch (e) { body.appendChild(notice(e.message, "error")); return; }
  }

  const step = STEPS[wiz.step].id;
  if (step === "describe") return stepDescribe(body);
  if (step === "refine") return stepRefine(body);
  if (step === "review") return stepReview(body);
  if (step === "build") return stepBuild(body);
}

function wizNav(body, { back, next, nextLabel, nextKind }) {
  const bar = el("div", { class: "wiz-nav" }, [
    back ? button("← Back", "ghost", back) : el("span", {}),
    el("span", { class: "grow" }),
    next ? button(nextLabel || "Continue →", nextKind || "primary",
                  (e) => guard(e.target, body, next)) : null,
  ].filter(Boolean));
  body.appendChild(bar);
}

/* ---- step 1: describe ---------------------------------------------------- */

function stepDescribe(body) {
  const wrap = el("div", { class: "pcol" });
  wrap.appendChild(el("p", { class: "plead" },
    "An analysis is a self-contained profile: its own literature corpus, its own uploaded documents, "
    + "its own engine runs and its own review queue. Nothing here touches your other analyses."));

  const nameIn = el("input", { class: "pinput", type: "text", placeholder: "Gene A × gene B regulation",
                               maxlength: "120" });
  const descIn = el("textarea", { class: "ptext", rows: "6", placeholder:
    "What literature should this corpus contain? Name the entities, the mechanisms, and the tissue "
    + "or disease context.\n\nExample: two transcription factors in a named cell type, the "
    + "degradation machinery that sets their protein turnover, and a candidate upstream regulator." });

  wrap.appendChild(field("Name", nameIn));
  wrap.appendChild(field("What should this corpus cover?", descIn,
    "The assistant turns this into literature queries. Be specific: the more mechanism you name, "
    + "the sharper the corpus. If you have a question in mind, say it — it helps choose the "
    + "queries — but you will ask it when you start a run, not here."));
  body.appendChild(wrap);

  const create = async (withAssistant) => {
    if (!nameIn.value.trim()) throw new Error("give the analysis a name");
    const rec = await postJSON("/api/projects", { name: nameIn.value.trim(),
                                                  description: descIn.value.trim() });
    wiz.pid = rec.id;
    wiz.rec = rec;
    await refreshProjects();
    setProject(rec.id, { silent: true });
    if (withAssistant && descIn.value.trim().length >= 10) {
      const res = await postJSON("/api/assistant/suggest", { description: descIn.value.trim(),
                                                             name: nameIn.value.trim() });
      await postJSON(`/api/projects/${encodeURIComponent(rec.id)}/chat/apply`, { patch: res.patch });
      wiz.rec = await getJSON(`/api/projects/${encodeURIComponent(rec.id)}`);
      wiz.seed = res.reply;
    }
    wiz.step = 1;
    await drawWizard();
  };

  const bar = el("div", { class: "wiz-nav" }, [
    el("span", { class: "grow" }),
    button("Set it up myself", "ghost", (e) => guard(e.target, body, () => create(false))),
    button("Draft it with the assistant →", "primary", (e) => guard(e.target, body, () => create(true))),
  ]);
  body.appendChild(bar);
  body.appendChild(el("p", { class: "pfine" },
    "The assistant proposes queries; it never applies them without you. Drafting costs one model call "
    + "and no literature is fetched yet."));
  nameIn.focus();
}

/* ---- step 2: refine (assistant + spec) ----------------------------------- */

function stepRefine(body) {
  const grid = el("div", { class: "refine-grid" });
  const chatCol = el("div", { class: "pcol" });
  const specCol = el("div", { class: "pcol" });
  grid.append(chatCol, specCol);
  body.appendChild(grid);

  const drawSpec = () => {
    specCol.innerHTML = "";
    specCol.appendChild(el("h2", { class: "psec" }, "The corpus definition"));
    specCol.appendChild(specEditor(wiz.pid, wiz.rec.spec, refreshWizRec));
    specCol.appendChild(disclosure("Add your own documents", "optional", () => {
      const w = el("div", {});
      w.appendChild(el("p", { class: "pfine" },
        "Anything the literature search cannot reach — a preprint, a thesis chapter, an internal "
        + "report, a paywalled PDF you have. The same extractor reads them, so they arrive in the "
        + "graph with quotes and provenance like any other paper."));
      w.appendChild(attachPanel(wiz.pid, refreshWizRec));
      return w;
    }));
  };

  chatCol.appendChild(el("h2", { class: "psec" }, "Talk it through"));
  chatCol.appendChild(assistantPanel(wiz.pid, () => refreshWizRec().then(drawSpec), wiz.seed));
  wiz.seed = null;
  drawSpec();

  wizNav(body, {
    back: () => { wiz.step = 0; wiz.pid = null; wiz.rec = null; drawWizard(); },
    next: async () => {
      await refreshWizRec();
      if (!(wiz.rec.spec.queries || []).length)
        throw new Error("add at least one literature query before continuing");
      if (!wiz.rec.spec.theme)      // theme is mechanical: it is the text triage ranks against
        throw new Error("add a theme — it is what relevance-ranks every candidate paper");
      wiz.step = 2;
      await drawWizard();
    },
  });
}

async function refreshWizRec() {
  wiz.rec = await getJSON(`/api/projects/${encodeURIComponent(wiz.pid)}`);
  return wiz.rec;
}

/* ---- step 3: review ------------------------------------------------------ */

function stepReview(body) {
  const s = wiz.rec.spec;
  const wrap = el("div", { class: "pcol" });
  wrap.appendChild(el("h2", { class: "psec" }, "What will be built"));
  wrap.appendChild(el("div", { class: "tiles wide" }, [
    tile(s.queries.length, "discovery queries"),
    tile(s.n_papers, "papers (max)"),
    tile((wiz.rec.attachments || []).length, "uploaded documents"),
    tile(s.year_max ? `≤ ${s.year_max}` : "all", "publication years"),
  ]));

  if (s.scope) {
    wrap.appendChild(el("h2", { class: "psec" }, "Scope"));
    wrap.appendChild(el("div", { class: "pquote" }, s.scope));
  }
  wrap.appendChild(el("h2", { class: "psec" }, "Theme (the relevance target)"));
  wrap.appendChild(el("div", { class: "pquote" }, s.theme || "(none set)"));
  wrap.appendChild(el("h2", { class: "psec" }, "Queries"));
  wrap.appendChild(el("div", { class: "qlist" }, s.queries.map((q, i) =>
    el("div", { class: "qrow" }, [el("span", { class: "qn" }, `q${i}`), el("code", {}, q)]))));

  wrap.appendChild(el("p", { class: "pfine" },
    `Building reads up to ${s.n_papers} papers with a model, which costs tokens and takes minutes. `
    + "The selected paper list is written to paper_list.json either way, so you can check what it "
    + "chose. Nothing is asked of the corpus yet — you set the question when you start a run."));
  body.appendChild(wrap);

  const bar = el("div", { class: "wiz-nav" }, [
    button("← Back", "ghost", () => { wiz.step = 1; drawWizard(); }),
    el("span", { class: "grow" }),
    button("Build the corpus", "primary", (e) => guard(e.target, body, startBuild)),
  ]);
  body.appendChild(bar);
}

async function startBuild() {
  const job = await postJSON(`/api/projects/${encodeURIComponent(wiz.pid)}/build`, {});
  wiz.job = job.id;
  wiz.step = 3;
  await refreshProjects();
  await drawWizard();
}

/* ---- step 4: build ------------------------------------------------------- */

function stepBuild(body) {
  const wrap = el("div", { class: "pcol" });
  body.appendChild(wrap);
  wrap.appendChild(jobMonitor(wiz.pid, wiz.job, {
    onFinish: async () => { await refreshProjects(); await refreshWizRec(); },
  }));
  const bar = el("div", { class: "wiz-nav" }, [
    button("Back to the definition", "ghost", () => { wiz.step = 1; drawWizard(); }),
    el("span", { class: "grow" }),
    button("Open the corpus page", "primary", () => {
      setProject(wiz.pid, { silent: true });
      location.hash = "corpus";
    }),
  ]);
  body.appendChild(bar);
}

/* ============================================================================
   #corpus — the active analysis
   ========================================================================== */

/* A collapsed section. Everything that is not "what was built" or "add to it" lives behind one of
   these, because a corpus that already exists should not greet you with the form that made it. */
function disclosure(title, subtitle, fill) {
  const d = el("details", { class: "pdisc" }, [
    el("summary", {}, [
      el("span", { class: "pd-title" }, title),
      subtitle ? el("span", { class: "pd-sub" }, subtitle) : null,
    ].filter(Boolean)),
  ]);
  let filled = false;
  d.addEventListener("toggle", () => {          // build the contents on first open, not on render
    if (!d.open || filled) return;
    filled = true;
    d.appendChild(el("div", { class: "pd-body" }, fill()));
  });
  return d;
}

EXTRA_VIEWS.corpus = async function renderCorpus() {
  closeProjectViews();
  main.innerHTML = "";
  if (!state.project) {
    main.appendChild(el("div", { class: "page-head" }, [el("h1", {}, "Corpus")]));
    main.appendChild(el("div", { class: "empty" }, "No analysis selected."));
    return;
  }
  const pid = state.project;
  let rec, stats, jobList;
  const head = el("div", { class: "page-head" }, [el("h1", {}, "Corpus")]);
  main.appendChild(head);
  const body = el("div", { class: "pscroll" });
  main.appendChild(body);
  body.appendChild(el("div", { class: "loading" }, "Loading…"));

  try {
    [rec, stats, jobList] = await Promise.all([
      getJSON(`/api/projects/${encodeURIComponent(pid)}`),
      getJSON(`/api/projects/${encodeURIComponent(pid)}/kg`),
      getJSON(`/api/projects/${encodeURIComponent(pid)}/jobs`).catch(() => ({ jobs: [] })),
    ]);
  } catch (e) {
    body.innerHTML = "";
    body.appendChild(el("div", { class: "empty" }, e.message));
    return;
  }
  body.innerHTML = "";
  head.appendChild(el("span", { class: "grow" }));
  head.appendChild(el("span", { class: `pstatus ${rec.status}` }, rec.adopted ? "existing" : rec.status));

  const jl = jobList.jobs || [];
  const running = jl.find((j) => j.status === "running");
  const rebuild = async (mode) => {
    await postJSON(`/api/projects/${encodeURIComponent(pid)}/build`, { mode });
    await EXTRA_VIEWS.corpus();
  };

  body.appendChild(el("h2", { class: "ptitle" }, rec.name));
  if (rec.description) body.appendChild(el("p", { class: "plead" }, rec.description));

  // --- what exists, stated as a fact --------------------------------------
  // Read from the BUILD's own manifest, not from the spec. The spec is a plan and it is editable;
  // describing the graph with it would silently re-label an old artifact with a new intention.
  if (stats.exists) {
    const b = rec.built || {};
    const bits = [
      `${pnum(stats.papers.n)} papers`,
      `${pnum(stats.claims.n)} claims`,
      `${pnum(stats.claims.entities)} entities`,
      stats.disputed ? `${pnum(stats.disputed)} disputed` : null,
      b.built ? `built ${agoTime(b.built)}` : null,
      b.queries && b.queries.length ? `from ${b.queries.length} quer${b.queries.length === 1 ? "y" : "ies"}` : null,
      b.n_attachments ? `${b.n_attachments} of your documents` : null,
    ].filter(Boolean);
    body.appendChild(el("div", { class: "corpus-facts" }, bits.join(" · ")));
    if (b.stale) {
      body.appendChild(notice(
        "The saved definition has changed since this corpus was built, so the numbers above describe "
        + "the older definition. Rebuild to apply the change.", "warn"));
    }
  } else {
    body.appendChild(notice("No corpus has been built for this analysis yet.", "info"));
  }

  // --- the two things you actually came to do ------------------------------
  const panelHost = el("div", { class: "panel-host" });
  if (stats.exists) {
    body.appendChild(el("div", { class: "prow" }, [
      button("Open the graph", "", () => { location.hash = "graph"; }),
      button("Start an investigation", "primary", () => { openRunLauncher(pid, rec, panelHost); }),
      button("Past investigations", "ghost", () => { location.hash = "workflow"; }),
    ]));
  }
  body.appendChild(panelHost);

  // --- a live job ----------------------------------------------------------
  if (running) {
    body.appendChild(el("h2", { class: "psec" }, running.kind === "run" ? "Running now" : "Building now"));
    if (running.kind === "run") {
      body.appendChild(runMonitor(pid, running));
    } else {
      body.appendChild(jobMonitor(pid, running.id, { onFinish: () => EXTRA_VIEWS.corpus() }));
    }
  }

  // --- an adopted corpus is read-only; say so once and stop ----------------
  if (rec.adopted) {
    body.appendChild(notice(
      "This corpus was built outside the console, so its definition is not editable here. You can "
      + "browse its graph and run the engine against it.", "info"));
    return;
  }

  // --- add to it -----------------------------------------------------------
  // The one edit that does not invalidate the graph: more material, folded in by an expand. Adding
  // a query and dropping a PDF are the same action here, which is why they share a button.
  if (stats.exists) {
    body.appendChild(el("h2", { class: "psec" }, "Add to this corpus"));
    body.appendChild(el("p", { class: "pfine" },
      "New papers and new documents are folded into the existing graph. Nothing already in it is "
      + "re-read, and nothing is re-paid for."));
    const qIn = el("input", { class: "pinput grow", type: "text",
                              placeholder: "another Europe PMC query — e.g. MYC AND MAX AND stability" });
    const addQ = button("Add the query", "", (e) => guard(e.target, body, async () => {
      const q = qIn.value.trim();
      if (!q) throw new Error("type a query first");
      const cur = rec.spec.queries || [];
      await postJSON(`/api/projects/${encodeURIComponent(pid)}`, { spec: { queries: cur.concat([q]) } });
      qIn.value = "";
    }));
    const addWrap = el("div", { class: "pcol add-row" }, [
      el("div", { class: "prow" }, [qIn, addQ]),
      attachPanel(pid, () => refreshProjects()),
    ]);
    body.appendChild(addWrap);
  }

  // --- everything else, folded away ---------------------------------------
  const defTitle = stats.exists ? "Edit the definition" : "Define the corpus";
  const defSub = stats.exists ? "changes here need a rebuild" : "what should the engine read?";
  const def = disclosure(defTitle, defSub, () => {
    const wrap = el("div", {});
    if (stats.exists) {
      wrap.appendChild(notice(
        "Editing these fields changes what the NEXT build reads. The graph you have now is not "
        + "touched until you rebuild, and a rebuild discards it and starts over.", "warn"));
    }
    // Save is secondary here: the build button beside it is the consequential action.
    const ed = specEditor(pid, rec.spec, async () => { await refreshProjects(); }, { saveKind: "" });
    wrap.appendChild(ed);
    // The build button joins the editor's own save row: saving and then rebuilding is one thought.
    const buildBtn = button(stats.exists ? "Save and rebuild" : "Build the corpus", "primary",
      (e) => guard(e.target, wrap, async () => {
        if (stats.exists && !confirm(
          `Rebuild "${rec.name}"? The current graph — ${pnum(stats.claims.n)} claims — is discarded `
          + "and every paper is read again.")) return;
        await ed.save();
        await rebuild("build");
      }));
    if (running) buildBtn.disabled = true;
    ed.querySelector(".prow").appendChild(buildBtn);
    wrap.appendChild(el("h3", { class: "psec small" }, "Ask the assistant"));
    wrap.appendChild(assistantPanel(pid, () => EXTRA_VIEWS.corpus()));
    return wrap;
  });
  if (!stats.exists) def.open = true;      // nothing built yet: this is the page
  body.appendChild(def);

  body.appendChild(disclosure("History", `${jl.length} job${jl.length === 1 ? "" : "s"}`,
                              () => jobHistory(pid, jl, body)));

  body.appendChild(disclosure("Delete this analysis", "permanent", () => {
    const w = el("div", {});
    w.appendChild(button("Delete it and its corpus", "danger", (e) => guard(e.target, w, async () => {
      if (!confirm(`Delete "${rec.name}" and its corpus? This cannot be undone.`)) return;
      await postJSON(`/api/projects/${encodeURIComponent(pid)}/delete`, { purge: true });
      await refreshProjects();
      setProject(state.projects[0] ? state.projects[0].id : null, { silent: true });
      location.hash = "projects";
    })));
    return w;
  }));
};

function jobHistory(pid, jl, errHost) {
  if (!jl.length) return el("div", { class: "empty small" }, "Nothing has run yet.");
  return el("div", { class: "jlist" }, jl.map((j) => {
    const row = el("div", { class: "jrow" }, [
      el("span", { class: `jdot ${j.status}` }),
      el("span", { class: "jid mono" }, j.run_id || j.id),
      el("span", { class: "jkind" }, (j.dry ? "dry " : "") + j.kind),
      el("span", { class: "grow" }),
      el("span", { class: "jwhen" }, j.started ? agoTime(j.started) : ""),
      j.status === "running"
        ? button("Cancel", "ghost small", (e) => guard(e.target, errHost, async () => {
            await postJSON(`/api/projects/${encodeURIComponent(pid)}/jobs/${j.id}/cancel`, {});
            await EXTRA_VIEWS.corpus();
          }))
        : button("Log", "ghost small", async () => {
            const d = await getJSON(`/api/projects/${encodeURIComponent(pid)}/jobs/${j.id}/log`);
            const pre = row.nextSibling && row.nextSibling.classList &&
                        row.nextSibling.classList.contains("jlog") ? row.nextSibling : null;
            if (pre) { pre.remove(); return; }
            row.after(el("pre", { class: "jlog" }, d.log || "(the process wrote nothing)"));
          }),
    ]);
    if (j.kind === "run" && j.run_id) {
      row.querySelector(".jid").addEventListener("click", () => {
        location.hash = `workflow/${j.run_id}`;
      });
      row.querySelector(".jid").classList.add("link");
    }
    if (j.error) row.appendChild(el("span", { class: "jerr" }, j.error));
    return row;
  }));
}

/* ---- starting a run ------------------------------------------------------ */

/** The launcher: a question and a step budget. The question lives here and only here: a corpus is
    built once and asked many different things, so it is never prefilled from the corpus. */
function openRunLauncher(pid, rec, host) {
  if (host.querySelector(".runlaunch")) { host.innerHTML = ""; return; }
  host.innerHTML = "";
  const goal = el("textarea", { class: "ptext", rows: "3", placeholder:
    "e.g. What sets the protein turnover of gene A in this cell type, and is the known E3 ligase the only route?" });
  const steps = el("input", { class: "pinput", type: "number", min: "1", max: "200", value: "30" });
  const box = el("div", { class: "runlaunch" }, [
    el("h3", { class: "psec small" }, "Start an investigation"),
    field("What do you want to find out?", goal,
          "The question is set per run, not per corpus — the same corpus can be asked different "
          + "things, and each run records the question it was given."),
  ]);
  // What the engine can actually read, so the question can be written against it rather than blind.
  const theme = (rec.spec && rec.spec.theme) || "";
  if (theme) {
    box.appendChild(el("details", { class: "pdisc" }, [
      el("summary", {}, [el("span", { class: "pd-title" }, "What this corpus covers")]),
      el("div", { class: "pd-body" }, [el("div", { class: "pquote" }, theme)]),
    ]));
  }
  box.appendChild(el("div", { class: "pgrid4" }, [field("Steps", steps)]));
  box.appendChild(el("p", { class: "pfine" },
    "This costs model tokens and runs experiment code in a Docker sandbox. It keeps going in the "
    + "background if you close the page."));
  const bar = el("div", { class: "prow" }, [
    button("Start", "primary", (e) => guard(e.target, box, async () => {
      const job = await postJSON(`/api/projects/${encodeURIComponent(pid)}/run`,
                                 { goal: goal.value.trim(), steps: Number(steps.value) });
      location.hash = `workflow/${job.run_id}`;
    })),
    button("Cancel", "ghost", () => { host.innerHTML = ""; }),
  ]);
  box.appendChild(bar);
  host.appendChild(box);
  goal.focus();
}

/** A run has no fixed stage list the way a build does, so it gets a line of its own rather than the
    build monitor's checklist. */
function runMonitor(pid, job) {
  const host = el("div", { class: "monitor" });
  const line = el("div", { class: "mon-headline" }, "Starting…");
  host.append(line, el("div", { class: "prow" }, [
    button("Watch it", "primary", () => { location.hash = `workflow/${job.run_id}`; }),
    button("Stop", "ghost", (e) => guard(e.target, host, async () => {
      await postJSON(`/api/projects/${encodeURIComponent(pid)}/jobs/${job.id}/cancel`, {});
      await EXTRA_VIEWS.corpus();
    })),
  ]));
  const es = new EventSource(
    `/api/projects/${encodeURIComponent(pid)}/jobs/${encodeURIComponent(job.id)}/stream`);
  es.addEventListener("progress", (e) => {
    try {
      const ev = JSON.parse(e.data);
      if (ev._heartbeat) return;
      if (ev.stage === "fail") { line.textContent = ev.msg || "The run failed"; line.className = "mon-headline bad"; }
      else if (ev.stage === "finish") { line.textContent = ev.msg || "Done"; line.className = "mon-headline good"; }
      else if (ev.msg) line.textContent = ev.msg;
    } catch {}
  });
  es.addEventListener("end", () => es.close());
  es.onerror = () => es.close();
  projStreams.push(es);
  return host;
}

/* ============================================================================
   Shared components
   ========================================================================== */

/* ---- the spec editor ----------------------------------------------------- */

function specEditor(pid, spec, onSaved, opts = {}) {
  const host = el("div", { class: "pcard-form" });
  const lines = (a) => (a || []).join("\n");

  const scope = el("textarea", { class: "ptext", rows: "2" }, spec.scope || "");
  const theme = el("textarea", { class: "ptext", rows: "4" }, spec.theme || "");
  const queries = el("textarea", { class: "ptext mono", rows: "8" }, lines(spec.queries));
  const seeds = el("textarea", { class: "ptext mono", rows: "3" }, lines(spec.seed_dois));
  const n = el("input", { class: "pinput", type: "number", min: "5", max: "2000",
                          value: String(spec.n_papers) });
  const ymin = el("input", { class: "pinput", type: "number", placeholder: "any",
                             value: spec.year_min || "" });
  const ymax = el("input", { class: "pinput", type: "number", placeholder: "any",
                             value: spec.year_max || "" });
  const conc = el("input", { class: "pinput", type: "number", min: "1", max: "40",
                             value: String(spec.concurrency) });
  const ftOnly = el("input", { type: "checkbox", ...(spec.full_text_only ? { checked: "checked" } : {}) });

  // No goal field here, and no wording that implies one. What the engine is ASKED is set when a run
  // starts; this form only says what the collection contains.
  host.appendChild(field("Scope — what this corpus covers, and what it leaves out", scope,
    "A description, not a question. It is written into the corpus card so the engine knows the "
    + "shape of what it can read, including what is absent, so it does not read a gap in the corpus "
    + "as a finding about biology."));
  host.appendChild(field("Theme — the relevance target", theme,
    "Every candidate paper is ranked by how close it is to this text. Write it like the abstract of "
    + "the ideal paper."));
  host.appendChild(field("Literature queries (one per line)", queries,
    "Europe PMC syntax: AND / OR / NOT, \"quoted phrases\", AUTH:\"Lastname I\". Each line is an "
    + "independent discovery channel; partial overlap between them is what lets the build estimate "
    + "whether the corpus is saturated."));
  host.appendChild(el("div", { class: "pgrid4" }, [
    field("Max papers", n),
    field("From year", ymin),
    field("To year", ymax),
    field("Extract in parallel", conc),
  ]));
  host.appendChild(field("Force-include these DOIs (one per line)", seeds,
    "Anchors that relevance ranking is not allowed to drop."));
  // `exclude_terms` is not edited here: it is a research control for held-out builds, set from the
  // CLI, and preserved on save rather than blanked.
  host.appendChild(el("label", { class: "pcheck" }, [ftOnly,
    el("span", {}, "Full text only — drop papers where only the abstract could be fetched")]));

  const status = el("span", { class: "psaved" });
  // Exposed on the host so the corpus page can save and then rebuild without faking a click.
  host.save = async () => {
    const patch = {
      scope: scope.value, theme: theme.value,
      queries: queries.value.split("\n"), seed_dois: seeds.value.split("\n"),
      n_papers: Number(n.value), concurrency: Number(conc.value),
      year_min: ymin.value === "" ? null : Number(ymin.value),
      year_max: ymax.value === "" ? null : Number(ymax.value),
      full_text_only: ftOnly.checked,
    };
    const rec = await postJSON(`/api/projects/${encodeURIComponent(pid)}`, { spec: patch });
    status.textContent = `saved · ${rec.spec.queries.length} queries`;
    setTimeout(() => { status.textContent = ""; }, 4000);
    if (onSaved) await onSaved(rec);
    return rec;
  };
  // `??`, not `||`: "" means a plain button.
  const save = button("Save definition", opts.saveKind ?? "primary",
                      (e) => guard(e.target, host, host.save));
  host.appendChild(el("div", { class: "prow" }, [save, status]));
  return host;
}

/* ---- the assistant panel ------------------------------------------------- */

function assistantPanel(pid, onApplied, seedReply) {
  const host = el("div", { class: "chat" });
  const log = el("div", { class: "chat-log" });
  const input = el("textarea", { class: "ptext", rows: "3",
    placeholder: "Ask for narrower queries, a different angle, a date cutoff… (⌘/Ctrl+Enter to send)" });
  const sendBtn = button("Send", "primary", (e) => guard(e.target, host, send));

  host.append(log, el("div", { class: "chat-input" }, [input, sendBtn]));

  function bubble(role, text, patch) {
    const b = el("div", { class: `bub ${role}` }, [el("div", { class: "bub-text" }, text || "")]);
    if (patch && Object.keys(patch).length) {
      const summary = Object.entries(patch).map(([k, v]) =>
        `${k}: ${Array.isArray(v) ? v.length + " item(s)" : String(v).slice(0, 60)}`).join("  ·  ");
      const card = el("div", { class: "patch" }, [
        el("div", { class: "patch-head" }, "Proposed change"),
        el("div", { class: "patch-sum mono" }, summary),
        el("details", {}, [el("summary", {}, "see it"),
                           el("pre", {}, JSON.stringify(patch, null, 2))]),
      ]);
      card.appendChild(el("div", { class: "prow" }, [
        button("Apply to the definition", "primary small", (e) => guard(e.target, host, async () => {
          await postJSON(`/api/projects/${encodeURIComponent(pid)}/chat/apply`, { patch });
          card.appendChild(notice("Applied.", "good"));
          if (onApplied) await onApplied();
        })),
      ]));
      b.appendChild(card);
    }
    log.appendChild(b);
    log.scrollTop = log.scrollHeight;
    return b;
  }

  async function send() {
    const msg = input.value.trim();
    if (!msg) return;
    input.value = "";
    bubble("user", msg);
    const thinking = bubble("assistant pending", "thinking…");
    try {
      const res = await postJSON(`/api/projects/${encodeURIComponent(pid)}/chat`, { message: msg });
      thinking.remove();
      bubble("assistant", res.reply, res.patch);
    } catch (e) {
      thinking.remove();
      bubble("assistant error", e.message);
    }
  }
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); send(); }
  });

  // Replay the stored conversation — it lives on the project, so it survives a reload.
  getJSON(`/api/projects/${encodeURIComponent(pid)}`).then((rec) => {
    for (const t of rec.chat || []) bubble(t.role, t.content, t.patch);
    if (seedReply) bubble("assistant", seedReply);
    if (!log.children.length)
      log.appendChild(el("div", { class: "empty small" },
        "Describe what you want covered and the assistant will propose queries."));
  }).catch(() => {});

  return host;
}

/* ---- attachments --------------------------------------------------------- */

function attachPanel(pid, onChange) {
  const host = el("div", { class: "attach" });
  const listEl = el("div", { class: "attach-list" });
  const drop = el("div", { class: "dropzone", tabindex: "0" }, [
    el("div", { class: "dz-title" }, "Drop PDFs here, or click to choose"),
    el("div", { class: "dz-sub" }, "pdf · txt · md · xml — read into text as soon as they land"),
  ]);
  const picker = el("input", { type: "file", multiple: "multiple", style: "display:none",
                               accept: ".pdf,.txt,.md,.xml,.nxml" });
  const status = el("div", { class: "attach-status" });

  async function upload(files) {
    for (const f of files) {
      const row = el("div", { class: "attach-row pending" }, [
        el("span", { class: "af-name" }, f.name), el("span", { class: "af-meta" }, "reading…")]);
      listEl.prepend(row);
      try {
        const r = await fetch(`/api/projects/${encodeURIComponent(pid)}/attachments`, {
          method: "POST", headers: { "X-Filename": encodeURIComponent(f.name) }, body: f });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.error || r.statusText);
        row.remove();
      } catch (e) {
        row.className = "attach-row failed";
        row.lastChild.textContent = e.message;
        continue;
      }
    }
    await load();
    if (onChange) await onChange();
  }

  async function load() {
    let atts = [];
    try { atts = (await getJSON(`/api/projects/${encodeURIComponent(pid)}/attachments`)).attachments || []; }
    catch (e) { status.textContent = e.message; return; }
    listEl.innerHTML = "";
    if (!atts.length) { status.textContent = "No documents uploaded."; return; }
    status.textContent = `${atts.length} document(s) · ${pnum(
      atts.reduce((a, b) => a + (b.n_chars || 0), 0))} characters of text`;
    for (const a of atts) {
      listEl.appendChild(el("div", { class: "attach-row" }, [
        el("span", { class: "af-name" }, a.filename),
        el("span", { class: "af-meta" },
           `${pnum(a.n_chars)} chars${a.doi ? " · " + a.doi : ""}${a.year ? " · " + a.year : ""}`),
        el("span", { class: "grow" }),
        button("Remove", "ghost small", (e) => guard(e.target, host, async () => {
          await postJSON(`/api/projects/${encodeURIComponent(pid)}/attachments/${a.id}/delete`, {});
          await load();
          if (onChange) await onChange();
        })),
      ]));
    }
  }

  drop.addEventListener("click", () => picker.click());
  drop.addEventListener("keydown", (e) => { if (e.key === "Enter") picker.click(); });
  picker.addEventListener("change", () => upload([...picker.files]));
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => {
    e.preventDefault();
    drop.classList.remove("over");
    upload([...e.dataTransfer.files]);
  });

  host.append(drop, picker, status, listEl);
  load();
  return host;
}

/* ---- the build monitor --------------------------------------------------- */

// The stages a build reports, in the order they run. Fixed here rather than discovered from the
// stream so the whole pipeline is visible from the first second — you can see what is still to come,
// not just what has happened.
const BUILD_STAGES = [
  ["plan", "Plan"], ["discover", "Search the literature"], ["dedup", "De-duplicate"],
  ["filter", "Apply the filters"], ["known", "Skip what we have"], ["triage", "Rank by relevance"],
  ["fetch", "Fetch full text"], ["attach", "Fold in your documents"],
  ["extract", "Extract claims (model)"], ["store", "Write the graph"],
  ["status", "Label contradictions"], ["papers", "Store full text"], ["card", "Write the corpus card"],
];

function jobMonitor(pid, jobId, opts = {}) {
  const host = el("div", { class: "monitor" });
  const headline = el("div", { class: "mon-headline" }, "Starting…");
  const rows = {};
  const list = el("div", { class: "mon-stages" });
  for (const [id, label] of BUILD_STAGES) {
    const bar = el("div", { class: "mon-bar" }, [el("i", {})]);
    const row = el("div", { class: "mon-row", "data-stage": id }, [
      el("span", { class: "mon-dot" }),
      el("span", { class: "mon-label" }, label),
      el("span", { class: "mon-msg" }, ""),
      bar,
    ]);
    rows[id] = { row, bar: bar.firstChild, msg: row.querySelector(".mon-msg") };
    list.appendChild(row);
  }
  const summary = el("div", { class: "mon-summary" });
  host.append(headline, list, summary);
  if (!jobId) { headline.textContent = "No build running."; return host; }

  const apply = (ev) => {
    if (ev._heartbeat) return;
    if (ev.stage === "finish" || ev.stage === "fail") {
      const bad = ev.stage === "fail";
      headline.textContent = ev.msg || (bad ? "Build failed" : "Done");
      headline.className = "mon-headline " + (bad ? "bad" : "good");
      if (ev.summary) summary.appendChild(buildSummary(ev.summary));
      if (opts.onFinish) opts.onFinish(ev);
      return;
    }
    const r = rows[ev.stage];
    if (!r) return;
    for (const k of Object.keys(rows)) rows[k].row.classList.remove("active");
    if (ev.status === "warn") {
      r.row.classList.add("warn");
      r.msg.textContent = ev.msg || "";
      return;
    }
    r.row.classList.add(ev.status === "done" ? "done" : "active");
    r.msg.textContent = ev.msg || "";
    headline.textContent = ev.msg || "";
    headline.className = "mon-headline";
    if (ev.done != null && ev.total) {
      r.bar.style.width = `${Math.round((ev.done / ev.total) * 100)}%`;
      r.row.classList.add("has-bar");
    } else if (ev.status === "done") {
      r.bar.style.width = "100%";
      r.row.classList.add("has-bar");
    }
  };

  const es = new EventSource(
    `/api/projects/${encodeURIComponent(pid)}/jobs/${encodeURIComponent(jobId)}/stream`);
  es.addEventListener("progress", (e) => { try { apply(JSON.parse(e.data)); } catch {} });
  es.addEventListener("end", () => es.close());
  es.onerror = () => {
    // An SSE error after the job finished is just the stream closing; only say something if the
    // build is still supposed to be running.
    getJSON(`/api/projects/${encodeURIComponent(pid)}/jobs/${encodeURIComponent(jobId)}`)
      .then((d) => {
        if (d.job.status === "running") headline.textContent = "Lost the progress stream — reload to reattach.";
        es.close();
      }).catch(() => es.close());
  };
  projStreams.push(es);
  return host;
}

function buildSummary(s) {
  const box = el("div", { class: "sumbox" });
  if (s.dry) {
    box.appendChild(el("div", { class: "tiles wide" }, [
      tile(pnum(s.n_candidates), "candidates found"),
      tile(pnum(s.n_selected), "selected"),
      tile(s.completeness ? `${Math.round((s.completeness.completeness || 0) * 100)}%` : "—",
           "estimated coverage"),
      tile(s.score_range || "—", "relevance span"),
    ]));
    if (s.papers && s.papers.length) {
      box.appendChild(el("div", { class: "psec small" }, "Top of the selected set"));
      box.appendChild(el("div", { class: "plist" }, s.papers.slice(0, 20).map((p) =>
        el("div", { class: "prow-paper" }, [
          el("span", { class: "pp-year mono" }, String(p.year || "—")),
          el("span", { class: "pp-title" }, p.title),
          el("span", { class: "pp-score mono" }, (p.score || 0).toFixed(3)),
        ]))));
    }
    return box;
  }
  box.appendChild(el("div", { class: "tiles wide" }, [
    tile(pnum(s.n_papers), "papers read"),
    tile(pnum(s.n_claims), "claims extracted"),
    tile(pnum(s.kg ? s.kg.entities : 0), "entities"),
    tile(fmtDur(s.elapsed_s), "elapsed"),
  ]));
  return box;
}

/* ---- the graph tab's empty state ---------------------------------------- */

/** Returns true if it took over the page (nothing to draw yet). */
async function kgEmptyState(mainEl, head) {
  let stats, rec;
  try {
    [stats, rec] = await Promise.all([
      getJSON(`/api/projects/${encodeURIComponent(state.project)}/kg`),
      getJSON(`/api/projects/${encodeURIComponent(state.project)}`),
    ]);
  } catch { return false; }
  head.appendChild(el("span", { class: "grow" }));
  head.appendChild(el("span", { class: "page-sub" }, rec.name));
  if (stats.exists && stats.claims.n) return false;

  const body = el("div", { class: "pscroll" });
  mainEl.appendChild(body);
  const ready = (rec.spec.queries || []).length && rec.spec.theme;
  body.appendChild(el("div", { class: "bigempty" }, [
    el("h2", {}, "This analysis has no graph yet"),
    el("p", {}, ready
      ? "The corpus definition is ready — build it and the graph appears here."
      : "Define the corpus first: what literature should the engine read?"),
    el("div", { class: "prow center" }, [
      button(ready ? "Go to the corpus page" : "Define the corpus", "primary",
             () => { location.hash = "corpus"; }),
      button("Switch analysis", "ghost", () => { location.hash = "projects"; }),
    ]),
  ]));
  return true;
}

/* ============================================================================
   The Workflow view's knowledge-graph lane

   The Engine and Verification lanes are driven by a run's event stream. This
   lane cannot be: the corpus is built before any run exists, by a different
   process, and its state lives in the graph file and the build's progress
   stream. So it is filled from /api/projects/<id>/lane instead, and it keeps
   itself live while a build is running.
   ========================================================================== */

const KG_LANE_IDS = ["find", "extract", "kg", "semantic"];
let kgLaneTimer = null;

async function paintKGLane() {
  clearTimeout(kgLaneTimer);
  if (!state.project || typeof wf === "undefined" || !wf.boxes) return;
  let lane;
  try { lane = await getJSON(`/api/projects/${encodeURIComponent(state.project)}/lane`); }
  catch { return; }
  if (state.view !== "workflow") return;

  for (const id of KG_LANE_IDS) {
    const box = wf.boxes[id];
    const n = lane.nodes[id];
    if (!box || !n) continue;
    const stat = box.querySelector(".fc-stat");
    // `kg` is also written every frame by paintFlow from the run's own database. Leave it alone
    // rather than have two writers fight over one element.
    if (stat && id !== "kg") stat.textContent = n.badge || "—";
    box.classList.remove("kgl-active", "kgl-done", "kgl-armed");
    if (n.state === "active") box.classList.add("kgl-active");
    else if (n.state === "done") box.classList.add("kgl-done");
    else if (n.state === "armed") box.classList.add("kgl-armed");
    if (n.detail) box.title = `${n.badge ? n.badge + " — " : ""}${n.detail}`;
  }

  // A collapsed section during a live build hides the only thing moving. Open it, and say what is
  // happening in a summary line this lane owns.
  const sec = wf.kgSection;
  if (sec) {
    const head = sec.querySelector(".fc-sec-head");
    let sub = sec.querySelector(".kgl-sub");
    if (!sub && head) {
      sub = el("span", { class: "kgl-sub" });
      head.appendChild(sub);
    }
    // Open the lane when there is something in it; a manual collapse still sticks.
    const hasContent = lane.stats && lane.stats.exists && lane.stats.claims.n > 0;
    if (hasContent && !lane.live && !sec.dataset.userToggled) {
      sec.classList.remove("collapsed");
      const caret = sec.querySelector(".fc-caret");
      if (caret) caret.textContent = "▾";
      if (!sec.dataset.autoOpened) {
        sec.dataset.autoOpened = "1";
        requestAnimationFrame(() => drawFlowEdges(document.querySelector(".fc")));
      }
    }
    if (!sec.dataset.toggleWatched) {
      sec.dataset.toggleWatched = "1";
      const h = sec.querySelector(".fc-sec-head");
      if (h) h.addEventListener("click", () => { sec.dataset.userToggled = "1"; });
    }

    if (lane.live) {
      if (sec.classList.contains("collapsed")) {
        sec.classList.remove("collapsed");
        const caret = sec.querySelector(".fc-caret");
        if (caret) caret.textContent = "▾";
        requestAnimationFrame(() => drawFlowEdges(document.querySelector(".fc")));
      }
      if (sub) sub.textContent = `building now — ${lane.last_message || lane.stage}`;
      sec.classList.add("kgl-live");
    } else {
      sec.classList.remove("kgl-live");
      const s = lane.stats;
      if (sub && s && s.exists)
        sub.textContent = `${pnum(s.papers.n)} papers · ${pnum(s.claims.n)} claims · `
          + `${pnum(s.claims.entities)} entities · built offline`;
      else if (sub && !s.exists)
        sub.textContent = "no corpus built for this analysis yet";
    }
  }
  if (lane.live) kgLaneTimer = setTimeout(paintKGLane, 3000);
}

/** The Workflow view when this analysis has a corpus but no engine runs yet. */
function workflowNoRuns(host) {
  const body = el("div", { class: "pscroll" });
  host.appendChild(body);
  const cur = activeProject();
  const hasKG = cur && cur.has_kg;
  const launcher = el("div", { class: "panel-host" });
  body.appendChild(el("div", { class: "bigempty" }, [
    el("h2", {}, "No investigations in this analysis yet"),
    el("p", {}, hasKG
      ? `“${cur.name}” has a corpus. Start a run and the engine reasons over it — roaming the graph, `
        + "writing and running its own experiment code, and handing survivors to verification."
      : "Build this analysis's corpus first — the engine reasons over the graph, so there is nothing "
        + "to investigate until one exists."),
    el("div", { class: "prow center" }, [
      hasKG
        ? button("Start an investigation", "primary", async () => {
            const rec = await getJSON(`/api/projects/${encodeURIComponent(state.project)}`);
            openRunLauncher(state.project, rec, launcher);
          })
        : button("Go to the corpus", "primary", () => { location.hash = "corpus"; }),
      button("All analyses", "ghost", () => { location.hash = "projects"; }),
    ]),
  ]));
  body.appendChild(launcher);
}

/* ---------------------------------------------------------------------------
   Deep links vs scoping

   Scoping hides other analyses' runs — which is the point, until somebody opens
   `#workflow/<run>` for a run that lives in a different analysis. Then the
   picker has nothing to select and the page renders somebody else's run, or
   none. A URL naming a run is an unambiguous instruction; the right response is
   to FOLLOW it and move the scope to match, not to quietly ignore it.
   --------------------------------------------------------------------------- */

let runProjectCache = null;

async function ensureScopeForRun(runId) {
  if (!runId) return false;
  // Unscoped already shows every run, so there is nothing to widen — and narrowing here would undo
  // the user's explicit "show me everything" the moment the URL happened to name a run.
  if (!state.project) return false;
  try {
    // Unscoped by design: the question is "where does this run live?", so filtering the answer by the
    // current project would assume the answer.
    if (!runProjectCache) {
      const rows = await (await fetch("/api/runs?project=all&all=1")).json();
      runProjectCache = new Map(rows.map((r) => [r.run_id, r.project || null]));
    }
    if (!runProjectCache.has(runId)) return false;      // unknown run: let the view 404
    const owner = runProjectCache.get(runId);
    if (owner === state.project) return false;
    setProject(owner, { silent: true });                 // silent: route() is already running
    return true;
  } catch {
    return false;
  }
}
