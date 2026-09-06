import { Check, Layers3, LockKeyhole } from "lucide-react";
import "../study.css";

interface QueryMetrics {
  macro: {
    query_count?: number;
    average_precision: number | null;
    average_precision_eligible_queries?: number;
    auroc: number | null;
    auroc_eligible_queries?: number;
    at_k: Record<
      string,
      { precision: number | null; precision_eligible_queries?: number }
    >;
  };
  overall: {
    candidate_count?: number;
    observed_count?: number;
    average_precision?: number | null;
    auroc?: number | null;
  };
}
interface StudyFailure {
  query_id: string;
  diagnostics?: unknown[];
  conditions: Record<
    string,
    { status: string | null; diagnostics?: unknown[] }
  >;
}
interface StudyUsage {
  attempted_calls: number;
  reported_calls: number;
  input_tokens: number;
  output_tokens: number;
  cache_creation_input_tokens: number;
  cache_read_input_tokens: number;
}
interface StudyBootstrap {
  confidence?: number;
  samples?: number;
  comparisons: Record<
    string,
    {
      eligible_queries: number;
      estimate: number | null;
      interval: [number, number] | null;
    }
  >;
}
export interface Study {
  status: "running" | "ready";
  planned_queries: number;
  saved_queries: number;
  planned_candidates: number;
  requested_output_tokens: number;
  audit?: {
    condition_validity: Record<
      string,
      { complete_queries: number; attempted_queries: number }
    >;
  };
  evaluation?: {
    coverage: {
      planned_queries: number;
      complete_queries: number;
      evaluated_candidates: number;
      planned_candidates: number;
      planned_observed: number;
      evaluated_observed: number;
      excluded_observed: number;
    };
    comparison: { models: Record<string, QueryMetrics> } | null;
    failures: StudyFailure[];
    usage: Record<string, StudyUsage>;
    bootstrap: StudyBootstrap | null;
  } | null;
}

const methods = [
  {
    id: "flat_log",
    label: "Flat log",
    detail: "Evidence and hypotheses in text",
  },
  {
    id: "static_graph",
    label: "Static graph",
    detail: "Initial graph with an appended log",
  },
  {
    id: "evolving_graph",
    label: "Evolving graph",
    detail: "Source graph and hypothesis memory",
  },
  {
    id: "popularity",
    label: "Historical popularity",
    detail: "Target degree; no model calls",
  },
];
const count = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value) && value >= 0;
const numeric = (value: number) => value.toLocaleString("en-US");
const metric = (value: number | null | undefined) =>
  typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(3)
    : "Unmeasurable";
const signed = (value: number) => `${value > 0 ? "+" : ""}${value.toFixed(3)}`;
const methodLabel = (id: string) =>
  methods.find((method) => method.id === id)?.label || id;
function diagnosticText(items: unknown[] = []): string[] {
  return items.flatMap((item) => {
    if (typeof item === "string") return [item];
    if (
      !item ||
      typeof item !== "object" ||
      !("errors" in item) ||
      !Array.isArray(item.errors)
    )
      return [];
    return item.errors.filter(
      (error): error is string => typeof error === "string",
    );
  });
}

export function ForecastStudy({
  study,
  revealed,
}: {
  study: Study | null;
  revealed: boolean;
}) {
  if (!study) return null;
  const evaluation = study.evaluation;
  const coverage = evaluation?.coverage;
  const models = evaluation?.comparison?.models;
  const failures = evaluation?.failures;
  const progressKnown =
    count(study.saved_queries) &&
    count(study.planned_queries) &&
    study.planned_queries > 0;
  const primary = models?.evolving_graph?.macro;
  const apQueries = primary?.average_precision_eligible_queries;
  const subset =
    coverage &&
    (coverage.complete_queries < coverage.planned_queries ||
      coverage.evaluated_candidates < coverage.planned_candidates);
  const bootstrap = evaluation?.bootstrap;
  return (
    <section
      id="forecast-study"
      className="forecast-study"
      aria-labelledby="study-title"
    >
      <header className="study-heading">
        <div>
          <span className="study-eyebrow">
            <Layers3 size={12} /> ACROSS THE COHORT
          </span>
          <h2 id="study-title">Put the same question to the whole field.</h2>
          <p>
            Historical queries and candidate sets were fixed before later
            records were opened.
          </p>
        </div>
        <span
          className={`study-status ${study.status === "running" ? "is-running" : ""}`}
        >
          {study.status === "running" ? (
            <i aria-hidden="true" />
          ) : (
            <Check size={11} />
          )}
          {study.status === "running" ? "Saving forecasts" : "Run recorded"}
        </span>
      </header>
      <div className="study-progress">
        <div className="study-progress-label" role="status" aria-live="polite">
          <span>
            {count(study.saved_queries) ? (
              <>
                <strong>{numeric(study.saved_queries)}</strong>
                {count(study.planned_queries)
                  ? ` / ${numeric(study.planned_queries)}`
                  : ""}{" "}
                query runs saved
              </>
            ) : (
              "Saved-query progress unavailable"
            )}
          </span>
          {count(study.planned_candidates) && (
            <span>{numeric(study.planned_candidates)} planned candidates</span>
          )}
        </div>
        {progressKnown && (
          <progress
            value={Math.min(study.saved_queries, study.planned_queries)}
            max={study.planned_queries}
            aria-label="Query runs saved"
          />
        )}
        <p>
          Saved runs include unsuccessful attempts. Scores use queries with
          complete rankings in every model condition.
        </p>
      </div>
      {failures && (
        <div className="study-failures">
          {failures.length > 0 ? (
            <details>
              <summary>
                <span>
                  {failures.length} query runs excluded by completion checks
                </span>
                <small>Inspect failures</small>
              </summary>
              <div className="study-failure-list">
                {failures.map((failure) => (
                  <article key={failure.query_id}>
                    <code>{failure.query_id}</code>
                    {diagnosticText(failure.diagnostics).map((error, index) => (
                      <p key={index}>{error}</p>
                    ))}
                    {Object.entries(failure.conditions).map(
                      ([id, condition]) => (
                        <div key={id}>
                          <strong>{methodLabel(id)}</strong>
                          <span>
                            {condition.status || "Status unavailable"}
                          </span>
                          {diagnosticText(condition.diagnostics).map(
                            (error, index) => (
                              <p key={index}>{error}</p>
                            ),
                          )}
                        </div>
                      ),
                    )}
                  </article>
                ))}
              </div>
            </details>
          ) : (
            <p>
              <Check size={12} /> No query runs excluded by completion checks.
            </p>
          )}
        </div>
      )}
      {!revealed ? (
        <div className="study-locked">
          <LockKeyhole size={14} />
          <div>
            <strong>The comparison opens with the future.</strong>
            <p>
              Forecast collection and completion checks remain visible while
              later outcomes stay closed.
            </p>
          </div>
        </div>
      ) : !evaluation ? (
        <div className="study-awaiting">
          <p>
            {study.status === "running"
              ? "Forecast collection is in progress. Scores appear after saved runs are evaluated."
              : "The run is recorded. Its outcome evaluation is not yet available."}
          </p>
        </div>
      ) : (
        <div className="study-results">
          {coverage && (
            <div className="study-coverage">
              <span className="study-section-label">
                {subset
                  ? "COMMON COMPLETE SUBSET"
                  : "COMPLETE HISTORICAL COHORT"}
              </span>
              <p>
                <strong>
                  {coverage.complete_queries}/{coverage.planned_queries}
                </strong>{" "}
                queries
                <span aria-hidden="true">·</span>
                <strong>
                  {coverage.evaluated_candidates}/{coverage.planned_candidates}
                </strong>{" "}
                candidates
                <span aria-hidden="true">·</span>
                <strong>
                  {coverage.evaluated_observed}/{coverage.planned_observed}
                </strong>{" "}
                later-observed associations
              </p>
              {subset && (
                <p className="study-subset-note">
                  These are conditional results for the completed subset.{" "}
                  {coverage.excluded_observed} later-observed associations are
                  excluded; this is not a score for the full cohort.
                </p>
              )}
            </div>
          )}
          {models ? (
            <>
              <div className="study-table-heading">
                <h3>Comparison across queries</h3>
                {count(apQueries) && (
                  <span className={apQueries < 2 ? "is-limited" : ""}>
                    AP eligible:{" "}
                    <strong>
                      {apQueries} {apQueries === 1 ? "query" : "queries"}
                    </strong>
                  </span>
                )}
              </div>
              <div className="study-table-scroll">
                <table className="study-table">
                  <caption>
                    Equal query weights; each metric reports its eligible query
                    count.
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Memory / baseline</th>
                      <th scope="col">Completed</th>
                      <th scope="col">Query-macro AP</th>
                      <th scope="col">Query-macro P@5</th>
                    </tr>
                  </thead>
                  <tbody>
                    {methods.map((method) => {
                      const row = models[method.id]?.macro;
                      const completed =
                        study.audit?.condition_validity[method.id];
                      const precision = row?.at_k["5"];
                      const eligibleAP =
                        row?.average_precision_eligible_queries;
                      const eligiblePrecision =
                        precision?.precision_eligible_queries;
                      return (
                        <tr
                          key={method.id}
                          className={
                            method.id === "popularity"
                              ? "study-baseline"
                              : undefined
                          }
                        >
                          <th scope="row">
                            <strong>{method.label}</strong>
                            <small>{method.detail}</small>
                          </th>
                          <td>
                            {completed
                              ? `${completed.complete_queries}/${completed.attempted_queries}`
                              : "—"}
                          </td>
                          <td>
                            <strong>
                              {row
                                ? metric(row.average_precision)
                                : "Unavailable"}
                            </strong>
                            {count(eligibleAP) && (
                              <small>
                                {eligibleAP} eligible{" "}
                                {eligibleAP === 1 ? "query" : "queries"}
                              </small>
                            )}
                          </td>
                          <td>
                            <strong>
                              {precision
                                ? metric(precision.precision)
                                : "Unavailable"}
                            </strong>
                            {count(eligiblePrecision) && (
                              <small>
                                {eligiblePrecision} eligible{" "}
                                {eligiblePrecision === 1 ? "query" : "queries"}
                              </small>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="study-metric-note">
                AP excludes queries without later-observed associations. P@5
                averages hits divided by the smaller of five or the query’s
                candidate count.
              </p>
              {count(apQueries) && apQueries < 2 && (
                <p className="study-limited-note">
                  {apQueries === 0
                    ? "No query has a measurable AP result."
                    : "Average precision rests on one eligible query."}{" "}
                  This run cannot establish general forecasting superiority.
                </p>
              )}
            </>
          ) : (
            <p className="study-awaiting">
              No common complete query set is available. Comparative scores are
              unavailable.
            </p>
          )}
          {bootstrap?.comparisons && (
            <details className="study-bootstrap">
              <summary>Paired differences and uncertainty</summary>
              <p>
                Recorded evolving-graph differences against each comparator.
                Query resampling is exploratory because queries share biological
                entities and sources.
              </p>
              {Object.entries(bootstrap.comparisons).map(([key, value]) => {
                const [pair, measure] = key.split("/");
                const baseline = pair.replace("evolving_graph-minus-", "");
                if (
                  !pair.startsWith("evolving_graph-minus-") ||
                  !["average_precision", "precision_at_5"].includes(measure)
                )
                  return null;
                return (
                  <div key={key} className="study-bootstrap-row">
                    <span>
                      Evolving − {methodLabel(baseline)}{" "}
                      <small>
                        {measure === "average_precision" ? "AP" : "P@5"}
                      </small>
                    </span>
                    <strong>
                      {value.estimate === null
                        ? "Unmeasurable"
                        : signed(value.estimate)}
                    </strong>
                    <p>
                      {value.eligible_queries < 2
                        ? `Informative interval not estimated: ${value.eligible_queries} eligible ${value.eligible_queries === 1 ? "query" : "queries"}.`
                        : value.interval
                          ? `${bootstrap.confidence ? `${Math.round(bootstrap.confidence * 100)}% ` : ""}interval ${signed(value.interval[0])} to ${signed(value.interval[1])} · ${value.eligible_queries} eligible queries`
                          : "Interval unavailable."}
                    </p>
                  </div>
                );
              })}
            </details>
          )}
        </div>
      )}
      <details className="study-protocol">
        <summary>Study allocation and recorded model use</summary>
        {count(study.requested_output_tokens) && (
          <p>
            Each model call requested a limit of{" "}
            {numeric(study.requested_output_tokens)} output tokens. Reported use
            can exceed this request; it is not a verified hard limit.
          </p>
        )}
        {revealed && evaluation?.usage && (
          <div className="study-usage">
            {methods
              .filter((method) => evaluation.usage[method.id])
              .map((method) => {
                const usage = evaluation.usage[method.id];
                return (
                  <p key={method.id}>
                    <strong>{method.label}</strong>
                    <span>
                      {usage.attempted_calls} attempted calls ·{" "}
                      {usage.reported_calls} reported calls ·{" "}
                      {numeric(usage.output_tokens)} output tokens
                    </span>
                  </p>
                );
              })}
          </div>
        )}
        <p>
          A later CIViC association is a curation outcome, not proof of a new
          discovery. Modern model training can include post-cutoff knowledge.
          Completion failures and shared biological sources limit conclusions.
        </p>
      </details>
    </section>
  );
}
