"""Shared-ledger integration, replay equivalence and predictor filtration."""
import copy
import json
import threading
import urllib.request
import urllib.error

import numpy as np
import pytest
pytest.importorskip("torch")

from dnhacksbio.native_group_replay import PrivateGroupReplayStore, canonical_inputs
from dnhacksbio.native_evidence import PrivateProcessStore
from dnhacksbio.protein_experiment import Store, EvidenceUnavailable, release_check
from dnhacksbio.experiment_transport import make_server


def inputs():
    rng = np.random.default_rng(12)
    spec = {"method": "protein-group-native-v1", "null": "equal measured representations",
            "population": "synthetic independent normal draws", "panel_hash": "1"*64,
            "model_hash": "2"*64, "preprocessing_hash": "3"*64, "family": "f", "parent": "p",
            "sampling": "fresh IID simulated donors; fixed preprocessing", "exclusions": [], "seed": 0, "max_epochs": 1}
    a = {"donors": [f"a-{i}" for i in range(48)], "values": rng.normal(size=(48, 3)).tolist()}
    b = {"donors": [f"b-{i}" for i in range(48)], "values": rng.normal(size=(48, 3)).tolist()}
    return spec, a, b


def test_replay_aliases_rollback_and_exact_sets(tmp_path):
    s, a, b = inputs()
    store = PrivateGroupReplayStore(tmp_path / "ledger")
    store.register("first", s, a, b)
    def crash():
        raise RuntimeError("simulated interrupted write")
    with pytest.raises(RuntimeError):
        store.replay("first", before_commit=crash)
    with store.connect() as con:
        assert con.execute("SELECT count(*) FROM consumed").fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM blocks").fetchone()[0] == 0
    restarted = PrivateGroupReplayStore(tmp_path / "ledger")
    restarted.replay("first")
    first = restarted.export("first")
    reversed_a = {k: list(reversed(v)) for k,v in a.items()}
    reversed_b = {k: list(reversed(v)) for k,v in b.items()}
    restarted.register("release-alias", s, reversed_a, reversed_b)
    restarted.replay("release-alias")
    assert restarted.export("release-alias") == first
    assert first["metadata"]["scored_pairs"] == 32
    for u in first["unit_sets"]:
        tr, va, sc = ({x for pair in u[k] for x in pair} for k in ("training", "validation", "scoring"))
        assert not tr & va and not tr & sc and not va & sc
    with restarted.connect() as con:
        assert con.execute("SELECT count(*) FROM consumed").fetchone()[0] == 96
        assert con.execute("SELECT count(*) FROM blocks").fetchone()[0] == 4
    reference = PrivateGroupReplayStore(tmp_path / "reference")
    reference.register("first", s, a, b); reference.replay("first")
    assert reference.export("first") == first


def test_duplicates_tissue_swap_and_undersized_inputs():
    s,a,b = inputs()
    b["donors"][0] = a["donors"][0]
    with pytest.raises(ValueError, match="Repeated"):
        canonical_inputs(s,a,b)
    s,a,b = inputs()
    a["donors"].pop(); a["values"].pop()
    with pytest.raises(ValueError, match="48"):
        canonical_inputs(s,a,b)


def test_release_change_cannot_reset_global_consumption(tmp_path):
    s,a,b = inputs()
    store = PrivateGroupReplayStore(tmp_path)
    store.register("first",s,a,b); store.replay("first")
    b["values"][0][0] += .01
    store.register("changed-release", s,a,b)
    with pytest.raises(ValueError, match="consumed"):
        store.replay("changed-release")
    # Existing association core and group replay literally share the consumed table.
    core = PrivateProcessStore(tmp_path)
    with core.connect() as con:
        assert con.execute("SELECT count(*) FROM consumed").fetchone()[0] == 96


def test_unreleased_http_has_no_result_or_completion_surface(tmp_path):
    store = Store(tmp_path)
    server = make_server(store, port=0)
    thread = threading.Thread(target=server.serve_forever); thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        for path in ("/results", "/jobs", "/receipts/test"):
            with pytest.raises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(base+path)
            assert error.value.code == 404
            assert json.loads(error.value.read()) == {"error": "not found"}
        request = urllib.request.Request(base+"/experiments", data=b'{"request_id":"secret-value"}', method="POST")
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        assert json.loads(error.value.read()) == {"error": "submission not accepted"}
    finally:
        server.shutdown(); thread.join(); server.server_close()


def test_release_requires_evidence_and_distinct_service_identity():
    with pytest.raises(EvidenceUnavailable):
        release_check({"release": {"enabled": True}})


def test_frozen_future_preprocessing_cannot_change_after_registration(tmp_path):
    s,a,b = inputs()
    store = PrivateGroupReplayStore(tmp_path)
    store.register("first",s,a,b)
    # Simulate replacing frozen inputs with a future-cohort-fitted transform.
    with store.connect() as con:
        key,raw = con.execute("SELECT id,spec FROM processes").fetchone()
        frozen = json.loads(raw)
        frozen["groups"][0]["values"][0][0] += 1
        con.execute("UPDATE processes SET spec=? WHERE id=?", (json.dumps(frozen),key))
    with pytest.raises(ValueError, match="frozen"):
        store.replay("first")
    with store.connect() as con:
        assert con.execute("SELECT count(*) FROM consumed").fetchone()[0] == 0


def test_configured_private_worker_and_receipt_alias(tmp_path):
    import os
    s, a, b = inputs()
    ledger = tmp_path / "ledger"
    ledger.mkdir(mode=0o700)
    # Synthetic operator attestations exercise plumbing, not biological approval.
    reviews = {k: {"status": "approved", "artifact_sha256": "4"*64, "reviewer": "test-fixture"}
               for k in ("sampling", "preprocessing", "untouched_history", "canonical_identity", "privacy")}
    manifest = {"spec": s, "groups": [a,b], "ledger_directory": str(ledger),
                "release": {"reviews": reviews, "discovery_uid": os.getuid()+1,
                            "power_report": {"model_hash": s["model_hash"], "panel_hash": s["panel_hash"],
                                "alpha": .05, "null_streams": 10000, "pairs": 48,
                                "minimum_effect_power_lower95": .85, "anytime_null_upper95": .055}}}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    store = Store(tmp_path / "queue")
    registration = store.configure(path)
    first = store.enqueue({"request_id": "first", **registration})
    assert first == {"receipt": "first", "status": "accepted"}
    assert store.process_one(timeout=60)
    store.enqueue({"request_id": "alias", **registration})
    output = tmp_path / "export.json"
    store.export(output)
    report = json.loads(output.read_text())
    assert len(report["jobs"]) == 1
    assert report["jobs"][0]["status"] == "completed"
    assert report["jobs"][0]["result"]["metadata"]["scored_pairs"] == 32
    manifest["spec"]["seed"] = 1
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="frozen"):
        store.configure(path)
