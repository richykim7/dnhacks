import { useCallback, useEffect, useState } from "react";
import type { RunDetail } from "./types";
import { id } from "./utils";
export async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const data = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(data?.error || `Request failed (${response.status})`);
  if (data === null)
    throw new Error("The server returned an unreadable response.");
  return data as T;
}
export const post = <T>(url: string, body: unknown = {}) =>
  request<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
export function useResource<T>(url: string | null, interval = 0) {
  const [state, setState] = useState<{
    data?: T;
    error?: string;
    loading: boolean;
  }>({ loading: true });
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((n) => n + 1), []);
  useEffect(() => {
    if (!url) {
      setState({ loading: false });
      return;
    }
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    setState({ loading: true });
    const load = async () => {
      try {
        const data = await request<T>(url, { signal: abort.signal });
        if (!abort.signal.aborted) setState({ data, loading: false });
      } catch (e) {
        if (!abort.signal.aborted)
          setState((s) => ({
            ...s,
            error: String((e as Error).message),
            loading: false,
          }));
      }
      if (!abort.signal.aborted && interval) timer = setTimeout(load, interval);
    };
    void load();
    return () => {
      abort.abort();
      clearTimeout(timer);
    };
  }, [url, interval, revision]);
  return { ...state, refresh };
}
// A selected agent owns exactly one stream. Reconnects resume from server event IDs;
// navigation closes the old stream and prevents late responses crossing branches.
export function useAgent(runId: string | null) {
  const [run, setRun] = useState<RunDetail>();
  const [error, setError] = useState("");
  const [connection, setConnection] = useState("Connecting");
  useEffect(() => {
    setRun(undefined);
    setError("");
    setConnection("Connecting");
    if (!runId) return;
    const abort = new AbortController();
    let stream: EventSource | undefined;
    const seen = new Set<string>();
    request<RunDetail>(`/api/runs/${id(runId)}`, { signal: abort.signal })
      .then((data) => {
        if (abort.signal.aborted) return;
        setRun(data);
        if (data.last_action === "done") {
          setConnection("Recorded");
          return;
        }
        stream = new EventSource(
          `/api/runs/${id(runId)}/stream?from=${data.resume_line}`,
        );
        stream.onopen = () => setConnection("Connected");
        stream.onerror = () => setConnection("Reconnecting");
        stream.addEventListener("step", (event) => {
          if (
            abort.signal.aborted ||
            (event.lastEventId && seen.has(event.lastEventId))
          )
            return;
          try {
            const step = JSON.parse(event.data);
            if (event.lastEventId) seen.add(event.lastEventId);
            setRun((r) =>
              r
                ? {
                    ...r,
                    steps: [...r.steps, step],
                    n_steps: r.n_steps + 1,
                    last_action: step.action,
                    active: step.action !== "done",
                  }
                : r,
            );
          } catch {
            setError(
              "One live update could not be read. Reload this agent to recover.",
            );
          }
        });
        stream.addEventListener("end", () => {
          stream?.close();
          setConnection("Recorded");
        });
      })
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message);
      });
    return () => {
      abort.abort();
      stream?.close();
    };
  }, [runId]);
  return { run, error, connection };
}
