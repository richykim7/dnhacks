import asyncio
import copy
import json
import math
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from dnhacksbio.branch_monitoring import statistics as S
from dnhacksbio.branch_monitoring.store import MonitorStore, digest
from dnhacksbio.branch_monitoring.worker import prefix_at, score_pending
from dnhacksbio.branch_monitoring.server import make_server
from dnhacksbio.explorer.runtime import Journal
from test_branch_control import report


def protocol():
    return dict(policy_id="pilot-v1", rubric="new, relevant, verified, nonduplicate, supported finding",
                verifier_model="test-fake", verifier_prompt_version="subtree-prefix-v1", corpus_hash="fixture",
                budget_unit="research_actions", terminal_budget=80, disclosure_boundary="after-frozen-study",
                sampling_policy="preselect-first-child-v1")


def enroll(s, run="r~1", eid="e", group="g"):
    return s.enroll(episode_id=eid, run_id=run, root_id="r", group_id=group, objective="Check mechanism",
                    initial_evidence=["old"], protocol=protocol(), start_sequence=0, calibration_unit=True)


def evidence(run="r~1~2", finding="new"):
    return dict(run_id=run, finding_id=finding, verified=True, relevant=True, nonduplicate=True,
                evidence_supported=True, artifact_refs=["immutable-artifact"])


PROVENANCE = {"assessor": "frozen-test-rubric", "artifact_refs": ["complete-continuation-audit"]}


def test_descendant_success_preexisting_and_duplicates(tmp_path):
    s = MonitorStore(tmp_path)
    enroll(s)
    result = s.close("e", termination="natural_finish", evidence=[evidence()], provenance=PROVENANCE)
    assert result["outcome"] == "success"
    assert result["label_provenance"]["evidence"][0]["run_id"] == "r~1~2"
    with pytest.raises(ValueError, match="immutable"):
        s.close("e", termination="budget_endpoint", provenance=PROVENANCE)
    enroll(s, eid="e2", group="g2")
    assert s.close("e2", termination="budget_endpoint", evidence=[evidence(finding="old")], provenance=PROVENANCE)["outcome"] == "unsuccessful"
    enroll(s, eid="e3", group="g3")
    f = evidence(); f["nonduplicate"] = False
    assert s.close("e3", termination="natural_finish", evidence=[f], provenance=PROVENANCE)["outcome"] == "unsuccessful"


def test_incomplete_pending_and_foreign_evidence(tmp_path):
    s = MonitorStore(tmp_path); enroll(s)
    with pytest.raises(ValueError, match="outside"):
        s.close("e", termination="natural_finish", evidence=[evidence("r~2")], provenance=PROVENANCE)
    assert s.close("e", termination="infrastructure_failure", provenance=PROVENANCE)["outcome"] == "censored"
    enroll(s, eid="e2", group="g2")
    assert s.close("e2", termination="budget_endpoint", pending_verification=True, provenance=PROVENANCE)["outcome"] == "pending"
    assert s.close("e2", termination="budget_endpoint", evidence=[evidence()], provenance=PROVENANCE)["outcome"] == "success"


def test_frozen_horizon_and_prefix_future_boundary(tmp_path):
    s = MonitorStore(tmp_path); enroll(s)
    with pytest.raises(ValueError, match="frozen"):
        s.enroll(episode_id="e", run_id="r~1", root_id="r", group_id="g", objective="Changed objective",
                 initial_evidence=[], protocol=protocol(), start_sequence=0, calibration_unit=True)
    p = dict(through_sequence=2, events=[], report=report(), report_version=1)
    c = s.append_checkpoint("e", p, cost=3, verifier_score=.7)
    assert c["remaining_budget"] == 77
    assert s.append_checkpoint("e", p, cost=3, verifier_score=.7) == c
    with pytest.raises(ValueError, match="immutable"):
        s.append_checkpoint("e", p, cost=4, verifier_score=.8)
    p2 = dict(p, report_version=2, through_sequence=3, events=[{"sequence":4}])
    with pytest.raises(ValueError, match="Future"):
        s.append_checkpoint("e", p2, cost=5, verifier_score=.7)
    p2["events"] = []
    with pytest.raises(ValueError, match="endpoint"):
        s.append_checkpoint("e", p2, cost=81, verifier_score=.7)


def test_worker_prefix_and_no_private_writeback(tmp_path):
    s = MonitorStore(tmp_path / "private"); ep = enroll(s)
    j = Journal(tmp_path / "public")
    j.register("r", "Root"); j.register("r~1", "Root")
    j.append("r~1", "a", "tool.started", {"action": "search_kg", "inputs": j.blob('{"query":"A"}')})
    e = j.append("r~1", "a", "checkpoint.report", {"version":1,"report":report(),"costs":{}})
    j.append("r~1", "a", "human.decision", {"private_confirmation":"DO-NOT-INCLUDE"})
    j.append("r~1", "a", "tool.ended", {"action":"search_kg", "observation":j.blob("FUTURE-EVIDENCE")})
    prefix = prefix_at(j, ep, e)
    assert "FUTURE-EVIDENCE" not in json.dumps(prefix) and "DO-NOT-INCLUDE" not in json.dumps(prefix)
    before = j.events("r")
    prompts = []
    async def verifier(p):
        prompts.append(p); return '{"score":0.731234}'
    assert asyncio.run(score_pending(s, j, complete_fn=verifier))["recorded"] == 1
    assert asyncio.run(score_pending(s, j, complete_fn=verifier))["recorded"] == 0
    assert j.events("r") == before
    assert "0.731234" not in json.dumps(before)
    assert "FUTURE-EVIDENCE" not in prompts[0]
    assert s.export()[0]["scores"] == [.731234]


def episode(i, outcome, scores, group=None):
    return dict(root_id=f"r{i}", group_id=group or f"g{i}", episode_id=f"e{i}", outcome=outcome,
                scores=scores, calibration_unit=True, protocol_hash="p")


def model():
    return S.fit([episode(1, "success", [.8,.9]), episode(2,"unsuccessful",[.2,.1])], "p")


def test_paper_threshold_sample_size_order_ties_and_strictness():
    assert S.pac_threshold([1.] * 115) is None
    assert S.pac_threshold(list(range(116))) == 115
    assert S.pac_threshold([1.] * 116) == 1
    # Small exactly enumerable binomial: n=5, alpha=.5, delta=.2 -> k=4, tail=6/32.
    assert S.pac_threshold([1,2,3,4,5], .5, .2) == 4
    for x in (math.nan, -1, math.inf):
        with pytest.raises(ValueError): S.pac_threshold([x])


def test_history_ratio_orientation_unsupported_length_and_missing():
    m = model()
    assert S.history_values(m,[.1,.1])[-1] > S.history_values(m,[.9,.9])[-1]
    assert S.history_values(m,[.8,None])[-1] is None
    assert S.history_values(m,[.8,.9,.8])[-1] is None


def test_group_separation_and_correlated_checkpoints_do_not_supply_units():
    m = model()
    with pytest.raises(ValueError, match="leakage"):
        S.calibrate(m, [episode(1,"success",[.8,.9])])
    c = S.calibrate(m, [episode(3,"success",[.8,.9])])
    assert c["successful_units"] == 1 and c["threshold"] is None and c["counts"]["checkpoints"] == 2
    with pytest.raises(ValueError, match="one preselected"):
        S.calibrate(m, [episode(3,"success",[.8,.9]), episode(4,"success",[.8,.9],group="g3")])
    with pytest.raises(ValueError, match="leakage"):
        S.evaluate(m,c,[episode(3,"success",[.9,.9])])
    altered = copy.deepcopy(m); altered["lengths"]["1"]["coefficients"][0] += 1
    with pytest.raises(ValueError, match="different"):
        S.evaluate(altered,c,[episode(5,"success",[.9,.9])])
    result = S.evaluate(m,c,[episode(5,"success",[.9,.9]),episode(6,"unsuccessful",[.1,.1])])
    assert result["methods"]["direct_verifier"]["detected_unsuccessful"] == 1
    assert result["methods"]["history_ratio"]["threshold"] is None


def test_private_reviews_no_feedback_or_universal_threshold(tmp_path):
    s = MonitorStore(tmp_path)
    association = dict(receipt="receipt",run_id="r~1",experiment_id="x",finding_id="finding",method_id="method",
        null="declared null",validity_policy="frozen method-specific family",evidence={"e_value":100.},
        provenance={"input_digest":"hash"},disclosure_boundary="study-end")
    r = s.associate_review(**association)
    assert r["decision"] is None
    with pytest.raises(ValueError): s.review(r["review_id"],"accepted","")
    s.review(r["review_id"],"accepted","Evidence and limitations inspected")
    assert s.associate_review(**association)["decision"] == "accepted"
    with pytest.raises(PermissionError): s.disclosure_export("study-end")
    assert not s.disclosure_export("different", authorized=True)
    assert s.disclosure_export("study-end",authorized=True)[0]["disclosed"] is True


def test_operator_authorization_no_cors_and_public_shell_contains_no_scores(tmp_path):
    s = MonitorStore(tmp_path); enroll(s)
    token = "test-only-operator-token-" + "x" * 32
    server = make_server(s, token, port=0)
    thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with pytest.raises(HTTPError) as err: urlopen(base+"/api/episodes")
        assert err.value.code == 401
        with urlopen(base) as r: assert "Check mechanism" not in r.read().decode()
        with urlopen(Request(base+"/api/episodes",headers={"Authorization":"Bearer "+token})) as r:
            assert not r.headers.get("Access-Control-Allow-Origin")
            assert json.load(r)["episodes"][0]["objective"] == "Check mechanism"
    finally:
        server.shutdown();server.server_close();thread.join()


def test_receipt_adapter_joins_canonical_evidence_without_scoring(tmp_path):
    import sqlite3
    from dnhacksbio.branch_monitoring.receipts import import_receipt
    queue = tmp_path / "queue"; queue.mkdir()
    with sqlite3.connect(queue / "scoring.sqlite3") as c:
        c.executescript("CREATE TABLE jobs(receipt TEXT,digest TEXT,payload TEXT,status TEXT,result TEXT); CREATE TABLE aliases(receipt TEXT,canonical TEXT);")
        c.execute("INSERT INTO jobs VALUES (?,?,?,?,?)", ("original","input-hash",json.dumps({"spec":{"method_id":"method","experiment_id":"x"}}),"completed",json.dumps({"e_value":12.})))
        c.execute("INSERT INTO aliases VALUES ('retry','original')")
    s=MonitorStore(tmp_path / "private")
    kwargs=dict(run_id="r~1",experiment_id="x",finding_id="f",method_id="method",null="frozen-null",validity_policy="family-v1",disclosure_boundary="end")
    row=import_receipt(s,queue,"retry",**kwargs)
    assert row["association"]["receipt"] == "original" and row["decision"] is None
    assert import_receipt(s,queue,"original",**kwargs)["review_id"] == row["review_id"]
    with pytest.raises(ValueError,match="unavailable"):
        import_receipt(s,queue,"missing",**kwargs)
    with pytest.raises(ValueError,match="mismatch"):
        import_receipt(s,queue,"retry",**dict(kwargs,experiment_id="foreign"))


def test_verifier_failure_is_missing_not_zero_or_negative(tmp_path):
    s=MonitorStore(tmp_path / "private");enroll(s)
    j=Journal(tmp_path / "public");j.register("r", "Root")
    j.append("r~1","a","checkpoint.report",{"version":1,"report":report(),"costs":{}})
    async def failure(_): raise RuntimeError("private-output-must-not-leak")
    asyncio.run(score_pending(s,j,complete_fn=failure))
    row=s.checkpoints("e")[0]
    assert row["verifier_score"] is None and row["monitor_statistic"] is None
    assert row["error"] == "verifier_unavailable"
    assert "private-output-must-not-leak" not in json.dumps(s.export())
    assert s.episode("e")["outcome"] == "unknown"


def test_worker_database_handle_is_read_only(tmp_path):
    import sqlite3
    from dnhacksbio.branch_monitoring.worker import ReadOnlyJournal
    j=Journal(tmp_path);j.register("r","Question")
    reader=ReadOnlyJournal(tmp_path,create=False)
    assert reader.manifest("r")["original_question"] == "Question"
    with pytest.raises(sqlite3.OperationalError): reader.append("r","a","intent",{"intent":"Must not write"})
