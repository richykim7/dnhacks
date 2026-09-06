import { describe, expect, it } from "vitest";
import { emptyRuntime, reduceRuntime, type RuntimeEvent } from "./runtime";
const event = (
  sequence: number,
  kind: string,
  payload = {},
  run_id = "root",
): RuntimeEvent => ({
  schema_version: 1,
  sequence,
  kind,
  payload,
  run_id,
  attempt_id: "a",
  recorded_at: sequence,
  producer: "runner",
  event_id: String(sequence),
  experiment_id: "exp",
});
describe("runtime reducer", () => {
  it("replays human decisions without changing the verifier assessment", () => {
    const before = reduceRuntime(
      emptyRuntime(),
      event(1, "experiment.reviewed", { verification: "CANDIDATE" }),
    );
    const after = reduceRuntime(
      before,
      event(2, "experiment.human_reviewed", {
        human_review: "validated",
        human_review_note: "Checked controls",
      }),
    );
    expect(before.runs.root.experiments.exp.human_review).toBeUndefined();
    expect(after.runs.root.experiments.exp.verification).toBe("CANDIDATE");
    expect(after.runs.root.experiments.exp.human_review).toBe("validated");
  });
  it("deduplicates and rejects gaps and unknown versions", () => {
    const e = event(1, "attempt.started");
    const s = reduceRuntime(emptyRuntime(), e);
    expect(reduceRuntime(s, e)).toBe(s);
    expect(() => reduceRuntime(s, event(3, "heartbeat"))).toThrow("gap");
    expect(() =>
      reduceRuntime(s, { ...event(2, "heartbeat"), schema_version: 2 }),
    ).toThrow("version");
  });
  it("never leaks future children, results, or artifacts at any cursor", () => {
    const events = [
      event(1, "attempt.started"),
      event(2, "attempt.started", {}, "root~1"),
      event(3, "experiment.queued", { status: "queued" }, "root~1"),
      event(
        4,
        "experiment.finished",
        { status: "completed", result: { value: 2 } },
        "root~1",
      ),
      event(5, "artifact", { artifact_id: "mol" }, "root~1"),
    ];
    const states = events.map((_, i) =>
      events.slice(0, i + 1).reduce(reduceRuntime, emptyRuntime()),
    );
    expect(states[0].runs["root~1"]).toBeUndefined();
    expect(states[2].runs["root~1"].experiments.exp.result).toBeUndefined();
    expect(states[3].runs["root~1"].experiments.exp.artifacts).toEqual([]);
    expect(
      states[4].runs["root~1"].experiments.exp.artifacts[0].available_sequence,
    ).toBe(5);
    expect(states[2].runs["root~1"].experiments.exp.status).toBe("queued");
  });
  it("separates worker heartbeat from activity and retains attempt history", () => {
    const events = [
      event(1, "attempt.started"),
      event(2, "tool.started", { label: "Running experiment" }),
      event(3, "heartbeat"),
      event(4, "lifecycle", { lifecycle: "budget_exhausted" }),
      { ...event(5, "attempt.started"), attempt_id: "b" },
    ];
    const before = events.slice(0, 4).reduce(reduceRuntime, emptyRuntime());
    expect(before.runs.root.activity).toBeNull();
    const resumed = events.reduce(reduceRuntime, emptyRuntime());
    expect(resumed.runs.root.attempt_id).toBe("b");
    expect(
      resumed.runs.root.history.some(
        (e: RuntimeEvent) => e.payload.lifecycle === "budget_exhausted",
      ),
    ).toBe(true);
  });
});
