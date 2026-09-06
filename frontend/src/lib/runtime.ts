import { useEffect, useState } from "react";
import { request } from "./api";
import type { JsonRecord } from "./types";
export type RuntimeEvent = {
  schema_version: number;
  sequence: number;
  run_id: string;
  attempt_id: string;
  kind: string;
  payload: JsonRecord;
  experiment_id?: string;
  operation_id?: string;
  recorded_at: number;
  producer: string;
  event_id: string;
};
export type RuntimeState = {
  schema_version: number;
  sequence: number;
  runs: Record<string, JsonRecord>;
};
export const emptyRuntime = (): RuntimeState => ({
  schema_version: 1,
  sequence: 0,
  runs: {},
});
// Shared by initial history, live delivery and every playback cursor.
export function reduceRuntime(
  state: RuntimeState,
  e: RuntimeEvent,
): RuntimeState {
  if (e.schema_version !== 1)
    throw new Error("Unsupported runtime history version");
  if (e.sequence <= state.sequence) return state;
  if (e.sequence !== state.sequence + 1) throw new Error("Runtime event gap");
  const previous = state.runs[e.run_id] || {
    run_id: e.run_id,
    experiments: {},
    history: [],
  };
  const run: JsonRecord = {
    ...previous,
    experiments: { ...previous.experiments },
    updated_at: e.recorded_at,
  };
  const p = e.payload,
    kind = e.kind;
  if (kind === "attempt.started")
    Object.assign(run, p, {
      attempt_id: e.attempt_id,
      lifecycle: "running",
      intent: "",
      activity: null,
      heartbeat_at: null,
    });
  else if (kind === "lifecycle") {
    Object.assign(run, p);
    if (
      [
        "completed",
        "failed",
        "cancelled",
        "budget_exhausted",
        "pruned",
      ].includes(p.lifecycle)
    ) {
      run.activity = null;
      for (const [id, value] of Object.entries(run.experiments)) {
        const exp = value as JsonRecord;
        if (["queued", "running"].includes(exp.status))
          run.experiments[id] = {
            ...exp,
            status: "interrupted",
            error: "Attempt ended before an experiment outcome was recorded",
          };
      }
    }
  } else if (kind === "worker.registered" && run.lifecycle === "queued")
    Object.assign(run, p, { attempt_id: e.attempt_id });
  else if (kind === "heartbeat") run.heartbeat_at = e.recorded_at;
  else if (kind === "intent") run.intent = p.intent;
  else if (["model.started", "tool.started"].includes(kind))
    run.activity = {
      ...p,
      operation_id: e.operation_id,
      started_at: e.recorded_at,
    };
  else if (["model.ended", "tool.ended", "tool.failed"].includes(kind))
    run.activity = null;
  else if (kind.startsWith("experiment.")) {
    const eid = e.experiment_id!;
    run.experiments[eid] = {
      ...(run.experiments[eid] || { experiment_id: eid, artifacts: [] }),
      ...p,
    };
  } else if (kind === "artifact") {
    const eid = e.experiment_id!,
      exp = run.experiments[eid];
    run.experiments[eid] = {
      ...exp,
      artifacts: [...exp.artifacts, { ...p, available_sequence: e.sequence }],
    };
  } else if (kind === "checkpoint.report") run.checkpoint = p;
  else if (kind === "branch.decision") run.decision = p;
  if (kind !== "heartbeat") run.history = [...run.history, e];
  return {
    ...state,
    sequence: e.sequence,
    runs: { ...state.runs, [e.run_id]: run },
  };
}
// Candidate is an automated verifier emission, not an accepted discovery. Link
// submission aliases to experiments so retried submissions cannot inflate it.
export function runtimeCandidates(run?: JsonRecord): JsonRecord[] {
  const experiments = Object.values(run?.experiments || {}) as JsonRecord[];
  const history: RuntimeEvent[] = run?.history || [];
  const parents = new Map<string, string>();
  const root = (key: string): string => {
    const parent = parents.get(key);
    if (!parent) {
      parents.set(key, key);
      return key;
    }
    if (parent === key) return key;
    const found = root(parent);
    parents.set(key, found);
    return found;
  };
  const identity = (experiment: unknown, submission: unknown) => {
    const exp =
      typeof experiment === "string" && experiment
        ? `experiment:${experiment}`
        : null;
    const sub = submission != null ? `submission:${submission}` : null;
    if (exp && sub) parents.set(root(sub), root(exp));
    return exp || sub;
  };
  const candidates: string[] = [];
  for (const e of history) {
    if (!e.kind.startsWith("experiment.")) continue;
    const key = identity(e.experiment_id, e.payload.submission_id);
    if (key && e.payload.verification === "CANDIDATE") candidates.push(key);
  }
  for (const exp of experiments) {
    const key = identity(exp.experiment_id, exp.submission_id);
    if (key && exp.verification === "CANDIDATE") candidates.push(key);
  }
  const emitted = new Set(candidates.map(root));
  const unique = new Map<string, JsonRecord>();
  for (const exp of experiments) {
    const key = identity(exp.experiment_id, exp.submission_id);
    if (key && emitted.has(root(key))) {
      const previous = unique.get(root(key));
      const representative = previous?.title ? previous : exp;
      const review =
        exp.human_review &&
        (!previous?.human_review ||
          (exp.human_review_at ?? 0) >= (previous.human_review_at ?? 0))
          ? exp
          : previous;
      unique.set(root(key), {
        ...representative,
        candidate_emitted: true,
        ...(review?.human_review
          ? {
              human_review: review.human_review,
              human_review_note: review.human_review_note,
              human_review_at: review.human_review_at,
              test_id: review.test_id,
            }
          : {}),
      });
    }
  }
  return [...unique.values()];
}
export function runtimeRunSummary(
  run?: JsonRecord,
  nowSeconds = Date.now() / 1000,
  historic = false,
) {
  const experiments = Object.values(run?.experiments || {}) as JsonRecord[];
  const history: RuntimeEvent[] = run?.history || [];
  const candidates = runtimeCandidates(run);
  const lifecycle = run?.lifecycle || "queued";
  const fresh =
    typeof run?.heartbeat_at === "number" &&
    nowSeconds - run.heartbeat_at <= 20 &&
    nowSeconds >= run.heartbeat_at;
  const running = lifecycle === "running";
  const started = [...history]
    .reverse()
    .find((e) => e.kind === "attempt.started")?.recorded_at;
  const ended = [
    "completed",
    "failed",
    "cancelled",
    "budget_exhausted",
    "pruned",
  ].includes(lifecycle)
    ? [...history]
        .reverse()
        .find(
          (e) => e.kind === "lifecycle" && e.payload.lifecycle === lifecycle,
        )?.recorded_at
    : undefined;
  const until = !running ? (ended ?? run?.updated_at ?? started) : nowSeconds;
  return {
    experimentCount: experiments.length,
    candidateCount: candidates.length,
    acceptedCount: candidates.filter((exp) => exp.human_review === "validated")
      .length,
    freshActivity:
      !historic &&
      running &&
      fresh &&
      Boolean(run?.activity || experiments.some((e) => e.status === "running")),
    status:
      running && !historic
        ? !fresh
          ? "stale"
          : run?.activity || experiments.some((e) => e.status === "running")
            ? "running"
            : "idle"
        : lifecycle,
    elapsedSeconds:
      started != null && until != null ? Math.max(0, until - started) : null,
  };
}

export type RuntimeMilestone = {
  sequence: number;
  recordedAt: number;
  title: string;
  summary: string;
};
const concise = (value: unknown, max = 320) =>
  typeof value === "string" ? value.trim().slice(0, max) : "";
// Deliberately allowlist ordinary research fields: model/tool output and private
// controller events never become a research summary.
export function runtimeMilestones(run?: JsonRecord): RuntimeMilestone[] {
  const result: RuntimeMilestone[] = [];
  for (const e of (run?.history || []) as RuntimeEvent[]) {
    const p = e.payload;
    let title = "",
      summary = "";
    if (e.kind === "intent") {
      title = "Research intent";
      summary = concise(p.intent);
    } else if (e.kind === "checkpoint.report") {
      title = "Research checkpoint";
      const report = p.report || {};
      summary =
        concise(
          [
            ...(report.findings || [])
              .slice(0, 2)
              .map((f: JsonRecord) => concise(f.claim, 180)),
            ...(report.completed_work || [])
              .slice(0, 1)
              .map((s: unknown) => concise(s, 140)),
            ...(report.blockers || [])
              .slice(0, 1)
              .map((s: unknown) => `Blocked: ${concise(s, 120)}`),
          ]
            .filter(Boolean)
            .join(" · "),
          520,
        ) || "Checkpoint recorded";
    } else if (e.kind === "branch.decision") {
      const decision = p.decision || p;
      title = "Branch decision";
      summary = concise(decision.reason || decision.objective);
    } else if (
      e.kind === "lifecycle" &&
      [
        "completed",
        "failed",
        "pruned",
        "cancelled",
        "budget_exhausted",
        "awaiting_parent",
      ].includes(p.lifecycle)
    ) {
      title =
        p.lifecycle === "awaiting_parent"
          ? "Awaiting parent decision"
          : "Research " + p.lifecycle.replaceAll("_", " ");
      summary = concise(p.reason) || title;
    }
    if (!summary || result.at(-1)?.summary === summary) continue;
    if (title === "Research intent" && result.at(-1)?.title === title)
      result.pop();
    result.push({
      sequence: e.sequence,
      recordedAt: e.recorded_at,
      title,
      summary,
    });
  }
  return result.reverse().slice(0, 8);
}
export function runtimeUrl(
  run: string,
  action: string,
  project: string,
  through?: number | null,
) {
  const qs = new URLSearchParams();
  if (project) qs.set("project", project);
  if (through != null) qs.set("through", String(through));
  return `/api/runtime/${encodeURIComponent(run)}/${action}?${qs}`;
}
export function useRuntime(root: string | null, project: string) {
  const [events, setEvents] = useState<RuntimeEvent[]>([]),
    [error, setError] = useState("");
  const [connection, setConnection] = useState("Connecting");
  useEffect(() => {
    setEvents([]);
    setError("");
    if (!root) return;
    const abort = new AbortController();
    let stream: EventSource | undefined,
      timer: ReturnType<typeof setTimeout>,
      cursor = 0;
    const collected: RuntimeEvent[] = [];
    const accept = (event: RuntimeEvent) => {
      if (event.sequence <= cursor) return;
      if (event.schema_version !== 1 || event.sequence !== cursor + 1)
        throw new Error("History gap");
      collected.push(event);
      cursor = event.sequence;
    };
    async function connect() {
      try {
        let batch: RuntimeEvent[];
        do {
          const response = await request<{ events: RuntimeEvent[] }>(
            runtimeUrl(root!, "events", project) + `&after=${cursor}`,
            { signal: abort.signal },
          );
          batch = response.events;
          batch.forEach(accept);
        } while (batch.length === 1000 && !abort.signal.aborted);
        if (abort.signal.aborted) return;
        setEvents([...collected]);
        setError("");
        stream = new EventSource(
          runtimeUrl(root!, "stream", project) + `&after=${cursor}`,
        );
        stream.onopen = () => setConnection("Connected");
        stream.onerror = () => setConnection("Reconnecting");
        stream.addEventListener("runtime", (message) => {
          try {
            accept(JSON.parse(message.data));
            setEvents([...collected]);
          } catch {
            stream?.close();
            setError("Recovering a gap in the live history…");
            timer = setTimeout(() => void connect(), 1000);
          }
        });
      } catch (e) {
        if (!abort.signal.aborted) {
          setError((e as Error).message);
          setConnection("Reconnecting");
          timer = setTimeout(() => void connect(), 3000);
        }
      }
    }
    void connect();
    return () => {
      abort.abort();
      stream?.close();
      clearTimeout(timer);
    };
  }, [root, project]);
  return { events, error, connection };
}
