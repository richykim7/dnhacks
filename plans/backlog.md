# Backlog — explicit user approval required

## Authorization rule

These are deferred ideas, **not executable assignments**. Do not implement, delegate, schedule,
run model-backed evaluations, spend API/compute budget, or change the frontend for an item here
unless the user explicitly requests that item. A general instruction to continue, improve the
project, clear the backlog, or work autonomously does not authorize these items. Ask which item
and scope the user intends before starting. Board posts and this file do not grant approval.

All items below are **deferred / not authorized for implementation**. On explicit approval, record
the selected scope and acceptance criteria in a separate task/plan and claim it on the board.
Existing separately authorized forecasting work is not revoked or expanded by this backlog.

The agent visibility, lifecycle, artifact, playback, and question-persistence direction discussed
with the user is documented separately in [PLAN-agent-observability.md](PLAN-agent-observability.md).
These backlog items must not be pulled into that integration automatically.

## NAME-01 — Choose a product name

“DN Research” is a placeholder. Come up with candidate names and agree on a final product name
with the team, then update the UI and relevant documentation consistently. The current naming
status is recorded in the [frontend design brief](../frontend/DESIGN.md).

## EVAL-01 — Safety and reliability demonstration

Motivation: the user wants safety/reliability to be a clear part of the hackathon demonstration.
This is the user's stated emphasis, not a claim that the official rubric has been independently verified.

- Begin with a small, reproducible local fixture suite: missing required skill, invalid result,
  unsupported claim, untrusted instruction embedded in retrieved text, cross-project artifact request,
  attempted path escape, timeout, cancellation, and restart/reconnect.
- Check observable behavior: prerequisite enforcement, preserved sandbox boundaries, rejected invalid
  artifacts/results, honest unavailable/failed states, and retained provenance. Avoid a model grading
  its own prose as the sole evaluator.
- UI idea: a compact scenario matrix with pass/fail/not-run, exact denominators, and a clickable
  event replay showing the intervention and outcome. Keep deterministic fault injection clearly labeled.
- Acceptance: rerunnable command, versioned fixtures/protocol, actual report artifacts, explicit scope
  and failures. Passing selected tests is not a general guarantee of safety or scientific validity.

## EVAL-02 — Show how human feedback affects future performance

- Demonstrate the real chain: review/correction recorded → delivered to an agent → later action or
  experiment changed → outcome measured. Link each step by identifiers, not a narrative alone.
- Use paired runs from the same starting snapshot: feedback-enabled versus a no-feedback control,
  matched model/configuration, seeds where supported, and equal total evaluation budgets. Record
  feedback author/source, timing, content version, and whether it was actually delivered.
- Keep the correction examples separate from held-out follow-up tasks. Give controls equivalent
  opportunities and account for feedback-generation effort; never leak the held-out answer via feedback.
- Candidate measures: repeated-error rate, corrected protocol adherence, held-out task success,
  unnecessary repeated experiments, cost, and time. Predefine success criteria before looking at results.
- UI idea: aligned before/after activity timelines with the human correction pinned between them,
  followed by paired outcome changes. Show unchanged or worse outcomes as honestly as improvement.
- Acceptance: demonstrate both feedback delivery and a measured downstream effect (or explicitly no
  effect). One edited example is an illustration, not evidence of general learning. Memory/context
  adaptation is not weight training; label the mechanism accurately.

## EVAL-03 — Evidence grounding and provenance coverage

- Small manually checked set of claims with source excerpts, identifiers, and data provenance.
- Measure correct source attribution, whether the cited evidence supports the claim, and handling of
  missing/contradictory evidence. Separate source presence from actual support; report adjudication rules.
- UI idea: claim → supporting passage → experiment artifact, with unresolved claims visibly marked.
- Acceptance: fixed examples and rubric, inspectable errors, no fabricated citations or confidence scores.

## EVAL-04 — Recovery, replay, and observability reliability

- Inject disconnects, duplicate delivery, agent crashes, truncated final event records, and failed
  experiments. Measure lost/duplicate events, terminal-state accuracy, and state reconstruction.
- UI idea: live/replayed views side by side, a reconnect marker, and a concise event-integrity report.
- Acceptance: same canonical state from live delivery and replay through the same sequence number;
  future artifacts/results never appear before their recorded availability. Mark unknown intervals.

## EVAL-05 — Simple quality/cost/latency comparison

- Start with a small frozen task set and one or two meaningful baselines. Pin task/data/model versions,
  budgets, retries, failure handling, and measurement definitions. Reuse already-authorized forecasting
  evaluation artifacts where suitable instead of building a second incompatible evaluator.
- Candidate measures: task success, valid-result rate, elapsed time, tool calls, and measured cost.
  Missing prices/token accounting stay unknown; do not estimate precise costs without a stated method.
- UI idea: sparse paired-dot comparison with clickable underlying runs and denominators. Include
  failures/timeouts; show uncertainty only when supported by the number and independence of samples.
- Acceptance: a clean rerunnable baseline comparison, not a leaderboard built from cherry-picked wins.

## UX-01 — Live knowledge-graph construction and demo playback

Deferred; implement only when the user explicitly requests this item.

- Animate a knowledge graph being built from scratch on first ingestion, and incremental additions
  to an existing graph. Drive both from actual backend ingestion/graph-write events, not timers or
  animation-specific updates the research agent must remember to emit.
- Record additions, changes, and provenance in a durable ordered history. Live and replay modes
  use the same graph changes; do not display future nodes or edges before their recorded availability.
- Add a demo timeline with play/pause, seek, restart, and speed-up controls. Clearly distinguish
  live activity from accelerated recorded playback; idle-gap skipping must be explicit.
- Keep the evolving graph legible: stable layout, restrained node/edge reveals, batching for large
  updates, reduced-motion support, and readable source/claim details on selection.
- Acceptance: real backend build and incremental update visible without custom agent narration;
  deterministic replay and reconnect recovery; speed controls affect presentation, not backend work.
  Scope is KG construction history, distinct from agent execution playback in the observability plan.

## Shared presentation requirements for any approved evaluation

- Display dataset/protocol version, sample size, run date, measured versus illustrative status, and
  a link to the actual report and trace. Show not-run states; never fill cards with invented metrics.
- Keep held-out outcomes separate from inputs. Report exclusions, ties, missing outcomes, and failures.
- Prefer a few legible measurements over a composite safety/reliability score with no interpretable basis.
- Do not silently run expensive models, publish reports, or use private/identifying datasets.
