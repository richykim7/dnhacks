import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  ExternalLink,
  GitBranch,
  LockKeyhole,
} from "lucide-react";
import type {
  ForecastCandidate,
  ForecastClaim,
  ForecastScenario,
} from "../lib/forecasting";
import "../reasoning.css";

type ConditionId = "flat_log" | "static_graph" | "evolving_graph";
interface Hypothesis {
  candidate_id: string;
  stance: string;
  rationale: string;
  evidence_ids: string[];
  status: string;
}
interface Revision {
  step: number;
  status: string;
  visible_evidence_ids: string[];
  new_evidence_ids: string[];
  hypotheses: Hypothesis[];
  forecasts: { candidate_id: string; score: number }[];
  graph: { source_claims: ForecastClaim[]; hypotheses: Hypothesis[] } | null;
  graph_revision: {
    source_claim_ids_added: string[];
    hypotheses_upserted: Hypothesis[];
    hypothesis_candidate_ids_removed: string[];
  };
  usage: {
    output_tokens?: number;
    input_tokens?: number;
    cache_creation_input_tokens?: number;
    cache_read_input_tokens?: number;
  }[];
  diagnostics: string[];
}
interface ReasoningComparison {
  scenario_id: string;
  origin: string;
  comparison_ready: boolean;
  candidates: ForecastCandidate[];
  provenance: { model: string };
  protocol: {
    evidence_batches: string[][];
    budget: { calls_per_condition: number; max_output_tokens_per_call: number };
  };
  conditions: Record<ConditionId, { status: string; events: Revision[] }>;
}
interface Evaluation {
  models: Record<
    string,
    {
      overall: {
        average_precision: number | null;
        auroc: number | null;
        observed_count: number;
        candidate_count: number;
        at_k: Record<
          string,
          { precision: number; hits: number; selected_count: number }
        >;
      };
    }
  >;
}
interface ReasoningPacket {
  status: string;
  comparison: ReasoningComparison | null;
  evaluation: Evaluation | null;
}

const modes: { id: ConditionId; label: string; copy: string }[] = [
  {
    id: "flat_log",
    label: "Flat log",
    copy: "Source evidence and working hypotheses are read as text.",
  },
  {
    id: "static_graph",
    label: "Static graph",
    copy: "The source graph stays fixed. New evidence and proposals enter the log.",
  },
  {
    id: "evolving_graph",
    label: "Evolving graph",
    copy: "Cited proposals become graph memory for the next model call.",
  },
];
const shorten = (value: string, max = 23) =>
  value.length > max ? `${value.slice(0, max - 1)}…` : value;
const number = (value: number) => value.toLocaleString("en-US");

function MemoryMap({
  scenario,
  comparison,
  revision,
  hypothesis,
  condition,
}: {
  scenario: ForecastScenario;
  comparison: ReasoningComparison;
  revision: Revision;
  hypothesis?: Hypothesis;
  condition: ConditionId;
}) {
  const nodes = new Map(scenario.nodes.map((node) => [node.id, node]));
  const candidate = comparison.candidates.find(
    (row) => row.id === hypothesis?.candidate_id,
  );
  const source = comparison.candidates[0]?.source;
  const union = new Map<string, ForecastClaim>();
  Object.values(comparison.conditions).forEach((run) =>
    run.events.forEach((event) =>
      event.graph?.source_claims.forEach((claim) => union.set(claim.id, claim)),
    ),
  );
  // The source neighborhood is laid out once from the recorded union, so advancing
  // a revision changes edges and emphasis without moving existing source nodes.
  const neighbors = [
    ...new Set(
      [...union.values()].flatMap((claim) => [claim.source, claim.target]),
    ),
  ]
    .filter((id) => id !== source)
    .sort()
    .slice(0, 8);
  const positions = new Map<string, { x: number; y: number }>();
  if (source) positions.set(source, { x: 345, y: 156 });
  neighbors.forEach((id, index) =>
    positions.set(id, {
      x: 157,
      y: 42 + (index * 228) / Math.max(1, neighbors.length - 1),
    }),
  );
  const claims = revision.graph?.source_claims || [];
  const active = new Set(
    claims.flatMap((claim) => [claim.source, claim.target]),
  );
  const cited = new Set(hypothesis?.evidence_ids || []);
  return (
    <svg
      className="reasoning-map"
      viewBox="0 0 650 322"
      role="img"
      aria-label={`Historical source graph with ${claims.length} source connections and ${hypothesis ? "one selected unverified proposal" : "no selected proposal"}`}
    >
      <text x="24" y="17" className="reasoning-map-label">
        SOURCE NEIGHBORHOOD
      </text>
      <text x="488" y="17" className="reasoning-map-label">
        SELECTED PROPOSAL
      </text>
      {claims.map((claim) => {
        const a = positions.get(claim.source),
          b = positions.get(claim.target);
        if (!a || !b) return null;
        return (
          <path
            key={claim.id}
            d={`M ${a.x} ${a.y} C 245 ${a.y}, 245 ${b.y}, ${b.x} ${b.y}`}
            className={`reasoning-source-edge ${claim.evidence_ids.some((id) => cited.has(id)) ? "is-cited" : ""}`}
          />
        );
      })}
      {[...positions].map(([id, position]) => (
        <g
          key={id}
          transform={`translate(${position.x} ${position.y})`}
          className={`reasoning-map-node ${id === source ? "is-query" : ""} ${active.has(id) || id === source ? "" : "is-dormant"}`}
        >
          <title>{nodes.get(id)?.label || id}</title>
          <circle r={id === source ? 9 : 5} />
          <text
            x={id === source ? 0 : -13}
            y={id === source ? 29 : 4}
            textAnchor={id === source ? "middle" : "end"}
          >
            {shorten(nodes.get(id)?.label || id, id === source ? 28 : 23)}
          </text>
        </g>
      ))}
      {candidate && hypothesis && (
        <g className="reasoning-proposal-graphic" key={candidate.id}>
          <path
            d="M 356 156 C 415 123, 484 123, 542 156"
            className="reasoning-proposal-edge"
          />
          <circle cx="552" cy="156" r="8" />
          <text x="552" y="185" textAnchor="middle">
            {shorten(
              nodes.get(candidate.target)?.label || candidate.target,
              24,
            )}
          </text>
          <text
            x="451"
            y="116"
            textAnchor="middle"
            className="reasoning-proposal-caption"
          >
            {condition === "evolving_graph"
              ? "unverified hypothesis"
              : "proposal in log"}
          </text>
          <title>{hypothesis.rationale}</title>
        </g>
      )}
      <text x="24" y="308" className="reasoning-map-label">
        SOLID · SOURCED ASSOCIATION
      </text>
      <text x="399" y="308" className="reasoning-map-label">
        DASHED · MODEL PROPOSAL
      </text>
    </svg>
  );
}

export function ForecastReasoning({
  scenario,
  revealed,
}: {
  scenario: ForecastScenario;
  revealed: boolean;
}) {
  const [packet, setPacket] = useState<ReasoningPacket | null>(null);
  const [loadState, setLoadState] = useState("Loading recorded comparison…");
  const [condition, setCondition] = useState<ConditionId>("evolving_graph");
  const [step, setStep] = useState(0);
  const [selected, setSelected] = useState("");
  useEffect(() => {
    const abort = new AbortController();
    setPacket(null);
    setStep(0);
    setSelected("");
    setLoadState("Loading recorded comparison…");
    const load = async () => {
      try {
        const response = await fetch("/api/forecasting/reasoning", {
          signal: abort.signal,
        });
        if (!response.ok) throw new Error("unavailable");
        const value: ReasoningPacket = await response.json();
        if (value.comparison?.scenario_id !== scenario.id) {
          setLoadState("No recorded model comparison for this scenario.");
          return;
        }
        setPacket(value);
        setLoadState("");
      } catch {
        if (!abort.signal.aborted)
          setLoadState("Recorded comparison unavailable. Reconnecting…");
      }
    };
    void load();
    const timer = window.setInterval(load, 10000);
    return () => {
      abort.abort();
      window.clearInterval(timer);
    };
  }, [scenario.id]);
  const comparison = packet?.comparison;
  const run = comparison?.conditions[condition];
  const revision = run?.events[Math.min(step, run.events.length - 1)];
  const hypotheses = useMemo(() => {
    const visible = new Set(revision?.visible_evidence_ids || []);
    return (revision?.hypotheses || []).filter(
      (row) =>
        row.evidence_ids.length > 0 &&
        row.evidence_ids.every((id) => visible.has(id)),
    );
  }, [revision]);
  useEffect(() => {
    setSelected((value) =>
      hypotheses.some((row) => row.candidate_id === value)
        ? value
        : hypotheses[0]?.candidate_id || "",
    );
  }, [hypotheses]);
  const hypothesis =
    hypotheses.find((row) => row.candidate_id === selected) || hypotheses[0];
  const candidate = comparison?.candidates.find(
    (row) => row.id === hypothesis?.candidate_id,
  );
  const labels = new Map(scenario.nodes.map((node) => [node.id, node.label]));
  const evidence = new Map(scenario.evidence.map((row) => [row.id, row]));
  const title = (id: string) => {
    const row = comparison?.candidates.find((item) => item.id === id);
    return row ? labels.get(row.target) || row.target : "Unknown candidate";
  };
  if (!comparison || !revision || !run)
    return (
      <section
        id="forecast-model-memory"
        className="reasoning-panel reasoning-pending"
        aria-label="Model memory comparison"
      >
        <GitBranch size={16} />
        <div>
          <strong>Model memory comparison</strong>
          <p role="status">{loadState}</p>
        </div>
      </section>
    );
  const mode = modes.find((item) => item.id === condition)!;
  const usage = run.events.flatMap((event) => event.usage || []);
  const outputTokens = usage.reduce(
    (total, row) => total + (row.output_tokens || 0),
    0,
  );
  const inputTokens = usage.reduce(
    (total, row) =>
      total +
      (row.input_tokens || 0) +
      (row.cache_creation_input_tokens || 0) +
      (row.cache_read_input_tokens || 0),
    0,
  );
  const sourceCount = new Set(comparison.protocol.evidence_batches.flat()).size;
  const graphHypotheses = revision.graph?.hypotheses || [];
  const citationCount = new Set(hypotheses.flatMap((row) => row.evidence_ids))
    .size;
  const metric = packet?.evaluation?.models[condition]?.overall;
  const delta = revision.graph_revision;
  return (
    <section
      id="forecast-model-memory"
      className="reasoning-panel"
      aria-labelledby="reasoning-title"
    >
      <header className="reasoning-heading">
        <div>
          <span className="reasoning-eyebrow">
            <GitBranch size={12} /> MODEL MEMORY
          </span>
          <h2 id="reasoning-title">The map becomes the next prompt.</h2>
          <p>Same evidence. Three ways to carry a hypothesis forward.</p>
        </div>
        <span
          className={`reasoning-origin ${comparison.origin === "illustrative" ? "is-illustrative" : ""}`}
        >
          {comparison.origin === "model"
            ? "Recorded model run"
            : "Illustrative replay"}
        </span>
      </header>
      <div
        className="reasoning-tabs"
        role="tablist"
        aria-label="Model memory representation"
      >
        {modes.map((item, index) => (
          <button
            key={item.id}
            id={`reasoning-tab-${item.id}`}
            role="tab"
            aria-selected={condition === item.id}
            aria-controls="reasoning-memory-view"
            tabIndex={condition === item.id ? 0 : -1}
            onClick={() => setCondition(item.id)}
            onKeyDown={(event) => {
              if (event.key !== "ArrowLeft" && event.key !== "ArrowRight")
                return;
              event.preventDefault();
              const next =
                (index + (event.key === "ArrowRight" ? 1 : 2)) % modes.length;
              setCondition(modes[next].id);
              (
                event.currentTarget.parentElement?.children[next] as
                  HTMLButtonElement | undefined
              )?.focus();
            }}
          >
            <span>0{index + 1}</span>
            {item.label}
          </button>
        ))}
      </div>
      <div
        id="reasoning-memory-view"
        role="tabpanel"
        aria-labelledby={`reasoning-tab-${condition}`}
      >
        <div className="reasoning-memory-caption">
          <p>{mode.copy}</p>
          <span>{revision.visible_evidence_ids.length} sources in view</span>
        </div>
        <div className="reasoning-body">
          <div className="reasoning-scene">
            {condition === "flat_log" ? (
              <div
                className="reasoning-text-log"
                aria-label="Evidence in flat text memory"
              >
                <div className="reasoning-log-label">
                  <BookOpen size={12} /> APPENDED SOURCE RECORDS
                </div>
                {revision.visible_evidence_ids.map((id, index) => {
                  const source = evidence.get(id);
                  return (
                    <article key={id}>
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      <div>
                        <h3>{source?.title || "Source unavailable"}</h3>
                        <p>
                          {source?.text ||
                            "This citation is absent from the loaded scenario."}
                        </p>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <MemoryMap
                scenario={scenario}
                comparison={comparison}
                revision={revision}
                hypothesis={hypothesis}
                condition={condition}
              />
            )}
            <div className="reasoning-revision-summary" aria-live="polite">
              <span>
                <b>+{delta.hypotheses_upserted.length}</b> proposal updates
              </span>
              <span>
                <b>−{delta.hypothesis_candidate_ids_removed.length}</b> removed
              </span>
              <span>
                <b>{graphHypotheses.length}</b> in graph memory
              </span>
              <span>
                <b>{citationCount}</b> cited sources
              </span>
            </div>
            {revision.diagnostics.length > 0 && (
              <p className="reasoning-invalid" role="status">
                This attempt is incomplete. {revision.diagnostics.join(" ")}
              </p>
            )}
          </div>
          <aside
            className="reasoning-inspector"
            aria-label="Inspect a model hypothesis"
          >
            <div className="reasoning-inspector-label">
              WORKING HYPOTHESES <span>{hypotheses.length}</span>
            </div>
            <div className="reasoning-hypotheses">
              {hypotheses.map((row) => (
                <button
                  key={row.candidate_id}
                  type="button"
                  aria-pressed={hypothesis?.candidate_id === row.candidate_id}
                  onClick={() => setSelected(row.candidate_id)}
                  title={title(row.candidate_id)}
                >
                  <span>{shorten(title(row.candidate_id), 31)}</span>
                  <small>
                    {row.stance === "deprioritize"
                      ? "lower priority"
                      : row.stance === "prioritize"
                        ? "prioritize"
                        : "uncertain"}
                  </small>
                </button>
              ))}
            </div>
            {hypothesis && candidate ? (
              <div className="reasoning-hypothesis-detail">
                <span className="reasoning-proposal-label">
                  UNVERIFIED MODEL PROPOSAL
                </span>
                <h3>
                  {labels.get(candidate.source) || candidate.source}{" "}
                  <ArrowRight size={12} />{" "}
                  {labels.get(candidate.target) || candidate.target}
                </h3>
                <p className="reasoning-rationale">{hypothesis.rationale}</p>
                <div className="reasoning-citations">
                  {hypothesis.evidence_ids.map((id) => {
                    const source = evidence.get(id);
                    return (
                      <article key={id}>
                        {source?.url ? (
                          <a href={source.url} target="_blank" rel="noreferrer">
                            {source.title}
                            <ExternalLink size={11} />
                          </a>
                        ) : (
                          <span>
                            {source?.title ||
                              "Citation unavailable in this scenario"}
                          </span>
                        )}
                        {source && (
                          <details>
                            <summary>Read cited evidence</summary>
                            <p>{source.text}</p>
                          </details>
                        )}
                      </article>
                    );
                  })}
                </div>
              </div>
            ) : (
              <p className="reasoning-empty">
                No citation-valid hypotheses were saved in this revision.
              </p>
            )}
          </aside>
        </div>
        <div className="reasoning-stepbar">
          <span>RECORDED REVISIONS</span>
          <div>
            {run.events.map((event, index) => (
              <button
                key={event.step}
                type="button"
                aria-pressed={step === index}
                onClick={() => setStep(index)}
              >
                <b>0{event.step}</b>
                {index === 0 ? "Read & propose" : "Read & revise"}
                <small>+{event.new_evidence_ids.length} sources</small>
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="reasoning-outcomes">
        {!revealed ? (
          <p>
            <LockKeyhole size={12} /> Forecasts are saved. Outcome scores open
            with the future.
          </p>
        ) : metric ? (
          <>
            <span className="reasoning-outcome-label">
              LATER RECORD · {metric.observed_count}/{metric.candidate_count}{" "}
              OBSERVED
            </span>
            <div>
              <span>
                Average precision{" "}
                <b>
                  {metric.average_precision === null
                    ? "Unmeasurable"
                    : metric.average_precision.toFixed(3)}
                </b>
              </span>
              <span>
                AUROC{" "}
                <b>
                  {metric.auroc === null
                    ? "Unmeasurable"
                    : metric.auroc.toFixed(3)}
                </b>
              </span>
              {metric.at_k["5"] && (
                <span>
                  Top 5 observed{" "}
                  <b>
                    {metric.at_k["5"].hits}/{metric.at_k["5"].selected_count}
                  </b>
                </span>
              )}
            </div>
            {metric.observed_count === 0 && (
              <p>
                No later-observed associations in this selected query; it cannot
                establish ranking superiority.
              </p>
            )}
          </>
        ) : (
          <p>Outcome evaluation has not yet been recorded.</p>
        )}
      </div>
      <details className="reasoning-protocol">
        <summary>Comparison conditions & actual model use</summary>
        <p>
          {comparison.candidates.length} fixed candidates · {sourceCount}{" "}
          historical sources · {comparison.protocol.budget.calls_per_condition}{" "}
          calls per condition ·{" "}
          {number(comparison.protocol.budget.max_output_tokens_per_call)} output
          tokens requested as the per-call limit.
        </p>
        <p>
          {mode.label} consumed {number(inputTokens)} input tokens (including
          cache) and {number(outputTokens)} output tokens across the recorded
          calls. Requested limits match; actual usage can differ.
        </p>
        <p>
          Model: {comparison.provenance.model}. Modern training may include
          post-cutoff biology. Citation checks establish source availability,
          not scientific proof. Source associations and model hypotheses remain
          separate.
        </p>
        {loadState && (
          <p role="status">{loadState} Showing the last recorded packet.</p>
        )}
      </details>
    </section>
  );
}
