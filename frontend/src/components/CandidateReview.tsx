import { useEffect, useState } from "react";
import { Check, X, ShieldCheck } from "lucide-react";
import { post, useResource } from "@/lib/api";
import type { JsonRecord } from "@/lib/types";
import { human, number } from "@/lib/utils";
import { Button } from "./ui/button";
import { Disclosure, ErrorNotice, Loading, Status } from "./common";
import "../candidate-review.css";

export default function CandidateReview({
  runId,
  experiment,
  project,
  cursor,
}: {
  runId: string;
  experiment: JsonRecord;
  project: string;
  cursor: number | null;
}) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<JsonRecord>();
  const params = new URLSearchParams({
    run: runId,
    experiment: experiment.experiment_id,
    ...(project ? { project } : {}),
  });
  const resource = useResource<JsonRecord>(
    open && cursor === null ? `/api/review/candidate?${params}` : null,
    10000,
  );
  useEffect(() => {
    if (resource.data) setSaved(undefined);
  }, [resource.data]);
  const card = saved || resource.data;
  const review = card?.test?.human_review || experiment.human_review;
  const pending = card?.pending;
  const label = pending
    ? `${pending.decision === "validated" ? "Acceptance" : "Rejection"} saved · awaiting application`
    : review === "validated"
      ? "Accepted by human review"
      : review === "rejected"
        ? "Rejected by human review"
        : "Awaiting human review";
  if (
    !experiment.candidate_emitted &&
    experiment.verification !== "CANDIDATE" &&
    !experiment.human_review
  )
    return null;
  async function decide(decision: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await post<JsonRecord>("/api/review/candidate", {
        run: runId,
        experiment: experiment.experiment_id,
        project: card?.project || project || undefined,
        decision,
        note: pending?.note || note,
      });
      setSaved(result);
      resource.refresh();
    } catch (e) {
      setError((e as Error).message);
      resource.refresh();
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="candidate-review" aria-label="Candidate review">
      <div className="candidate-review-heading">
        <ShieldCheck size={17} />
        <strong>Candidate review</strong>
        <Status
          label={label}
          tone={review === "rejected" ? "negative" : "attention"}
        />
      </div>
      {cursor !== null ? (
        <p className="muted">
          Recorded at this playback position. Return to Latest state to review
          this candidate.
        </p>
      ) : (
        <>
          <Button
            variant="secondary"
            size="sm"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? "Close review" : "Review candidate"}
          </Button>
          {open && (
            <div className="candidate-review-body">
              {resource.loading && !card && (
                <Loading label="Loading candidate evidence" />
              )}
              <ErrorNotice
                message={error || resource.error}
                retry={resource.refresh}
              />
              {card && (
                <>
                  <h4>
                    {card.test.hypothesis ||
                      experiment.title ||
                      "Candidate claim"}
                  </h4>
                  <p>
                    {card.test.subject} → {card.test.object} ·{" "}
                    {human(card.test.method)}
                  </p>
                  <p>
                    <strong>Automated verification:</strong>{" "}
                    {card.verification || experiment.verification}.{" "}
                    {card.verification_reason || card.test.verdict_note}
                  </p>
                  <dl className="measurements">
                    <div>
                      <dt>Effect</dt>
                      <dd>
                        {card.test.effect == null
                          ? "Not measured"
                          : number(card.test.effect)}
                      </dd>
                    </div>
                    <div>
                      <dt>Null-test p-value</dt>
                      <dd>
                        {card.test.p_null == null
                          ? "Not measured"
                          : number(card.test.p_null)}
                      </dd>
                    </div>
                  </dl>
                  <h4>Supporting evidence & limitations</h4>
                  {card.claim && (
                    <p>
                      {card.claim.subject_label} {human(card.claim.predicate)}{" "}
                      {card.claim.object_label}
                    </p>
                  )}
                  {card.evidence?.length ? (
                    card.evidence.map((e: JsonRecord, i: number) => (
                      <blockquote key={i}>
                        {e.quote || "No quotation recorded."}
                        <cite>
                          {e.source_label ||
                            e.source_ref ||
                            "Source not recorded"}
                        </cite>
                      </blockquote>
                    ))
                  ) : (
                    <p className="muted">
                      No linked literature evidence was recorded for this claim.
                      Inspect the experiment result and artifacts before
                      deciding.
                    </p>
                  )}
                  <p>
                    {card.test.novelty_detail ||
                      "Independent confirmation and study limitations are not established by automated candidate status."}
                  </p>
                  <Disclosure title="Supporting experiment result">
                    <pre>{JSON.stringify(card.result, null, 2)}</pre>
                  </Disclosure>
                  {card.code && (
                    <Disclosure title="Submitted analysis code">
                      <pre>{card.code}</pre>
                    </Disclosure>
                  )}
                  {(review || pending) && (
                    <div className="notice" role="status">
                      <strong>{label}</strong>
                      <p>
                        {card.test.review_note ||
                          pending?.note ||
                          experiment.human_review_note}
                      </p>
                      {pending?.recorded_at && (
                        <small>
                          Decision saved{" "}
                          {new Date(
                            pending.recorded_at * 1000,
                          ).toLocaleString()}
                        </small>
                      )}
                    </div>
                  )}
                  {card.message && <p role="status">{card.message}</p>}
                  {!review && !pending && (
                    <>
                      <label className="review-note">
                        Decision note (required)
                        <textarea
                          value={note}
                          onChange={(e) => setNote(e.target.value)}
                          rows={3}
                          maxLength={400}
                          placeholder="Explain the evidence supporting your decision and any limitations."
                        />
                      </label>
                      <p className="muted">
                        Accept promotes this candidate with its source records.
                        Reject records your correction. If the collection is
                        busy, your decision is saved for later application.
                      </p>
                      <div className="candidate-review-actions">
                        <Button
                          disabled={busy || !note.trim()}
                          onClick={() => void decide("validated")}
                        >
                          <Check size={15} />
                          {busy ? "Saving…" : "Accept"}
                        </Button>
                        <Button
                          variant="secondary"
                          disabled={busy || !note.trim()}
                          onClick={() => void decide("rejected")}
                        >
                          <X size={15} />
                          Reject
                        </Button>
                      </div>
                    </>
                  )}
                  {pending && (
                    <Button
                      disabled={busy}
                      onClick={() => void decide(pending.decision)}
                    >
                      {busy ? "Applying…" : "Apply saved decision"}
                    </Button>
                  )}
                </>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}
