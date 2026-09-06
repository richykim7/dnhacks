import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  ChevronRight,
  ExternalLink,
  GitBranch,
  Maximize2,
  Pause,
  Play,
  RotateCcw,
  Search,
  Sparkles,
  LockKeyhole,
  Download,
  Clock3,
} from "lucide-react";
import { Button } from "./ui/button";
import { ForecastReasoning } from "./ForecastReasoning";
import {
  illustrativePacket,
  type ForecastPacket,
  type ForecastNode,
} from "../lib/forecasting";
import "../forecasting.css";

const stages = [
  {
    label: "Read the past",
    title: "A field, as it was.",
    copy: "Start with a dated body of evidence. Every connection has a source; the future stays closed.",
  },
  {
    label: "Connect evidence",
    title: "New evidence changes the map.",
    copy: "Follow a mechanism, read another source, and connect previously separate neighborhoods.",
  },
  {
    label: "Choose branches",
    title: "Spend attention where it adds something.",
    copy: "Greedy selection rewards additional evidence coverage. Two promising branches can cover the same ground.",
  },
  {
    label: "Commit forecasts",
    title: "Make the next connection testable.",
    copy: "Save the ranked recommendations and the graph they came from before opening later evidence.",
  },
  {
    label: "Open the future",
    title: "Now see what the later record contains.",
    copy: "Match saved predictions to later evidence. Unobserved connections remain visible.",
  },
];
const typeLabels: Record<string, string> = {
  gene: "Genes",
  variant: "Variants",
  disease: "Disease context",
  therapy: "Therapy groups",
  therapy_group: "Therapy groups",
};
const year = (date: string) => date.slice(0, 4);
const short = (text: string, n = 23) =>
  text.length > n ? text.slice(0, n - 1) + "…" : text;
function download(packet: ForecastPacket) {
  if (packet.artifact_url) {
    const a = document.createElement("a");
    a.href = packet.artifact_url;
    a.download = `${packet.scenario.id}-run.json`;
    a.click();
    return;
  }
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(packet, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = `${packet.scenario.id}-replay.json`;
  a.click();
  URL.revokeObjectURL(url);
}
export function Forecasting() {
  const [packet, setPacket] = useState<ForecastPacket>(illustrativePacket);
  const [stage, setStage] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [selected, setSelected] = useState("");
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState("auto");
  const [connection, setConnection] = useState("Preparing historical run");
  const [focusedCandidate, setFocusedCandidate] = useState("");
  const inspector = useRef<HTMLElement>(null);
  useEffect(() => {
    inspector.current?.scrollTo({ top: 0 });
  }, [selected, focusedCandidate, stage]);
  useEffect(() => {
    if (provider === "illustrative") {
      setPacket(illustrativePacket);
      setConnection("Illustrative walkthrough");
      return;
    }
    const abort = new AbortController();
    const load = async () => {
      try {
        const r = await fetch("/api/forecasting/demo", {
          signal: abort.signal,
        });
        if (!r.ok) return;
        const value = await r.json();
        if (value.scenario && value.run) {
          setPacket(value);
          setConnection("Recorded historical run");
        }
      } catch {
        /* The illustrative provider remains available during preparation. */
      }
    };
    void load();
    const timer = setInterval(load, 10000);
    return () => {
      abort.abort();
      clearInterval(timer);
    };
  }, [provider]);
  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(
      () =>
        setStage((s) => {
          if (s >= 4) {
            setPlaying(false);
            return 4;
          }
          return s + 1;
        }),
      4200,
    );
    return () => clearInterval(timer);
  }, [playing]);
  const { scenario, run } = packet;
  const illustrative = run.origin === "illustrative";
  useEffect(() => {
    setSelected("");
    setFocusedCandidate("");
    setStage(0);
    setPlaying(false);
  }, [scenario.id]);
  const revisions = run.revisions || [];
  const revisionIndex =
    stage === 0
      ? 0
      : stage === 1
        ? Math.min(2, revisions.length - 1)
        : revisions.length - 1;
  const frame = revisions[revisionIndex];
  const acquiredIds = useMemo(
    () => new Set(frame?.evidence_ids || scenario.evidence.map((e) => e.id)),
    [frame, scenario],
  );
  const acquiredClaims = useMemo(
    () =>
      scenario.claims
        .filter((c) => c.evidence_ids.some((id) => acquiredIds.has(id)))
        .map((c) => ({
          ...c,
          evidence_ids: c.evidence_ids.filter((id) => acquiredIds.has(id)),
          contexts: c.contexts?.filter(
            (ctx) => !ctx.evidence_id || acquiredIds.has(ctx.evidence_id),
          ),
        })),
    [scenario, acquiredIds],
  );
  const nodes = useMemo(
    () => new Map(scenario.nodes.map((n) => [n.id, n])),
    [scenario],
  );
  const predictions = useMemo(
    () =>
      (stage < 3 && frame ? frame.forecasts : run.forecasts)
        .slice(0, 5)
        .map((f) => ({
          ...f,
          candidate: scenario.candidates.find((c) => c.id === f.candidate_id),
        }))
        .filter((f) => f.candidate),
    [scenario, run, stage, frame],
  );
  const selectedPrediction = run.forecasts.find(
    (f) => f.candidate_id === focusedCandidate,
  );
  const selectedPath = selectedPrediction?.paths?.[0]?.nodes || [];
  const pathPairs = new Set(
    selectedPath
      .slice(1)
      .map((id, i) => [selectedPath[i], id].sort().join("|")),
  );
  const graphNodes = useMemo(() => {
    const all = new Map(scenario.nodes.map((n) => [n.id, n]));
    scenario.claims.forEach((c) =>
      c.contexts?.forEach((ctx) => {
        if (ctx.disease) {
          const id = `context:disease:${ctx.disease_id || ctx.disease}`;
          all.set(id, { id, label: ctx.disease, type: "disease" });
        }
      }),
    );
    return [...all.values()];
  }, [scenario]);
  const graphClaims = useMemo(() => {
    const edges = [...acquiredClaims];
    const seen = new Set<string>();
    acquiredClaims.forEach((c) =>
      c.contexts?.forEach((ctx) => {
        if (!ctx.disease || nodes.get(c.source)?.type !== "variant") return;
        const target = `context:disease:${ctx.disease_id || ctx.disease}`;
        const id = `context:${c.source}:${target}`;
        if (seen.has(id)) return;
        seen.add(id);
        edges.push({
          id,
          source: c.source,
          target,
          relation: "evidence context",
          evidence_ids: ctx.evidence_id ? [ctx.evidence_id] : c.evidence_ids,
          contexts: [ctx],
        });
      }),
    );
    return edges;
  }, [acquiredClaims, nodes]);
  const displayNodes = useMemo(() => {
    const finalCandidates = run.forecasts
      .slice(0, 5)
      .map((f) => scenario.candidates.find((c) => c.id === f.candidate_id))
      .filter(Boolean);
    const priority = new Set(
      finalCandidates.flatMap((c) => [c!.source, c!.target]),
    );
    run.forecasts
      .slice(0, 5)
      .forEach((f) =>
        f.paths?.forEach((p) => p.nodes.forEach((id) => priority.add(id))),
      );
    const adjacent = scenario.claims.filter(
      (c) => priority.has(c.source) || priority.has(c.target),
    );
    adjacent.forEach((c) => {
      priority.add(c.source);
      priority.add(c.target);
      c.contexts?.forEach((ctx) => {
        if (ctx.disease)
          priority.add(`context:disease:${ctx.disease_id || ctx.disease}`);
      });
    });
    const focusNodes = new Set(
      selectedPrediction?.paths?.flatMap((p) => p.nodes) || [],
    );
    const focusCandidate = scenario.candidates.find(
      (c) => c.id === focusedCandidate,
    );
    if (focusCandidate) {
      focusNodes.add(focusCandidate.source);
      focusNodes.add(focusCandidate.target);
    }
    const ordered = [
      ...graphNodes.filter((n) => focusNodes.has(n.id)),
      ...graphNodes.filter((n) => priority.has(n.id) && !focusNodes.has(n.id)),
      ...graphNodes.filter((n) => !priority.has(n.id) && !focusNodes.has(n.id)),
    ];
    const counts: Record<string, number> = {};
    return ordered
      .filter((n) => {
        const t = n.type;
        counts[t] = (counts[t] || 0) + 1;
        return counts[t] <= 6;
      })
      .slice(0, 24);
  }, [graphNodes, scenario, run, focusedCandidate, selectedPrediction]);
  const positions = useMemo(() => {
    const byType: Record<string, ForecastNode[]> = {};
    displayNodes.forEach((n) => {
      const type = n.type === "therapy_group" ? "therapy" : n.type;
      (byType[type] ??= []).push(n);
    });
    const order = [
      "gene",
      "variant",
      "disease",
      "therapy",
      ...Object.keys(byType).filter(
        (t) => !["gene", "variant", "disease", "therapy"].includes(t),
      ),
    ];
    const map = new Map<string, { x: number; y: number }>();
    order.forEach((t, i) => {
      const group = byType[t] || [];
      group.forEach((n, j) =>
        map.set(n.id, {
          x: 100 + i * 215,
          y: 85 + ((j + 0.5) * 280) / Math.max(group.length, 1),
        }),
      );
    });
    return map;
  }, [displayNodes]);
  const displayedClaims = graphClaims.filter(
    (c) => positions.has(c.source) && positions.has(c.target),
  );
  const visibleClaims =
    illustrative && stage === 0 ? displayedClaims.slice(0, 5) : displayedClaims;
  const selectedNode =
    graphNodes.find((n) => n.id === selected) || nodes.get(selected);
  const selectedClaims = graphClaims.filter(
    (c) => c.source === selected || c.target === selected,
  );
  const evidenceIds = new Set(selectedClaims.flatMap((c) => c.evidence_ids));

  if (selectedPrediction)
    selectedPrediction.evidence_ids?.forEach((id) => evidenceIds.add(id));
  const pathEvidenceIds = selectedPrediction
    ? new Set(
        selectedPrediction.paths?.[0]?.evidence_ids ||
          selectedPrediction.evidence_ids ||
          [],
      )
    : evidenceIds;
  const evidence = selected
    ? scenario.evidence.filter(
        (e) => pathEvidenceIds.has(e.id) && acquiredIds.has(e.id),
      )
    : scenario.evidence.filter((e) => acquiredIds.has(e.id)).slice(-3);
  const recordedEvents = run.events.filter(
    (e) => e.type === "graph_updated" || e.type === "branches_selected",
  );
  const selectedCandidate =
    (focusedCandidate ? { candidate_id: focusedCandidate } : undefined) ||
    predictions.find(
      (p) =>
        p.candidate!.source === selected || p.candidate!.target === selected,
    );
  const outcome = selectedCandidate
    ? packet.outcomes.find(
        (o) => o.candidate_id === selectedCandidate.candidate_id,
      )
    : undefined;
  const futureSources =
    stage === 4 && outcome
      ? packet.future_evidence.filter((e) =>
          outcome.evidence_ids.includes(e.id),
        )
      : [];
  const jump = (n: number) => {
    setPlaying(false);
    setStage(n);
    if (n < 3) {
      setSelected("");
      setFocusedCandidate("");
    }
  };
  const activeNode = (n: ForecastNode) =>
    !query || n.label.toLowerCase().includes(query.toLowerCase());
  const models = packet.report?.models as
    | Record<
        string,
        {
          overall: {
            average_precision: number | null;
            auroc: number | null;
            at_k: Record<
              string,
              {
                precision: number | null;
                hits: number;
                k: number;
                selected: number;
                selected_count?: number;
              }
            >;
          };
          metadata?: Record<string, unknown>;
        }
      >
    | undefined;
  const firstObserved =
    stage === 4
      ? run.forecasts.find((f) =>
          packet.outcomes.some(
            (o) => o.candidate_id === f.candidate_id && o.observed,
          ),
        )
      : undefined;
  const scoreRows = Object.entries(models || {}).map(([id, value]) => ({
    id,
    ...value,
  }));
  const selectionEvent =
    run.events.find(
      (e) =>
        e.type === "branches_selected" && e.revision === (frame?.revision || 1),
    ) || run.events.find((e) => e.type === "branches_selected");
  const choices = (selectionEvent?.payload.choices || []) as {
    id: string;
    marginal_gain: number;
    new_facets: string[];
  }[];
  const revisionNumber = frame?.revision ?? Math.min(stage, 2);
  return (
    <section
      className="forecast-workspace"
      aria-label="Scientific forecasting workspace"
    >
      <div className="forecast-heading">
        <div>
          <div className="forecast-eyebrow">
            <span className="forecast-pulse" /> SCIENTIFIC FRONTIERS{" "}
            <span>/ BIOLOGY</span>
          </div>
          <h1>See the next connection.</h1>
          <p>{scenario.title}</p>
        </div>
        <div className="forecast-heading-actions">
          {!illustrative && (
            <button
              className="forecast-memory-jump"
              onClick={() =>
                document
                  .getElementById("forecast-model-memory")
                  ?.scrollIntoView({
                    behavior: window.matchMedia(
                      "(prefers-reduced-motion: reduce)",
                    ).matches
                      ? "instant"
                      : "smooth",
                    block: "start",
                  })
              }
            >
              Model memory <ArrowRight size={13} />
            </button>
          )}
          <label className="sr-only" htmlFor="forecast-provider">
            Run provider
          </label>
          <select
            id="forecast-provider"
            value={provider}
            onChange={(e) => {
              setProvider(e.target.value);
              jump(0);
            }}
          >
            <option value="auto">Historical run</option>
            <option value="illustrative">Illustrative walkthrough</option>
          </select>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Download replay artifact"
            onClick={() => download(packet)}
          >
            <Download size={17} />
          </Button>
        </div>
      </div>
      <div className="forecast-meta">
        <div className="forecast-period">
          <Clock3 size={14} />
          <span>
            Evidence available by <strong>{scenario.cutoff}</strong>
          </span>
          <ArrowRight size={13} />
          <span>
            Reveal <strong>{year(scenario.horizon)}</strong>
          </span>
        </div>
        <span
          className={`forecast-origin ${illustrative ? "is-illustrative" : ""}`}
        >
          {illustrative
            ? "Illustrative · no measured predictions"
            : "Computed · historical graph"}
        </span>
      </div>
      <div className="forecast-instrument">
        <div className="forecast-map">
          <div className="forecast-map-toolbar">
            <span>
              <NetworkMark /> EVIDENCE GRAPH{" "}
              <small>{visibleClaims.length} visible connections</small>
            </span>
            <div className="forecast-search">
              <Search size={14} />
              <input
                aria-label="Find a graph entity"
                placeholder="Find an entity"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
          </div>
          <div className="forecast-graph-scene">
            <svg
              viewBox="0 0 900 440"
              role="group"
              aria-label="Scientific evidence graph with genes, variants, disease context, and therapy groups"
            >
              <defs>
                <pattern
                  id="forecast-grid"
                  width="24"
                  height="24"
                  patternUnits="userSpaceOnUse"
                >
                  <circle
                    cx="1"
                    cy="1"
                    r="0.65"
                    fill="var(--grid)"
                    opacity="0.5"
                  />
                </pattern>
              </defs>
              <rect width="900" height="540" fill="url(#forecast-grid)" />
              {["gene", "variant", "disease", "therapy"].map((t, i) => (
                <text
                  className="forecast-column-label"
                  key={t}
                  x={100 + i * 215}
                  y={39}
                  textAnchor="middle"
                >
                  {typeLabels[t]?.toUpperCase()}
                </text>
              ))}
              {visibleClaims.map((c, i) => {
                const a = positions.get(c.source)!,
                  b = positions.get(c.target)!;
                const related =
                  !selected ||
                  c.source === selected ||
                  c.target === selected ||
                  pathPairs.has([c.source, c.target].sort().join("|"));
                return (
                  <path
                    key={c.id}
                    className={`forecast-edge ${pathPairs.has([c.source, c.target].sort().join("|")) ? "is-path" : ""} ${related ? "" : "is-muted"} ${i >= 5 ? "is-added" : ""}`}
                    style={{ animationDelay: `${Math.min(i, 20) * 30}ms` }}
                    d={`M${a.x} ${a.y} C${(a.x + b.x) / 2} ${a.y},${(a.x + b.x) / 2} ${b.y},${b.x} ${b.y}`}
                  />
                );
              })}
              {stage >= 3 &&
                (focusedCandidate
                  ? run.forecasts
                      .filter((f) => f.candidate_id === focusedCandidate)
                      .map((f) => ({
                        ...f,
                        candidate: scenario.candidates.find(
                          (c) => c.id === f.candidate_id,
                        ),
                      }))
                  : predictions.slice(0, 3)
                ).map((p) => {
                  const a = positions.get(p.candidate!.source),
                    b = positions.get(p.candidate!.target);
                  if (!a || !b) return null;
                  const observed = packet.outcomes.find(
                    (o) => o.candidate_id === p.candidate_id,
                  )?.observed;
                  return (
                    <path
                      key={p.candidate_id}
                      className={`forecast-prediction-edge ${stage === 4 && observed ? "is-matched" : ""} ${stage === 4 && !observed ? "is-unobserved" : ""}`}
                      d={`M${a.x} ${a.y} Q${(a.x + b.x) / 2} ${Math.min(425, Math.max(a.y, b.y) + 70)},${b.x} ${b.y}`}
                    />
                  );
                })}
              {displayNodes.map((n) => {
                const pos = positions.get(n.id)!;
                const isSelected = selected === n.id;
                return (
                  <g
                    key={n.id}
                    className={`forecast-node type-${n.type} ${isSelected ? "is-selected" : ""} ${activeNode(n) ? "" : "is-filtered"}`}
                    transform={`translate(${pos.x},${pos.y})`}
                    role="button"
                    tabIndex={0}
                    aria-label={`Inspect ${n.label}`}
                    onClick={() => {
                      setSelected(isSelected ? "" : n.id);
                      setFocusedCandidate("");
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelected(isSelected ? "" : n.id);
                        setFocusedCandidate("");
                      }
                    }}
                  >
                    <title>{n.label}</title>
                    <circle className="forecast-node-halo" r="24" />
                    <circle
                      r={n.type === "gene" ? 13 : n.type === "variant" ? 9 : 6}
                    />
                    <text y="33" textAnchor="middle">
                      {short(n.label, n.type === "therapy" ? 21 : 24)}
                    </text>
                  </g>
                );
              })}
            </svg>
            {stage === 2 && (
              <div className="forecast-branch-callout">
                <GitBranch size={17} />
                <div>
                  <strong>Cover what the first branch missed.</strong>
                  <span>
                    {illustrative
                      ? "Illustrative branch allocation"
                      : `${run.policy} · evidence overlap is counted once`}
                  </span>
                </div>
              </div>
            )}
          </div>
          <div className="forecast-map-footer">
            <div className="forecast-legend">
              <span>
                <i /> Source-backed connection
              </span>
              <span>
                <i className="is-dashed" /> Forecast
              </span>
              {stage === 4 && (
                <span>
                  <i className="is-match" /> Later evidence
                </span>
              )}
            </div>
            <button
              aria-label="Clear graph selection"
              onClick={() => {
                setSelected("");
                setFocusedCandidate("");
                setQuery("");
              }}
            >
              <Maximize2 size={15} /> Reset view
            </button>
          </div>
        </div>
        <aside
          ref={inspector}
          className="forecast-inspector"
          aria-label="Evidence and recommendations"
        >
          <div className="forecast-inspector-heading">
            <span>
              {selectedNode ? "SELECTED ENTITY" : "RESEARCH NOTEBOOK"}
            </span>
            {selectedNode && (
              <button
                onClick={() => {
                  setSelected("");
                  setFocusedCandidate("");
                }}
                aria-label="Clear selected entity"
              >
                ×
              </button>
            )}
          </div>
          <h2>{selectedNode?.label || stages[stage].title}</h2>
          <p className="forecast-inspector-copy">
            {selectedPrediction
              ? selectedPrediction.reason
              : selectedNode
                ? `${typeLabels[selectedNode.type] || selectedNode.type} · ${selectedClaims.length} source-linked connections`
                : stages[stage].copy}
          </p>
          {selectedPrediction && (
            <p className="forecast-prediction-context">
              Association forecast · no treatment-effect direction is predicted.
              Saved rank {selectedPrediction.rank ?? "—"}.
            </p>
          )}
          {selectedPrediction?.paths && (
            <div className="forecast-paths">
              <div className="forecast-section-label">WHY THIS CONNECTION</div>
              {selectedPrediction.paths.slice(0, 2).map((p, i) => (
                <p key={i}>{p.labels.join(" → ")}</p>
              ))}
            </div>
          )}
          {futureSources.length > 0 && (
            <div className="forecast-future-sources">
              <div className="forecast-section-label">LATER EVIDENCE</div>
              {futureSources.slice(0, 2).map((e) => (
                <article key={e.id}>
                  <strong>{e.title}</strong>
                  <small>
                    Added to CIViC by {e.available_at || scenario.horizon}
                    {e.publication_year
                      ? ` · paper published ${e.publication_year}`
                      : ""}
                  </small>
                  <p>{e.text}</p>
                  {e.url && (
                    <a href={e.url} target="_blank" rel="noreferrer">
                      Read later source <ExternalLink size={12} />
                    </a>
                  )}
                </article>
              ))}
            </div>
          )}
          {stage >= 3 && !selectedNode ? (
            <div className="forecast-recommendations">
              <div className="forecast-section-label">
                <LockKeyhole size={13} /> COMMITTED RECOMMENDATIONS
              </div>
              {predictions.map((p, i) => {
                const c = p.candidate!;
                const result = packet.outcomes.find(
                  (o) => o.candidate_id === p.candidate_id,
                );
                return (
                  <button
                    key={p.candidate_id}
                    className="forecast-recommendation"
                    onClick={() => {
                      setSelected(c.source);
                      setFocusedCandidate(p.candidate_id);
                    }}
                  >
                    <span className="forecast-rank">0{i + 1}</span>
                    <div>
                      <strong>{nodes.get(c.source)?.label || c.source}</strong>
                      <span>
                        <ArrowRight size={12} />
                        {nodes.get(c.target)?.label || c.target}
                      </span>
                      {stage === 4 && (
                        <small
                          className={
                            result?.observed ? "forecast-hit" : "forecast-miss"
                          }
                        >
                          {result?.observed ? (
                            <>
                              <Check size={12} /> Found in later evidence
                            </>
                          ) : (
                            "Unobserved by horizon"
                          )}
                        </small>
                      )}
                    </div>
                    <ChevronRight size={14} />
                  </button>
                );
              })}
              {stage === 4 &&
                !illustrative &&
                firstObserved &&
                !predictions.some(
                  (p) => p.candidate_id === firstObserved.candidate_id,
                ) && (
                  <button
                    className="forecast-later-match"
                    onClick={() => {
                      const c = scenario.candidates.find(
                        (c) => c.id === firstObserved.candidate_id,
                      );
                      if (c) {
                        setSelected(c.source);
                        setFocusedCandidate(c.id);
                      }
                    }}
                  >
                    <span>FIRST LATER MATCH</span>
                    <strong>Inspect saved rank {firstObserved.rank}</strong>
                    <small>
                      Selected after reveal · original ranking preserved
                    </small>
                    <ArrowRight size={14} />
                  </button>
                )}
            </div>
          ) : (
            <div className="forecast-source-list">
              <div className="forecast-section-label">
                {selectedPrediction
                  ? "SELECTED PATH EVIDENCE"
                  : selectedNode
                    ? "SUPPORTING EVIDENCE"
                    : "EVIDENCE IN VIEW"}
              </div>
              {evidence.slice(0, 3).map((e, i) => (
                <article className="forecast-source" key={e.id}>
                  <span className="forecast-source-number">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <h3>{e.title}</h3>
                    <p>{e.text}</p>
                    {e.url && (
                      <a href={e.url} target="_blank" rel="noreferrer">
                        Open source <ExternalLink size={11} />
                      </a>
                    )}
                  </div>
                </article>
              ))}
              {selectedNode && evidence.length === 0 && (
                <p className="forecast-inspector-copy">
                  Select a connected entity to inspect the supporting evidence.
                </p>
              )}
            </div>
          )}
          {stage === 2 &&
            !illustrative &&
            !selectedNode &&
            choices.length > 0 && (
              <div className="forecast-selection-detail">
                <div className="forecast-section-label">
                  THE ALLOCATION DECISION
                </div>
                <p>
                  <strong>
                    {Number(selectionEvent?.payload.value || 0).toFixed(1)}
                  </strong>{" "}
                  weighted evidence coverage
                </p>
                <p>
                  <strong>
                    {(
                      Number(selectionEvent?.payload.certificate_ratio || 0) *
                      100
                    ).toFixed(1)}
                    %
                  </strong>{" "}
                  certified fraction of the upper bound
                </p>
                <small>
                  This certifies the declared coverage objective, not forecast
                  accuracy.
                </small>
                <details>
                  <summary>Inspect selected evidence</summary>
                  {choices.map((c) => (
                    <div key={c.id}>
                      <span>
                        {scenario.evidence.find((e) => e.id === c.id)?.title ||
                          c.id}
                      </span>
                      <b>+{c.marginal_gain.toFixed(2)}</b>
                    </div>
                  ))}
                </details>
              </div>
            )}
          <div className="forecast-inspector-foot">
            <span className="forecast-pulse" />
            <span>{connection}</span>
          </div>
        </aside>
      </div>
      <div className="forecast-playback">
        <button
          className="forecast-play"
          aria-label={playing ? "Pause sequence" : "Play sequence"}
          onClick={() => {
            if (stage === 4) {
              setStage(0);
              setSelected("");
              setFocusedCandidate("");
            }
            setPlaying(!playing);
          }}
        >
          {playing ? <Pause size={18} /> : <Play size={18} />}
        </button>
        <div className="forecast-stages">
          {stages.map((s, i) => (
            <button
              key={s.label}
              onClick={() => jump(i)}
              className={
                i === stage ? "is-current" : i < stage ? "is-past" : ""
              }
              aria-current={i === stage ? "step" : undefined}
            >
              <span>
                {i < stage ? (
                  <Check size={12} />
                ) : (
                  String(i + 1).padStart(2, "0")
                )}
              </span>
              <strong>{s.label}</strong>
            </button>
          ))}
        </div>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Restart sequence"
          onClick={() => {
            jump(0);
            setSelected("");
            setFocusedCandidate("");
          }}
        >
          <RotateCcw size={16} />
        </Button>
        <Button
          variant="default"
          className="forecast-next"
          onClick={() => jump(Math.min(stage + 1, 4))}
          disabled={stage === 4}
        >
          {stage === 3 ? "Reveal evidence" : "Continue"}
          <ArrowRight size={15} />
        </Button>
      </div>
      <div className="forecast-bottom">
        <div>
          <Sparkles size={15} />
          <span>
            {illustrative
              ? "Explore the interaction now. Historical data and measured comparisons are being connected."
              : `${scenario.dataset} · ${run.model} · ${run.policy}`}
          </span>
        </div>
        <span>
          Graph revision {revisionNumber}{" "}
          <span className="forecast-bottom-dot">/</span> Historical cutoff stays
          fixed
        </span>
      </div>
      {!illustrative && stage === 4 && (
        <section className="forecast-results">
          <div>
            <span className="forecast-eyebrow">THE BACKTEST</span>
            <h2>Every recommendation meets the same future.</h2>
            <p>
              This replay predicts later CIViC curation of older papers, not
              newly published discoveries. Greedy optimizes evidence coverage;
              this first run does not beat uniform selection on forecasting. The
              full historical graph uses a larger evidence budget.
            </p>
          </div>
          {scoreRows.length > 0 ? (
            <div className="forecast-score-rows">
              {scoreRows.map((row, i) => (
                <div key={i}>
                  <strong>{row.id.replaceAll("_", " ")}</strong>
                  <span>
                    {row.overall.average_precision === null
                      ? "Not measured"
                      : row.overall.average_precision.toFixed(4)}
                  </span>
                  <small>
                    Average precision · precision@5{" "}
                    {row.overall.at_k["5"]?.precision == null
                      ? "—"
                      : `${(row.overall.at_k["5"].precision! * 100).toFixed(0)}%`}
                  </small>
                </div>
              ))}
            </div>
          ) : (
            <p className="forecast-inspector-copy">
              Detailed comparisons are being assembled from the saved prediction
              records.
            </p>
          )}
        </section>
      )}
      {!illustrative && (
        <ForecastReasoning scenario={scenario} revealed={stage === 4} />
      )}
      {recordedEvents.length > 0 && (
        <details className="forecast-run-details">
          <summary>
            Inspect the recorded graph revisions and selection decisions
          </summary>
          {recordedEvents.map((e) => (
            <article key={e.seq}>
              <strong>{e.title}</strong>
              <p>{e.description}</p>
            </article>
          ))}
        </details>
      )}
    </section>
  );
}
function NetworkMark() {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
    >
      <path d="M3 4l9 1-5 8L3 4z" stroke="currentColor" />
      <circle cx="3" cy="4" r="2" fill="currentColor" />
      <circle cx="12" cy="5" r="2" fill="currentColor" />
      <circle cx="7" cy="13" r="2" fill="currentColor" />
    </svg>
  );
}
