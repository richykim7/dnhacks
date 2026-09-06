import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { GitBranch, Terminal, X } from "lucide-react";
import { Button } from "./ui/button";
import { Disclosure, ErrorNotice, Loading, Status } from "./common";
import { request } from "@/lib/api";
import {
  runtimeUrl,
  runtimeRunSummary,
  runtimeMilestones,
  type RuntimeEvent,
} from "@/lib/runtime";
import type { JsonRecord } from "@/lib/types";
import { actionLabel, date, human, number } from "@/lib/utils";
import "@/runtime.css";
import CandidateReview from "./CandidateReview";
import NodeScene, { type SceneChoice } from "./NodeScene";
const SpindleMetrics = lazy(() => import("./spindle/SpindleMetrics"));
const SpindleObservatory = lazy(() => import("./spindle/SpindleObservatory"));
const TissueWorkbench = lazy(() => import("./tissue/TissueWorkbench"));
const IllustrativeScene = lazy(() => import("./IllustrativeScene"));

function RecordedDisclosure({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <details
      className="disclosure"
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>{title}</summary>
      {open && <div>{children}</div>}
    </details>
  );
}

function BlobText({
  runId,
  blob,
  project,
  cursor,
}: {
  runId: string;
  blob: JsonRecord;
  project: string;
  cursor: number | null;
}) {
  const [text, setText] = useState("");
  useEffect(() => {
    const abort = new AbortController();
    void fetch(runtimeUrl(runId, `blob/${blob.storage_key}`, project, cursor), {
      signal: abort.signal,
    })
      .then(async (r) => {
        if (!r.ok) throw new Error("Recorded output unavailable");
        return r.text();
      })
      .then(setText)
      .catch((e) => {
        if (!abort.signal.aborted) setText(e.message);
      });
    return () => abort.abort();
  }, [runId, blob.storage_key, project, cursor]);
  return <pre>{text || "Loading recorded output…"}</pre>;
}
function TerminalView({ runId, project }: { runId: string; project: string }) {
  const [capture, setCapture] = useState<JsonRecord>(),
    [error, setError] = useState("");
  useEffect(() => {
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout>,
      failures = 0;
    async function poll() {
      if (!document.hidden)
        try {
          const c = await request<JsonRecord>(
            runtimeUrl(runId, "terminal", project),
            { signal: abort.signal },
          );
          if (!abort.signal.aborted) {
            setCapture(c);
            setError("");
            failures = 0;
          }
        } catch (e) {
          if (!abort.signal.aborted) {
            setError((e as Error).message);
            failures++;
          }
        }
      if (!abort.signal.aborted)
        timer = setTimeout(poll, Math.min(15000, 1000 * 2 ** failures));
    }
    void poll();
    return () => {
      abort.abort();
      clearTimeout(timer);
    };
  }, [runId, project]);
  return (
    <div className="terminal-view">
      <ErrorNotice message={error} />
      {capture?.available ? (
        <>
          <small>Screen captured {date(capture.captured_at)}</small>
          <pre>{capture.text}</pre>
          <p className="muted">{capture.notice}</p>
        </>
      ) : (
        <p>{capture?.reason || "Checking registered terminal…"}</p>
      )}
    </div>
  );
}

export function RuntimeDetail({
  experimentId,
  run,
  runId,
  project,
  cursor,
  connection,
  replayTime,
  onClose,
}: {
  experimentId?: string | null;
  run?: JsonRecord;
  runId: string;
  project: string;
  cursor: number | null;
  connection: string;
  replayTime?: number;
  onClose: () => void;
}) {
  const [terminal, setTerminal] = useState(false);
  const [showAllExperiments, setShowAllExperiments] = useState(false);
  const [now, setNow] = useState(Date.now());
  const [chosenScene, setChosenScene] = useState<string | null>(null);
  useEffect(() => setChosenScene(null), [experimentId, runId]);
  useEffect(() => {
    setShowAllExperiments(Boolean(experimentId));
  }, [experimentId, runId]);
  useEffect(() => {
    if (experimentId)
      document
        .querySelector(`[data-experiment-id="${CSS.escape(experimentId)}"]`)
        ?.scrollIntoView({ block: "nearest" });
  }, [experimentId, showAllExperiments]);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const historic = cursor !== null;
  const summary = runtimeRunSummary(
    run,
    historic ? (replayTime ?? run?.updated_at ?? 0) : now / 1000,
    historic,
  );
  const milestones = runtimeMilestones(run);
  const events: RuntimeEvent[] = run?.history || [];
  const exps = (
    Object.values(run?.experiments || {}) as JsonRecord[]
  ).reverse();
  const rankedExps = [...exps].sort(
    (a, b) =>
      Number(b.experiment_id === experimentId) -
        Number(a.experiment_id === experimentId) ||
      Number(["queued", "running"].includes(b.status)) -
        Number(["queued", "running"].includes(a.status)) ||
      Number(b.verification === "CANDIDATE") -
        Number(a.verification === "CANDIDATE"),
  );
  const visibleExps = showAllExperiments ? rankedExps : rankedExps.slice(0, 3);
  const sceneChoices: SceneChoice[] = exps.flatMap((experiment) =>
    (experiment.artifacts || [])
      .filter(
        (artifact: JsonRecord) =>
          artifact.status === "available" &&
          [
            "binder_bundle",
            "molecular_structure",
            "filament_trajectory",
            "tissue_simulation",
            "illustrative_scene",
          ].includes(artifact.kind),
      )
      .map((artifact: JsonRecord) => ({
        key: `${experiment.experiment_id}:${artifact.artifact_id}`,
        experiment,
        artifact,
      })),
  );
  const activeScene =
    sceneChoices.find((c) => c.key === chosenScene) ||
    sceneChoices.find(
      (c) =>
        c.experiment.experiment_id === experimentId &&
        c.artifact.kind === "binder_bundle",
    ) ||
    sceneChoices.find((c) => c.experiment.experiment_id === experimentId) ||
    sceneChoices.find((c) => c.artifact.kind === "binder_bundle") ||
    sceneChoices[0];
  return (
    <div
      className={`node-workspace researcher-workspace ${activeScene ? "has-scene" : ""}`}
    >
      {activeScene && (
        <div className="workspace-render">
          {["binder_bundle", "molecular_structure"].includes(
            activeScene.artifact.kind,
          ) ? (
            <NodeScene
              choices={sceneChoices}
              active={activeScene}
              onSelect={setChosenScene}
              onClose={onClose}
              events={events}
              runId={runId}
              project={project}
              cursor={cursor}
            />
          ) : (
            <section className="node-scene" aria-label="Research scene">
              <header className="node-scene-header">
                <label>
                  Scene source
                  <select
                    aria-label="Scene source"
                    value={activeScene.key}
                    onChange={(event) => setChosenScene(event.target.value)}
                  >
                    {sceneChoices.map((choice) => (
                      <option key={choice.key} value={choice.key}>
                        {choice.experiment.title || "Experiment"} ·{" "}
                        {choice.artifact.name || human(choice.artifact.kind)}
                      </option>
                    ))}
                  </select>
                </label>
              </header>
              <div
                className="node-scene-object"
                data-scene-experiment-id={activeScene.experiment.experiment_id}
              >
                <Suspense fallback={<Loading label="Opening recorded scene" />}>
                  {activeScene.artifact.kind === "illustrative_scene" ? (
                    <IllustrativeScene
                      key={activeScene.key}
                      url={runtimeUrl(
                        runId,
                        `blob/${activeScene.artifact.storage_key}`,
                        project,
                        cursor,
                      )}
                    />
                  ) : activeScene.artifact.kind === "tissue_simulation" ? (
                    <TissueWorkbench
                      embedded
                      key={activeScene.key}
                      actions={
                        events.filter(
                          (e) =>
                            e.kind === "tissue.scene" &&
                            e.experiment_id ===
                              activeScene.experiment.experiment_id &&
                            e.payload.artifact_sha256 ===
                              activeScene.artifact.sha256,
                        ) as any
                      }
                      owner={`${activeScene.experiment.title || "Experiment"} · ${runId}`}
                      url={runtimeUrl(
                        runId,
                        `blob/${activeScene.artifact.storage_key}`,
                        project,
                        cursor,
                      )}
                    />
                  ) : (
                    <SpindleObservatory
                      key={activeScene.key}
                      sha256={activeScene.artifact.sha256}
                      sceneActions={events
                        .filter(
                          (e) =>
                            e.kind === "scene.recipe" &&
                            e.experiment_id ===
                              activeScene.experiment.experiment_id &&
                            e.payload.bundle_sha256 ===
                              activeScene.artifact.sha256,
                        )
                        .map((e) => ({
                          sequence: e.sequence,
                          note: e.payload.note,
                          recipe_sha256: e.payload.recipe.sha256,
                          view: e.payload.view,
                        }))}
                      url={runtimeUrl(
                        runId,
                        `blob/${activeScene.artifact.storage_key}`,
                        project,
                        cursor,
                      )}
                    />
                  )}
                </Suspense>
              </div>
            </section>
          )}
        </div>
      )}
      <section
        className="node-research"
        aria-label="Research activity and findings"
      >
        <div className="detail-head">
          <span>
            <GitBranch size={15} />
            Researcher
          </span>
          <Button
            size="icon"
            variant="ghost"
            aria-label="Close researcher detail"
            onClick={onClose}
          >
            <X size={17} />
          </Button>
        </div>
        <div className="detail-intro">
          <Status
            label={human(summary.status)}
            tone={run?.lifecycle === "failed" ? "negative" : "neutral"}
          />
          <h2>{run?.branch_objective || "Research branch"}</h2>
          {run?.reason && <p>{run.reason}</p>}
          {
            <div className="current-work">
              <small>Current activity</small>
              <strong>
                {run?.activity?.label
                  ? actionLabel(run.activity.action || run.activity.label)
                  : "No operation recorded"}
              </strong>
              {run?.intent && (
                <>
                  <small>Agent’s stated intent</small>
                  <p>{run.intent}</p>
                </>
              )}
              <small>
                {historic
                  ? "Recorded at playback cursor"
                  : `${connection} · ${summary.status === "stale" ? "Worker heartbeat stale or unavailable" : summary.status === "running" || summary.status === "idle" || summary.status === "stale" ? "Latest research state" : "Recorded research state"}`}
              </small>
            </div>
          }
          <Disclosure title="Full objective and intent">
            <p>
              <strong>Research question:</strong>{" "}
              {run?.original_question || "Not recorded"}
            </p>
            <p>
              <strong>Branch objective:</strong>{" "}
              {run?.branch_objective || "Not recorded"}
            </p>
            {run?.intent && (
              <p>
                <strong>Current intent:</strong> {run.intent}
              </p>
            )}
          </Disclosure>
        </div>
        <div className="detail-scroll research-overview">
          <div className="research-section-heading">
            <h3>
              Experiments <span>{summary.experimentCount}</span>
            </h3>
            {summary.candidateCount > 0 && (
              <span className="runtime-candidate-badge">
                {summary.candidateCount} candidate
                {summary.candidateCount === 1 ? "" : "s"} emitted
              </span>
            )}
          </div>
          {exps.length ? (
            visibleExps.map((exp) => (
              <article
                className="experiment-detail"
                key={exp.experiment_id}
                data-experiment-id={exp.experiment_id}
              >
                <Status
                  label={human(exp.status)}
                  tone={exp.status === "failed" ? "negative" : "neutral"}
                />
                <h3>{exp.title || exp.method || "Experiment"}</h3>
                {typeof exp.summary === "string" && <p>{exp.summary}</p>}
                {typeof exp.plan === "string" && <p>{exp.plan}</p>}
                {exp.error && <p className="notice">{exp.error}</p>}
                <p className="muted">
                  {exp.method || "Exploratory analysis"}
                  {exp.exploratory ? " · Not audited" : ""}
                </p>
                {exp.result && (
                  <dl className="measurements">
                    {[
                      ["effect", "Method-specific effect"],
                      ["p_null", "Null-test p-value"],
                      ["n_units", "Independent samples"],
                    ].map(([key, label]) =>
                      typeof exp.result[key] === "number" &&
                      Number.isFinite(exp.result[key]) ? (
                        <div key={key}>
                          <dt>{label}</dt>
                          <dd>{number(exp.result[key])}</dd>
                        </div>
                      ) : null,
                    )}
                  </dl>
                )}
                {exp.result && typeof exp.result.summary === "string" && (
                  <p>{exp.result.summary}</p>
                )}
                {exp.result && (
                  <Disclosure title="Recorded result">
                    <pre>{JSON.stringify(exp.result, null, 2)}</pre>
                  </Disclosure>
                )}
                {(exp.verification || exp.human_review) && (
                  <div className="notice">
                    <strong>
                      {exp.human_review === "validated"
                        ? "Accepted by human review"
                        : exp.human_review === "rejected"
                          ? "Rejected by human review"
                          : exp.verification === "CANDIDATE"
                            ? "CANDIDATE · automated checks passed, awaiting human review"
                            : exp.verification === "KILL"
                              ? "Rejected by verifier"
                              : "Verification pending"}
                    </strong>
                    {exp.verification_reason && (
                      <p>{exp.verification_reason}</p>
                    )}
                    {exp.human_review_note && <p>{exp.human_review_note}</p>}
                  </div>
                )}
                <CandidateReview
                  runId={runId}
                  experiment={{
                    ...exp,
                    candidate_emitted: (run?.history || []).some(
                      (e: RuntimeEvent) =>
                        e.experiment_id === exp.experiment_id &&
                        e.payload.verification === "CANDIDATE",
                    ),
                  }}
                  project={project}
                  cursor={cursor}
                />
                {exp.code && (
                  <RecordedDisclosure title="Analysis code">
                    <BlobText
                      runId={runId}
                      blob={exp.code}
                      project={project}
                      cursor={cursor}
                    />
                  </RecordedDisclosure>
                )}
                {exp.stdout && (
                  <RecordedDisclosure title="Recorded output">
                    <BlobText
                      runId={runId}
                      blob={exp.stdout}
                      project={project}
                      cursor={cursor}
                    />
                  </RecordedDisclosure>
                )}
                {exp.stderr?.byte_length > 0 && (
                  <RecordedDisclosure title="Error output">
                    <BlobText
                      runId={runId}
                      blob={exp.stderr}
                      project={project}
                      cursor={cursor}
                    />
                  </RecordedDisclosure>
                )}
                {events
                  .filter(
                    (e) =>
                      e.kind === "tissue.capture" &&
                      e.experiment_id === exp.experiment_id,
                  )
                  .map((e) => (
                    <RecordedDisclosure
                      key={e.sequence}
                      title={`Agent tissue capture · event ${e.sequence}`}
                    >
                      <img
                        alt={`Recorded tissue scene, recipe ${e.payload.recipe_sha256}`}
                        style={{ width: "100%", borderRadius: 8 }}
                        src={runtimeUrl(
                          runId,
                          `blob/${e.payload.image_sha256}`,
                          project,
                          cursor,
                        )}
                      />
                      <p>Scene revision: {e.payload.recipe_sha256}</p>
                      {events
                        .filter(
                          (o) =>
                            o.kind === "tissue.observation" &&
                            o.payload.capture_id === e.payload.capture_id,
                        )
                        .map((o) => (
                          <p key={o.sequence}>
                            {o.payload.status}: {o.payload.observation}
                          </p>
                        ))}
                    </RecordedDisclosure>
                  ))}
                {(run?.history ?? []).some(
                  (e: RuntimeEvent) =>
                    e.kind === "binder.job" &&
                    e.experiment_id === exp.experiment_id,
                ) && (
                  <RecordedDisclosure title="Binder design activity">
                    <p>
                      Recorded job states; queued receipts require an operator
                      launch. No simulated compute progress.
                    </p>
                    <ol>
                      {(run?.history ?? [])
                        .filter(
                          (e: RuntimeEvent) =>
                            e.kind === "binder.job" &&
                            e.experiment_id === exp.experiment_id,
                        )
                        .map((e: RuntimeEvent) => (
                          <li key={e.sequence}>
                            {human(e.payload.state)}
                            {e.payload.candidate_id
                              ? ` · ${e.payload.candidate_id}`
                              : ""}
                            {e.payload.reason ? ` · ${e.payload.reason}` : ""}
                            {e.payload.rejection_reason
                              ? ` · Rejected: ${e.payload.rejection_reason}`
                              : ""}
                          </li>
                        ))}
                    </ol>
                  </RecordedDisclosure>
                )}
                {(exp.artifacts || []).map((artifact: JsonRecord) => (
                  <div
                    className="experiment-artifact"
                    key={artifact.artifact_id}
                  >
                    {artifact.status === "available" &&
                    [
                      "molecular_structure",
                      "binder_bundle",
                      "filament_trajectory",
                      "tissue_simulation",
                      "illustrative_scene",
                    ].includes(artifact.kind) ? (
                      <>
                        <h4>{artifact.name}</h4>
                        {artifact.provenance?.category && (
                          <Status label={human(artifact.provenance.category)} />
                        )}
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() =>
                            setChosenScene(
                              `${exp.experiment_id}:${artifact.artifact_id}`,
                            )
                          }
                        >
                          {activeScene?.artifact.artifact_id ===
                            artifact.artifact_id &&
                          activeScene?.experiment.experiment_id ===
                            exp.experiment_id
                            ? "Viewing in research scene"
                            : "View in research scene"}
                        </Button>
                        <Disclosure title="Artifact provenance">
                          <pre>
                            {JSON.stringify(artifact.provenance, null, 2)}
                          </pre>
                          <small>SHA-256: {artifact.sha256}</small>
                        </Disclosure>
                      </>
                    ) : artifact.kind === "spindle_metrics" &&
                      artifact.status === "available" ? (
                      <Suspense
                        fallback={<Loading label="Opening ensemble metrics" />}
                      >
                        <SpindleMetrics
                          url={runtimeUrl(
                            runId,
                            `blob/${artifact.storage_key}`,
                            project,
                            cursor,
                          )}
                        />
                      </Suspense>
                    ) : artifact.status === "available" &&
                      [
                        "binder_target",
                        "binder_epitope",
                        "binder_protocol",
                        "binder_comparison",
                        "binder_followup",
                      ].includes(artifact.kind) ? (
                      <RecordedDisclosure
                        title={`Inspect ${human(artifact.kind)}`}
                      >
                        <p>Immutable exploratory record · {artifact.name}</p>
                        <a
                          href={runtimeUrl(
                            runId,
                            `blob/${artifact.storage_key}`,
                            project,
                            cursor,
                          )}
                          download={`${artifact.kind}.json`}
                        >
                          Download record
                        </a>
                        <BlobText
                          runId={runId}
                          blob={artifact}
                          project={project}
                          cursor={cursor}
                        />
                      </RecordedDisclosure>
                    ) : artifact.kind === "scene_movie" &&
                      artifact.status === "available" ? (
                      <video
                        controls
                        preload="metadata"
                        aria-label="Saved spindle trajectory movie"
                        style={{ width: "100%", maxHeight: 640 }}
                        src={runtimeUrl(
                          runId,
                          `blob/${artifact.storage_key}`,
                          project,
                          cursor,
                        )}
                      />
                    ) : artifact.kind === "scene_capture" &&
                      artifact.status === "available" ? (
                      <figure className="binder-recorded-capture">
                        <img
                          src={runtimeUrl(
                            runId,
                            `blob/${artifact.storage_key}`,
                            project,
                            historic ? artifact.available_sequence : null,
                          )}
                          alt={artifact.name}
                        />
                        <figcaption>
                          Recorded agent view · {artifact.name}
                        </figcaption>
                      </figure>
                    ) : (
                      <p className="notice">
                        Artifact {artifact.status}:{" "}
                        {artifact.failure_reason || "Not available yet"}
                      </p>
                    )}
                  </div>
                ))}
              </article>
            ))
          ) : (
            <p className="muted">No experiments at this point.</p>
          )}
          {exps.length > 3 && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setShowAllExperiments((value) => !value)}
            >
              {showAllExperiments
                ? "Show fewer experiments"
                : `Show all ${exps.length} experiments`}
            </Button>
          )}
          <section
            className="research-milestones"
            aria-label="Major research steps"
          >
            <h3>Major steps</h3>
            {milestones.length ? (
              milestones.map((step) => (
                <article className="activity-entry" key={step.sequence}>
                  <div className="entry-meta">
                    <strong>{step.title}</strong>
                    <time>{date(step.recordedAt)}</time>
                  </div>
                  <p>{step.summary}</p>
                </article>
              ))
            ) : (
              <p className="muted">
                Meaningful research steps will appear as they are recorded.
              </p>
            )}
          </section>
          <RecordedDisclosure title="Advanced diagnostics">
            <p className="muted">
              Recent public runtime events. Research summaries above omit model
              and tool noise.
            </p>
            <Button
              size="sm"
              variant="ghost"
              disabled={historic}
              onClick={() => setTerminal((s) => !s)}
            >
              <Terminal size={14} />
              {terminal && !historic ? "Hide terminal" : "Show terminal"}
            </Button>
            {historic && (
              <p className="muted">
                Terminal snapshots are unavailable in playback.
              </p>
            )}
            {terminal && !historic && (
              <TerminalView key={runId} runId={runId} project={project} />
            )}
            {events
              .filter((e) =>
                /^(attempt|lifecycle|intent|model|tool|experiment|artifact|checkpoint|branch)[.]*?/.test(
                  e.kind,
                ),
              )
              .slice(-40)
              .reverse()
              .map((e) => (
                <article className="activity-entry" key={e.event_id}>
                  <div className="entry-meta">
                    <span>{human(e.kind.replaceAll(".", " "))}</span>
                    <time>{date(e.recorded_at)}</time>
                  </div>
                  {e.payload.error && <p>{e.payload.error}</p>}
                  {typeof e.payload.observation === "string" ? (
                    <p>{e.payload.observation}</p>
                  ) : e.payload.observation?.storage_key ? (
                    <RecordedDisclosure title="Recorded observation">
                      <BlobText
                        runId={runId}
                        blob={e.payload.observation}
                        project={project}
                        cursor={cursor}
                      />
                    </RecordedDisclosure>
                  ) : null}
                </article>
              ))}
          </RecordedDisclosure>
        </div>
      </section>
    </div>
  );
}
