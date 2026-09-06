"""Async verification handoff between exploration (fast, self-judged) and verification (slow, strict).

The explorer `submit()`s an experiment it judged good and keeps exploring. A worker `drain()`s the queue
and runs the falsifier on each submission, then writes the verdicts back to the graph and the promotion
queue. Verdict feedback to the explorer names the failure kind (see falsifier.KILL_KIND). The code
that produced every number is stored on the submission so a human at the promotion gate can audit it.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from dnhacksbio.explorer import lineage as LIN
from dnhacksbio.falsifier import Falsifier, kind_of_kill
from dnhacksbio.litmap.store import KGStore
from dnhacksbio.methods import ToolResult


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# A fixable or indecisive test, worth another attempt. Keyed on the falsifier's stable slugs.
_RETRY_REASONS = {"no-effect", "malformed-p", "too-few-units", "not-robust"}


def _feedback_status(status: str, reason: str, note: str) -> str:
    """Map a verifier verdict to the tree-search action the explorer takes on that branch: candidate ->
    promising; a fixable/indecisive test -> needs-retry; a flipped direction -> reframe (the inverse is a
    lead); non-significant -> dead (prune)."""
    if status == "CANDIDATE":
        return "promising"
    r = (reason or "").strip().lower()
    if r == "direction-wrong":
        return "reframe"
    if r in _RETRY_REASONS:
        return "needs-retry"
    return "dead"


class VerifyQueue:
    def __init__(self, db_path: str | Path | None = None, kg: KGStore | None = None):
        # Share one KGStore connection so the queue, graph, papers and log are one DB (writeback lands
        # where the explorer and promotion read). Pass `kg` to attach to an existing store; else create one.
        self._owns_kg = kg is None
        self.kg = kg or KGStore(db_path)
        self.con = self.kg.con
        self.db_path = self.kg.db_path
        self._schema()

    def _schema(self) -> None:
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS verification_queue (
                submission_id BIGINT PRIMARY KEY,
                run_id VARCHAR, status VARCHAR,          -- queued | verified | failed
                source VARCHAR,
                hypothesis VARCHAR, subject VARCHAR, object VARCHAR, method VARCHAR,
                expected_sign INTEGER, kg_claim_id VARCHAR,
                result_json VARCHAR,                     -- {effect, p_null, null_model, n_units, robust, dataset}
                code VARCHAR,                            -- the code that produced it (auditable)
                provenance VARCHAR,
                verdict VARCHAR, reason VARCHAR,
                submitted_at VARCHAR, processed_at VARCHAR
            )""")

    # --- explorer side ----------------------------------------------------------------------------
    def submit(self, *, run_id: str, hypothesis: str, subject: str, object: str, method: str,
               expected_sign: int, result: dict, code: str = "", kg_claim_id: str = "",
               provenance: dict | None = None, source: str = "explorer") -> int:
        """The explorer drops a self-judged experiment. `result` carries the standardized fields the
        falsifier needs (effect, p_null, null_model, n_units, robust)."""
        sid = int(self.con.execute(
            "SELECT COALESCE(MAX(submission_id),0)+1 FROM verification_queue").fetchone()[0])
        self.con.execute("INSERT INTO verification_queue "
                         "(submission_id,run_id,status,source,hypothesis,subject,object,method,expected_sign,"
                         "kg_claim_id,result_json,code,provenance,verdict,reason,submitted_at,processed_at) "
                         "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         [sid, run_id, "queued", source, hypothesis, str(subject), str(object), method,
                          int(expected_sign or 0), kg_claim_id, json.dumps(result or {}), code,
                          json.dumps(provenance or {}), "", "", _now(), ""])
        return sid

    def pending(self, run_id: str | None = None) -> list[dict]:
        """Queued submissions for a whole investigation tree. The worker is started with the root run_id
        but a forked branch submits under its own path-encoded id (`root~1`), so scope on `lineage.tree_sql`
        rather than exact equality."""
        w, params = "WHERE status='queued'", []
        if run_id:
            frag, params = LIN.tree_sql(run_id)
            w += f" AND {frag}"
        cols = ("submission_id", "run_id", "hypothesis", "subject", "object", "method", "expected_sign",
                "kg_claim_id", "result_json", "code", "provenance")
        rows = self.con.execute(f"SELECT {','.join(cols)} FROM verification_queue {w} ORDER BY submission_id",
                                params).fetchall()
        out = []
        for r in rows:
            d = dict(zip(cols, r))
            d["result"] = json.loads(d.pop("result_json") or "{}")
            d["provenance"] = json.loads(d.get("provenance") or "{}")
            out.append(d)
        return out

    def adjudicated(self, run_id: str, *, verdict: str = "CANDIDATE", limit: int = 40) -> list[dict]:
        """Every adjudicated result in this investigation tree, most recent first: the lossless upward
        channel. A node synthesizing after a fork sees only digest prose for its direct children, so deeper
        verified findings are read from here directly. These are adjudicated outputs, not a sibling's
        working memory, so reading them does not breach branch isolation."""
        frag, params = LIN.tree_sql(run_id)
        rows = self.con.execute(
            f"SELECT run_id, hypothesis, verdict FROM verification_queue "
            f"WHERE {frag} AND verdict = ? ORDER BY submission_id DESC LIMIT ?",
            [*params, verdict, int(limit)]).fetchall()
        return [{"run_id": r[0], "hypothesis": r[1], "verdict": r[2]} for r in rows]

    # --- worker side ------------------------------------------------------------------------------
    def _publish_verified(self, run_id: str) -> None:
        """Recoverable publication from the durable queue; event IDs make retries idempotent.

        This records the verifier's assessment, not human confirmation or graph promotion.
        Legacy queues without a runtime association retain their existing behavior.
        """
        journal = getattr(self, "runtime_journal", None)
        if journal is None:
            return
        frag, params = LIN.tree_sql(run_id)
        rows = self.con.execute("SELECT submission_id,run_id,provenance,verdict,reason FROM verification_queue "
                                f"WHERE status='verified' AND {frag}", params).fetchall()
        for sid, rid, raw, verdict, reason in rows:
            prov = json.loads(raw or "{}")
            if not prov.get("experiment_id") or not prov.get("attempt_id"):
                continue
            try:
                journal.append(rid, prov["attempt_id"], "experiment.reviewed",
                               {"verification": verdict, "verification_reason": reason,
                                "submission_id": sid}, experiment_id=prov["experiment_id"],
                               producer="verifier", event_id=f"verification-{rid}-{sid}")
            except Exception:
                journal.degraded = True
                raise

    @staticmethod
    def _toolresult(row: dict) -> ToolResult:
        res = row["result"]
        return ToolResult(
            tool=row["method"], effect=res.get("effect"), p_null=float(res.get("p_null", 1.0)),
            null_model=res.get("null_model", ""), n_units=int(res.get("n_units", 0) or 0),
            expected_sign=int(row["expected_sign"] or 0),
            robust=bool(res.get("robust", True)),
            trust_class="audited-statistic",   # an experiment that follows the rigor skill is the audited statistic
            dataset=res.get("dataset", ""), method=res.get("method", row["method"]))

    def drain(self, run_id: str, *, falsifier: Falsifier | None = None) -> list[dict]:
        """Process every queued submission for a run: local soundness (direction, null, robustness), and
        write verdicts back to the working graph. Returns the verdict dicts."""
        fal = falsifier or Falsifier()
        self._publish_verified(run_id)
        rows = self.pending(run_id)
        if not rows:
            return []
        trs = [self._toolresult(r) for r in rows]

        kg = self.kg
        elog = None
        results = []
        for row, tr in zip(rows, trs):
            ok, reason, note = fal.soundness_floor_tool(tr)
            cls = None if ok else kind_of_kill(reason)
            fb_note = note if ok else f"[{cls}] {note}"        # the factual class only
            explore_entry = (row.get("provenance") or {}).get("exploration_entry")
            # Stamp the branch that produced this, not the root: engine_tests is idempotent on
            # (run_id, subject, object, method, expected_sign), and two branches testing the same thing
            # must both be kept.
            rec = {"run_id": row["run_id"],
                   "status": "CANDIDATE" if ok else "KILL", "reason": (None if ok else reason),
                   "verdict_note": fb_note, "subject": row["subject"], "object": row["object"],
                   "method": row["method"], "effect": tr.effect,
                   "p_null": tr.p_null, "expected_sign": tr.expected_sign,
                   "observed_sign": tr.observed_sign, "hypothesis": row["hypothesis"],
                   "kg_claim_id": row["kg_claim_id"], "source": "explorer", "claim_id": "",
                   "explore_entry": explore_entry}
            results.append(rec)
            self.con.execute(
                "UPDATE verification_queue SET status='verified', verdict=?, reason=?, "
                "processed_at=? WHERE submission_id=?",
                [rec["status"], rec["reason"] or "", _now(), row["submission_id"]])
            # fold the verdict back onto the explorer's experiment entry (retry / reframe / prune next roam).
            if explore_entry:
                if elog is None:
                    from dnhacksbio.explorer.exploration import ExplorationLog
                    elog = ExplorationLog(con=self.kg.con)
                elog.record_feedback(int(explore_entry), source="verifier", verdict=rec["status"],
                                     reason=rec["reason"] or "", note=fb_note,
                                     new_status=_feedback_status(rec["status"], rec["reason"] or "", note))
        kg.write_back(results, run_id=run_id)
        self._publish_verified(run_id)
        return results

    def counts(self) -> dict:
        rows = self.con.execute("SELECT status, COUNT(*) FROM verification_queue GROUP BY status").fetchall()
        return dict(rows)

    def close(self) -> None:
        if self._owns_kg:
            self.kg.close()
