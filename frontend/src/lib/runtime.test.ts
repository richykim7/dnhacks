import { describe, expect, it } from "vitest";
import {
  emptyRuntime,
  reduceRuntime,
  runtimeCandidates,
  runtimeRunSummary,
  runtimeMilestones,
  type RuntimeEvent,
} from "./runtime";
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

describe("research projection", () => {
  it("counts candidate experiments once across retries, duplicate deliveries and playback", () => {
    const events = [
      event(1, "attempt.started"),
      event(2, "experiment.queued", {
        title: "Test the mechanism",
        status: "queued",
      }),
      event(3, "experiment.finished", {
        status: "completed",
        result: { effect: 2 },
      }),
      event(4, "experiment.reviewed", {
        verification: "CANDIDATE",
        submission_id: 7,
      }),
      event(5, "experiment.reviewed", {
        verification: "CANDIDATE",
        submission_id: 7,
      }),
      event(6, "experiment.submitted", {
        verification: "pending",
        submission_id: 8,
      }),
      event(7, "experiment.reviewed", {
        verification: "CANDIDATE",
        submission_id: 8,
      }),
      event(8, "experiment.human_reviewed", { human_review: "validated" }),
      {
        ...event(9, "experiment.reviewed", {
          verification: "CANDIDATE",
          submission_id: 8,
        }),
        experiment_id: "alias",
      },
    ];
    const at = (cursor: number) =>
      events.slice(0, cursor).reduce(reduceRuntime, emptyRuntime());
    expect(runtimeRunSummary(at(3).runs.root).candidateCount).toBe(0);
    expect(runtimeRunSummary(at(5).runs.root).candidateCount).toBe(1);
    expect(runtimeCandidates(at(6).runs.root)[0]).toMatchObject({
      experiment_id: "exp",
      verification: "pending",
      candidate_emitted: true,
    });
    expect(runtimeRunSummary(at(7).runs.root).acceptedCount).toBe(0);
    expect(runtimeRunSummary(at(8).runs.root).acceptedCount).toBe(1);
    expect(runtimeRunSummary(at(9).runs.root).candidateCount).toBe(1);
    expect(runtimeRunSummary(at(9).runs.root).acceptedCount).toBe(1);
    const state = at(8);
    expect(reduceRuntime(state, events[7])).toBe(state);
    expect(runtimeRunSummary(at(3).runs.root).candidateCount).toBe(0);
  });
  it("shows activity only with a fresh heartbeat and never animates replay", () => {
    const state = [
      event(1, "attempt.started"),
      event(2, "tool.started", { label: "Running analysis" }),
      event(3, "heartbeat"),
    ].reduce(reduceRuntime, emptyRuntime());
    expect(runtimeRunSummary(state.runs.root, 10)).toMatchObject({
      status: "running",
      freshActivity: true,
      elapsedSeconds: 9,
    });
    expect(runtimeRunSummary(state.runs.root, 40)).toMatchObject({
      status: "stale",
      freshActivity: false,
    });
    expect(runtimeRunSummary(state.runs.root, 1000, true)).toMatchObject({
      status: "running",
      freshActivity: false,
      elapsedSeconds: 2,
    });
    const idle = reduceRuntime(state, event(4, "tool.ended"));
    expect(runtimeRunSummary(idle.runs.root, 10)).toMatchObject({
      status: "idle",
      freshActivity: false,
    });
  });
  it("derives bounded major steps from public research records without output noise", () => {
    const state = [
      event(1, "intent", { intent: "Compare independent samples" }),
      event(2, "tool.started", { label: "Tool noise" }),
      event(3, "experiment.output", { text: "Raw output" }),
      event(4, "checkpoint.report", {
        report: {
          findings: [
            { claim: "Effect disappears in controls", references: ["exp"] },
          ],
          completed_work: ["Checked controls"],
          blockers: [],
        },
        costs: { ignored: 99 },
      }),
      event(5, "branch.decision", {
        decision: {
          action: "finish",
          reason: "Controls ruled out the hypothesis",
        },
      }),
    ].reduce(reduceRuntime, emptyRuntime());
    const steps = runtimeMilestones(state.runs.root);
    expect(steps.map((s) => s.title)).toEqual([
      "Branch decision",
      "Research checkpoint",
      "Research intent",
    ]);
    expect(steps[1].summary).toContain("Effect disappears in controls");
    expect(JSON.stringify(steps)).not.toContain("Raw output");
    expect(JSON.stringify(steps)).not.toContain("ignored");
  });
});
