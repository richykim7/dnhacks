"""Additive import checks use disposable, synthetic local state only."""
import importlib.util
import json
from pathlib import Path

import pytest

from dnhacksbio.explorer.runtime import Journal
from dnhacksbio.webui.deployment import Busy, lease

SPEC = importlib.util.spec_from_file_location("presentation_import", Path(__file__).parents[1] / "scripts/import_presentation.py")
importer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(importer)


@pytest.fixture
def bundle(tmp_path):
    source, destination = tmp_path / "staged", tmp_path / "app"
    project = source / "projects/example"
    project.mkdir(parents=True)
    (project / "kg.duckdb").write_bytes(b"private graph fixture")
    (project / "project.json").write_text(json.dumps(dict(id="example", presentation_only=True,
        adopted=False, runs=["sample"], kg_db=str(project / "kg.duckdb"))))
    journal = Journal(source / "processed")
    journal.register("sample", "Example question", project="example")
    journal.append("sample", "attempt", "attempt.started", event_id="example-start")
    reference = journal.blob("example output")
    journal.append("sample", "attempt", "experiment.output", dict(output=reference), event_id="example-output")
    journal.append("sample", "attempt", "lifecycle", dict(lifecycle="completed"), event_id="example-end")
    return source, destination, journal, reference


def run(bundle, **kwargs):
    source, destination, _, _ = bundle
    return importer.import_bundle(source, destination, "example", "sample", **kwargs)


def test_dry_run_never_creates_destination(bundle):
    result = run(bundle)
    assert result["action"] == "new" and result["events"] == 3 and not result["applied"]
    assert not bundle[1].exists()


def test_additive_import_preserves_other_project_and_active_journal(bundle):
    _, destination, _, reference = bundle
    existing = Journal(destination / "processed")
    existing.register("ongoing", "Unrelated work", project="other")
    existing.append("ongoing", "active", "attempt.started", event_id="unrelated-start")
    before = existing.events("ongoing")
    control = destination / "processed/control.sqlite3"
    control.write_bytes(b"do not replace")
    other = destination / "projects/other/kg.duckdb"
    other.parent.mkdir(parents=True)
    other.write_bytes(b"other graph")
    assert run(bundle, apply=True)["action"] == "new"
    assert existing.events("ongoing") == before
    assert len(existing.events("sample")) == 3
    assert control.read_bytes() == b"do not replace" and other.read_bytes() == b"other graph"
    assert existing.read_blob(reference["storage_key"]) == b"example output"
    project = destination / "projects/example"
    assert json.loads((project / "project.json").read_text())["kg_db"] == str(project / "kg.duckdb")


def test_idempotent_after_private_review_changes(bundle):
    run(bundle, apply=True)
    _, destination, _, _ = bundle
    journal = Journal(destination / "processed", create=False)
    journal.append("sample", "attempt", "experiment.human_reviewed", dict(human_review="rejected"),
                   producer="human-review", event_id="human-review-new")
    graph = destination / "projects/example/kg.duckdb"
    graph.write_bytes(b"private graph updated by human review")
    assert run(bundle, apply=True)["action"] == "noop"
    assert graph.read_bytes() == b"private graph updated by human review"
    assert len(journal.events("sample")) == 4


def test_changed_source_conflicts_with_existing_import(bundle):
    run(bundle, apply=True)
    (bundle[0] / "projects/example/kg.duckdb").write_bytes(b"changed bundle")
    with pytest.raises(ValueError, match="conflicts"):
        run(bundle, apply=True)


def test_unrelated_project_name_is_never_overwritten(bundle):
    target = bundle[1] / "projects/example"
    target.mkdir(parents=True)
    (target / "project.json").write_text('{}')
    with pytest.raises(ValueError, match="without this import receipt"):
        run(bundle, apply=True)
    assert (target / "project.json").read_text() == '{}'


def test_event_id_collision_aborts_before_copy(bundle):
    journal = Journal(bundle[1] / "processed")
    journal.register("other", "Other", project="other")
    journal.append("other", "other", "attempt.started", event_id="example-start")
    with pytest.raises(ValueError, match="Event identifier collision"):
        run(bundle, apply=True)
    assert not (bundle[1] / "projects/example").exists()


def test_corrupt_blob_and_nonterminal_run_are_rejected(bundle):
    source, destination, journal, reference = bundle
    path = source / "processed/runtime/blobs" / reference["storage_key"]
    path.write_bytes(b"different bytes")
    with pytest.raises(ValueError, match="Blob byte length|content does not match"):
        run(bundle)
    path.write_bytes(b"example output")
    journal.append("sample", "resumed", "attempt.started")
    with pytest.raises(ValueError, match="terminal final lifecycle"):
        run(bundle)
    assert not destination.exists()


def test_graph_symlink_and_hardlink_are_rejected(bundle, tmp_path):
    graph = bundle[0] / "projects/example/kg.duckdb"
    original = tmp_path / "shared.duckdb"
    graph.rename(original)
    graph.symlink_to(original)
    with pytest.raises(ValueError, match="private regular file"):
        run(bundle)
    graph.unlink()
    graph.hardlink_to(original)
    with pytest.raises(ValueError, match="private regular file"):
        run(bundle)


def test_interrupted_journal_registration_can_resume(bundle, monkeypatch):
    insert = importer.insert_records
    def interrupted(con, data):
        con.execute("INSERT INTO manifests VALUES (?,?,?,?)", data["manifests"][0])
        raise RuntimeError("simulated interruption")
    monkeypatch.setattr(importer, "insert_records", interrupted)
    with pytest.raises(RuntimeError, match="interruption"):
        run(bundle, apply=True)
    assert (bundle[1] / "projects/example" / importer.RECEIPT).exists()
    assert Journal(bundle[1] / "processed", create=False).manifests() == []
    monkeypatch.setattr(importer, "insert_records", insert)
    assert run(bundle, apply=True)["action"] == "recover"
    assert run(bundle, apply=True)["action"] == "noop"


def test_deployment_lease_blocks_apply_but_not_dry_run(bundle, tmp_path):
    home = tmp_path / "installation"
    with lease(exclusive=True, path=home / "research.lock"):
        assert run(bundle, deployment_home=home)["applied"] is False
        with pytest.raises(Busy):
            run(bundle, apply=True, deployment_home=home)
    assert not bundle[1].exists()


def test_scoped_source_journal_rejects_another_investigation(bundle):
    bundle[2].register("elsewhere", "Outside scope", project="example")
    with pytest.raises(ValueError, match="outside the requested"):
        run(bundle)


def test_only_referenced_blobs_are_copied(bundle):
    extra = bundle[2].blob("unreferenced staging output")
    run(bundle, apply=True)
    assert not (bundle[1] / "processed/runtime/blobs" / extra["storage_key"]).exists()


def test_resumed_imported_run_is_not_treated_as_matching_review(bundle):
    run(bundle, apply=True)
    journal = Journal(bundle[1] / "processed", create=False)
    journal.append("sample", "resumed", "attempt.started")
    with pytest.raises(ValueError, match="Only scoped human review"):
        run(bundle)


def test_missing_imported_blob_is_not_silent_success(bundle):
    run(bundle, apply=True)
    (bundle[1] / "processed/runtime/blobs" / bundle[3]["storage_key"]).unlink()
    with pytest.raises(ValueError, match="missing a referenced"):
        run(bundle)
