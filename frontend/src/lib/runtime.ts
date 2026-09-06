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
      ["completed", "failed", "cancelled", "budget_exhausted"].includes(
        p.lifecycle,
      )
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
  } else if (kind === "branch.decision") run.decision = p;
  if (kind !== "heartbeat") run.history = [...run.history, e];
  return {
    ...state,
    sequence: e.sequence,
    runs: { ...state.runs, [e.run_id]: run },
  };
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
