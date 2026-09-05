// Standalone presentation prototype. These illustrative records are never production fixtures.
const $ = (selector) => document.querySelector(selector);
const nodes = [
  {
    id: "v1",
    x: 325,
    y: 235,
    label: "BRAF V600E",
    sub: "VARIANT",
    kind: "hub",
    r: 57,
  },
  { id: "g1", x: 160, y: 125, label: "BRAF", sub: "GENE", r: 28 },
  { id: "g2", x: 160, y: 365, label: "MAPK", sub: "PATHWAY", r: 25 },
  {
    id: "v2",
    x: 490,
    y: 120,
    label: "Related variant",
    sub: "HISTORICAL CONTEXT",
    r: 30,
  },
  { id: "d1", x: 490, y: 370, label: "Melanoma", sub: "DISEASE", r: 30 },
  {
    id: "t1",
    x: 785,
    y: 205,
    label: "Therapy group A",
    sub: "CANDIDATE 01",
    kind: "therapy",
  },
  {
    id: "t2",
    x: 775,
    y: 385,
    label: "Therapy group B",
    sub: "CANDIDATE 02",
    kind: "therapy",
  },
  {
    id: "t3",
    x: 740,
    y: 500,
    label: "Therapy group C",
    sub: "CANDIDATE 03",
    kind: "therapy",
  },
  { id: "p1", x: 80, y: 245, label: "Prior study", r: 12 },
  { id: "p2", x: 325, y: 70, label: "Variant context", r: 12 },
  { id: "p3", x: 325, y: 450, label: "Assay evidence", r: 12 },
  { id: "p4", x: 605, y: 255, label: "Shared target", r: 18, added: true },
  { id: "p5", x: 610, y: 470, label: "Disease context", r: 12, added: true },
  { id: "p6", x: 640, y: 75, label: "Prior association", r: 12, added: true },
];
nodes.forEach((node) => {
  node.y = node.y * 0.68 + 10;
});
const edges = [
  ["g1", "v1"],
  ["g2", "v1"],
  ["g1", "v2"],
  ["v1", "d1"],
  ["g1", "p1"],
  ["g2", "p1"],
  ["v1", "p2"],
  ["g2", "p3"],
  ["p3", "d1"],
  ["v2", "t1"],
  ["d1", "t2"],
  ["v2", "p6"],
  ["p6", "t1"],
  ["v1", "p4"],
  ["p4", "t1"],
  ["d1", "p5"],
  ["p5", "t3"],
];
const candidates = [
  {
    target: "t1",
    name: "Therapy group A",
    why: "A related variant and shared target create two historical support paths.",
    outcome: "Later recorded",
    observed: true,
  },
  {
    target: "t2",
    name: "Therapy group B",
    why: "The historical disease neighborhood provides a second candidate connection.",
    outcome: "Later recorded",
    observed: true,
  },
  {
    target: "t3",
    name: "Therapy group C",
    why: "A weaker disease-context path motivates another candidate for follow-up.",
    outcome: "Not recorded by horizon",
    observed: false,
  },
];
const scenes = [
  {
    title: "What could we see in 2018?",
    description:
      "A small biological neighborhood. Later evidence stays out of view.",
    label: "THE HISTORICAL FRONTIER",
    kicker: "01 / FREEZE HISTORY",
    change: "SNAPSHOT READY",
    text: "The future is withheld. Start with the connections available at the cutoff.",
    next: "Evolve the graph",
  },
  {
    title: "Evidence changes the frontier.",
    description:
      "Newly inspected historical evidence adds paths worth following.",
    label: "THE GRAPH IS EVOLVING",
    kicker: "02 / FOLLOW THE EVIDENCE",
    change: "3 CONTEXT NODES ADDED",
    text: "A shared target connects two neighborhoods. The next candidate has a reason.",
    next: "Lock the forecasts",
  },
  {
    title: "A connection worth looking for.",
    description:
      "Ranked using historical information. Later outcomes remain locked.",
    label: "FORECASTS LOCKED · 2018",
    kicker: "03 / MAKE A PREDICTION",
    change: "RANKING FROZEN",
    text: "Select a candidate to illuminate its support. These ranks will not change on reveal.",
    next: "Reveal 2022 evidence",
  },
  {
    title: "Then, let history answer.",
    description:
      "The same forecasts. A later evidence packet. An inspectable result.",
    label: "LATER EVIDENCE · 2022",
    kicker: "04 / REVEAL THE EVIDENCE",
    change: "EVIDENCE UNLOCKED",
    text: "Two illustrative associations later recorded. One remains unrecorded by the horizon.",
    next: "Replay the story",
  },
];
let stage = 0,
  selected = 0,
  focused = false,
  unlocked = false,
  sourceOpen = false;
const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
function path(a, b, bend = 0) {
  return `M ${a.x} ${a.y} Q ${(a.x + b.x) / 2} ${(a.y + b.y) / 2 + bend} ${b.x} ${b.y}`;
}
function supportIds() {
  return selected === 0
    ? ["v1", "g1", "v2", "p4", "t1"]
    : selected === 1
      ? ["v1", "d1", "t2"]
      : ["v1", "d1", "p5", "t3"];
}
function graph() {
  const support = supportIds();
  $("#edges").innerHTML = edges
    .filter(([a, b]) => stage > 0 || (!byId[a].added && !byId[b].added))
    .map(([a, b]) => {
      const isSupport = focused && support.includes(a) && support.includes(b);
      return `<path class="edge ${stage === 1 && (byId[a].added || byId[b].added) ? "new" : ""} ${focused ? (isSupport ? "highlight" : "dim") : ""}" d="${path(byId[a], byId[b], 18)}"/>`;
    })
    .join("");
  $("#nodes").innerHTML = nodes
    .filter((n) => stage > 0 || !n.added)
    .map(
      (n) =>
        `<g class="node ${n.kind || ""} ${focused && !support.includes(n.id) ? "dim" : ""}" transform="translate(${n.x} ${n.y})">${n.kind === "therapy" ? '<rect x="-81" y="-27" width="162" height="54" rx="8"/>' : `<circle r="${n.r}"/>`}<text text-anchor="middle" y="${n.kind === "hub" ? 5 : n.kind === "therapy" ? 4 : n.r + 24}">${n.label}</text>${n.sub ? `<text class="sub" text-anchor="middle" y="${n.kind === "hub" ? 84 : n.kind === "therapy" ? 46 : n.r + 41}">${n.sub}</text>` : ""}</g>`,
    )
    .join("");
  $("#forecast-edges").innerHTML =
    stage < 2
      ? ""
      : candidates
          .map(
            (c, i) =>
              `<path class="forecast ${stage === 3 && c.observed ? "observed" : ""} ${selected !== i ? "dim" : ""}" d="${path(byId.v1, byId[c.target], -85)}"/>`,
          )
          .join("") +
        `<g transform="translate(455 155)"><rect class="graph-tag" width="165" height="29" rx="14"/><text class="graph-tag-text" text-anchor="middle" x="82" y="19">${stage === 3 ? (candidates[selected].observed ? "✓ Later recorded" : "○ Not yet recorded") : "? Forecast connection"}</text></g>`;
}
function candidateCards() {
  return candidates
    .map(
      (c, i) =>
        `<button class="candidate" data-candidate="${i}" aria-pressed="${i === selected}"><span class="rank">0${i + 1}</span><span><b>BRAF V600E →</b><b>${c.name}</b><small>${i === 0 ? "Shared target + variant context" : i === 1 ? "Disease neighborhood" : "Exploratory context"}</small>${stage === 3 ? `<span class="result">${c.observed ? "✓" : "○"} ${c.outcome}</span>` : ""}</span></button>`,
    )
    .join("");
}
function panel() {
  $("#panel-kicker").textContent = [
    "THE QUESTION",
    "WHY THE GRAPH MATTERS",
    "NEXT CONNECTIONS",
    "THE EVIDENCE REVEAL",
  ][stage];
  $("#panel-count").textContent = `0${stage + 1}—04`;
  if (stage === 0)
    return `<div class="large-year">2018</div><div class="year-caption">A FROZEN STARTING POINT</div><h2>Could we have seen<br>the next association?</h2><p class="question">Which variant–therapy connections will appear in later evidence?</p><div class="boundary"><strong>History is the test.</strong>Start with the earlier graph. Rank missing associations. Only then open the later snapshot.</div>`;
  if (stage === 1)
    return `<h2>More than a map.<br>A reason to look.</h2><p>Each update changes which missing connection is worth investigating.</p><div class="event"><b>01</b><div><strong>Inspect earlier evidence</strong>Read a prior association in the frozen source packet.</div></div><div class="event"><b>02</b><div><strong>Connect shared context</strong>Add a target and biological context to the graph.</div></div><div class="event"><b>03</b><div><strong>Surface a future candidate</strong>Trace a short path to a therapy group without peeking ahead.</div></div><div class="boundary"><strong>Graph growth ≠ time travel.</strong>We are processing evidence available at the cutoff. The 2022 outcome packet stays closed.</div>`;
  if (stage === 2)
    return `<h2>Three places<br>to look next.</h2><p>Illustrative ranking · 2018 information only</p>${candidateCards()}<p class="rationale">${candidates[selected].why}</p><div class="boundary">Forecasts are now locked. Reveal cannot reorder these candidates.</div>`;
  const c = candidates[selected];
  return `<div class="future-stamp">2022 / LATER SNAPSHOT OPENED</div><h2>${c.observed ? "The missing link<br>gets a record." : "Still an open<br>question."}</h2>${candidateCards()}<div class="source-card"><header><span>${c.observed ? "LATER EVIDENCE" : "UNRESOLVED"}</span><span>2022</span></header><section><h3>BRAF V600E →<br>${c.name}</h3><p>${c.observed ? "<mark>Association recorded in the later packet.</mark> Inspect the underlying record and its biological context." : "No association is recorded for this candidate by the horizon. Absence is not disproof."}</p><small>Illustrative outcome · not a real CIViC finding</small><button class="source-button" id="source" aria-expanded="${sourceOpen}">${sourceOpen ? "Hide record details ↑" : "Inspect evidence record ↗"}</button>${sourceOpen ? "<p><strong>Prototype record</strong><br>Source ID: illustrative-only<br>Snapshot: March 2022<br>Publication date: not supplied<br>Disease: melanoma<br>Treatment direction: not supplied<br>In the integrated demo, show the cached source excerpt and actual CIViC link here.</p>" : ""}</section></div>`;
}
function render() {
  const s = scenes[stage];
  document.body.dataset.stage = String(stage);
  for (const [id, value] of Object.entries({
    "scene-title": s.title,
    "scene-description": s.description,
    "graph-label": s.label,
    "graph-kicker": s.kicker,
    "change-type": s.change,
    "change-text": s.text,
    revision: `REVISION 0${Math.min(stage + 1, 3)}`,
    "lock-label":
      stage === 3 ? "Later evidence revealed" : "Later evidence is locked",
  }))
    $("#" + id).textContent = value;
  $("#panel-content").innerHTML = panel();
  $("#next").innerHTML = `${s.next} <span>→</span>`;
  document.querySelectorAll("[data-step]").forEach((b) => {
    const n = Number(b.dataset.step);
    if (n === stage) b.setAttribute("aria-current", "step");
    else b.removeAttribute("aria-current");
    b.disabled = n === 3 && !unlocked;
  });
  $("#lens").setAttribute("aria-pressed", String(focused));
  $("#lens").textContent = focused
    ? "◎ Show whole neighborhood"
    : "◎ Focus support path";
  graph();
  document.querySelectorAll("[data-candidate]").forEach(
    (b) =>
      (b.onclick = () => {
        selected = Number(b.dataset.candidate);
        focused = true;
        sourceOpen = false;
        render();
      }),
  );
  if ($("#source"))
    $("#source").onclick = () => {
      sourceOpen = !sourceOpen;
      render();
      $("#source").focus();
    };
  $("#announcement").textContent = `${s.title} ${s.text}`;
}
function go(next) {
  stage = Math.max(0, Math.min(3, next));
  if (stage >= 2) unlocked = true;
  focused = stage >= 2;
  sourceOpen = false;
  render();
}
function reset() {
  stage = 0;
  selected = 0;
  focused = false;
  unlocked = false;
  sourceOpen = false;
  $("#fallback-status").textContent = "";
  render();
}
$("#next").onclick = () => (stage === 3 ? reset() : go(stage + 1));
$("#reset").onclick = reset;
$("#lens").onclick = () => {
  focused = !focused;
  render();
};
document
  .querySelectorAll("[data-step]")
  .forEach((b) => (b.onclick = () => go(Number(b.dataset.step))));
$("#failure").onclick = () => {
  $("#fallback-status").textContent =
    "Service failure rehearsal: local illustrative replay remains available. Selection and stage preserved.";
};
document.addEventListener("keydown", (e) => {
  if (
    e.target.closest("button,a,input,textarea,select,summary") ||
    e.ctrlKey ||
    e.metaKey ||
    e.altKey
  )
    return;
  if (e.key === "ArrowRight") {
    e.preventDefault();
    go(stage + 1);
  }
  if (e.key === "ArrowLeft") {
    e.preventDefault();
    go(stage - 1);
  }
  if (e.key.toLowerCase() === "r") reset();
});
render();
