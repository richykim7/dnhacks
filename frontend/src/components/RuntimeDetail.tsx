import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { GitBranch, Terminal, X } from "lucide-react";
import { Button } from "./ui/button";
import { AnimatedTabs } from "./ui/animated-tabs";
import { Disclosure, ErrorNotice, Loading, Status } from "./common";
import { request } from "@/lib/api";
import { runtimeUrl, type RuntimeEvent } from "@/lib/runtime";
import type { JsonRecord } from "@/lib/types";
import { actionLabel, date, human, number } from "@/lib/utils";
import "@/runtime.css";
const BinderWorkbench = lazy(() => import("./binder/Workbench"));
const SpindleObservatory = lazy(() => import("./spindle/SpindleObservatory"));
const Structures = lazy(() => import("./Structures"));

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
  onClose,
}: {
  experimentId?: string | null;
  run?: JsonRecord;
  runId: string;
  project: string;
  cursor: number | null;
  connection: string;
  onClose: () => void;
}) {
  const [tab, setTab] = useState("activity"),
    [terminal, setTerminal] = useState(false);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    setTab(experimentId ? "experiments" : "activity");
  }, [experimentId]);
  useEffect(() => {
    if (experimentId && tab === "experiments")
      document
        .querySelector(`[data-experiment-id="${CSS.escape(experimentId)}"]`)
        ?.scrollIntoView({ block: "nearest" });
  }, [experimentId, tab]);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const historic = cursor !== null;
  const stale = run?.heartbeat_at ? now / 1000 - run.heartbeat_at > 20 : true;
  const events: RuntimeEvent[] = run?.history || [];
  const exps = Object.values(run?.experiments || {}) as JsonRecord[];
  return (
    <>
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
          label={human(run?.lifecycle || "Not started at this point")}
          tone={run?.lifecycle === "failed" ? "negative" : "neutral"}
        />
        <h2>{run?.branch_objective || "Research branch"}</h2>
        {run?.reason && <p>{run.reason}</p>}
        {tab === "activity" && (
          <div className="current-work">
            <small>Runtime execution</small>
            <strong>
              {run?.activity?.label
                ? actionLabel(run.activity.action || run.activity.label)
                : "No operation running"}
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
                : `${connection} · ${stale ? "Worker heartbeat stale or unavailable" : "Worker heartbeat current"}`}
            </small>
          </div>
        )}
        <Disclosure title="Original research question">
          <p>{run?.original_question || "Not recorded"}</p>
        </Disclosure>
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
          <small className="muted">
            Terminal snapshots are unavailable in playback.
          </small>
        )}
        {terminal && !historic && (
          <TerminalView key={runId} runId={runId} project={project} />
        )}
      </div>
      <AnimatedTabs
        label="Researcher detail"
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "activity", label: "Activity" },
          { value: "experiments", label: "Experiments" },
        ]}
      />
      <div className="detail-scroll">
        {tab === "activity" ? (
          [...events]
            .reverse()
            .slice(0, 200)
            .map((e) => (
              <article className="activity-entry" key={e.event_id}>
                <div className="entry-meta">
                  <span>{human(e.kind.replaceAll(".", " "))}</span>
                  <time>{date(e.recorded_at)}</time>
                </div>
                {e.kind === "intent" ? (
                  <p>{e.payload.intent}</p>
                ) : e.payload.error ? (
                  <p className="notice">{e.payload.error}</p>
                ) : e.kind === "experiment.output" ? (
                  <pre>{e.payload.text}</pre>
                ) : e.payload.reason ? (
                  <p>{e.payload.reason}</p>
                ) : null}
                {e.payload.observation && (
                  <RecordedDisclosure title="Recorded observation">
                    <BlobText
                      runId={runId}
                      blob={e.payload.observation}
                      project={project}
                      cursor={cursor}
                    />
                  </RecordedDisclosure>
                )}
                {e.payload.inputs && (
                  <RecordedDisclosure title="Tool inputs">
                    <BlobText
                      runId={runId}
                      blob={e.payload.inputs}
                      project={project}
                      cursor={cursor}
                    />
                  </RecordedDisclosure>
                )}
                {e.kind === "instructions.delivered" && (
                  <p>
                    Complete {human(e.payload.name)} guidance supplied to the
                    model request. Delivery does not prove comprehension.
                  </p>
                )}
                {e.kind === "feedback.delivered" && (
                  <p>
                    Feedback supplied to the model request. This is not a
                    measured performance improvement.
                  </p>
                )}
              </article>
            ))
        ) : exps.length ? (
          exps.map((exp) => (
            <article
              className="experiment-detail"
              key={exp.experiment_id}
              data-experiment-id={exp.experiment_id}
            >
              <Status
                label={human(exp.status)}
                tone={exp.status === "failed" ? "negative" : "neutral"}
              />
              <h3>{exp.title || "Experiment"}</h3>
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
                          ? "Passed verifier checks · awaiting human review"
                          : exp.verification === "KILL"
                            ? "Rejected by verifier"
                            : "Verification pending"}
                  </strong>
                  {exp.verification_reason && <p>{exp.verification_reason}</p>}
                  {exp.human_review_note && <p>{exp.human_review_note}</p>}
                </div>
              )}
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
              {exp.artifacts.map((artifact: JsonRecord) => (
                <div className="experiment-artifact" key={artifact.artifact_id}>
                  {artifact.status === "available" &&
                  artifact.kind === "filament_trajectory" ? (
                    <Suspense
                      fallback={<Loading label="Opening spindle observatory" />}
                    >
                      <SpindleObservatory
                        url={runtimeUrl(
                          runId,
                          `blob/${artifact.storage_key}`,
                          project,
                          cursor,
                        )}
                      />
                    </Suspense>
                  ) : artifact.status === "available" &&
                    ["molecular_structure", "binder_bundle"].includes(artifact.kind) ? (
                    <>
                      <h4>{artifact.name}</h4>
                      <Status label={human(artifact.provenance.category)} />
                      <Suspense
                        fallback={
                          <Loading label="Opening experiment structure" />
                        }
                      >
                        {artifact.kind === "binder_bundle" ? (
                          <BinderWorkbench
                            sha256={artifact.sha256}
                            url={runtimeUrl(
                              runId,
                              `blob/${artifact.storage_key}`,
                              project,
                              historic ? artifact.available_sequence : null,
                            )}
                          />
                        ) : (
                          <Structures
                            owner={`${exp.title || "Experiment"} · ${runId}`}
                            artifact={artifact}
                            url={runtimeUrl(
                              runId,
                              `blob/${artifact.storage_key}`,
                              project,
                              historic ? artifact.available_sequence : null,
                            )}
                          />
                        )}
                      </Suspense>
                      <Disclosure title="Structure provenance">
                        <pre>
                          {JSON.stringify(artifact.provenance, null, 2)}
                        </pre>
                        <small>SHA-256: {artifact.sha256}</small>
                      </Disclosure>
                    </>
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
      </div>
    </>
  );
}
