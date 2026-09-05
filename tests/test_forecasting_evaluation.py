"""Ranking arithmetic, cohort integrity, and sealed outcome boundaries."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from dnhacksbio.forecasting.evaluation import compare_forecasts, evaluate_forecasts


def rows(labels=(True, False, True, False), scores=(0.9, 0.8, 0.7, 0.6), queries=None):
    queries = queries or ["q1"] * len(labels)
    candidates = [{"id": f"c{i}", "source": "gene", "target": f"drug{i}", "query_id": query}
                  for i, query in enumerate(queries)]
    forecasts = [{"candidate_id": f"c{i}", "score": score} for i, score in enumerate(scores)]
    outcomes = [{"candidate_id": f"c{i}", "observed": label,
                 "evidence_ids": [f"later-{i}"] if label else []}
                for i, label in enumerate(labels)]
    return candidates, forecasts, outcomes


def test_known_ranking_and_hit_miss_artifacts():
    result = evaluate_forecasts(*rows(), ks=(2, 10))
    metrics = result["overall"]
    assert metrics["average_precision"] == pytest.approx(5 / 6)
    assert metrics["auroc"] == pytest.approx(3 / 4)
    assert metrics["at_k"]["2"] == {
        "requested_k": 2, "eligible_candidates": 4, "selected_count": 2,
        "precision_denominator": 2, "hits": 1, "precision": .5, "recall": .5,
        "selected_ids": ["c0", "c1"], "hit_ids": ["c0"],
        "unobserved_ids": ["c1"], "missed_ids": ["c2"],
    }
    assert metrics["at_k"]["10"]["precision_denominator"] == 4
    assert metrics["at_k"]["10"]["precision"] == .5
    assert result["ranking"][0]["outcome_evidence_ids"] == ["later-0"]


def test_ties_are_half_credit_auc_and_threshold_ap_independent_of_row_order():
    candidates, forecasts, outcomes = rows(scores=(1, 1, 1, 1))
    result = evaluate_forecasts(candidates, forecasts, outcomes, ks=(1,))
    assert result["overall"]["auroc"] == .5
    assert result["overall"]["average_precision"] == .5
    assert result["overall"]["at_k"]["1"]["selected_ids"] == ["c0"]
    assert evaluate_forecasts(candidates[::-1], forecasts[::-1], outcomes[::-1], ks=(1,)) == result


def test_mixed_score_ties_match_manual_threshold_calculation():
    result = evaluate_forecasts(*rows(scores=(3, 2, 2, 1)))
    assert result["overall"]["average_precision"] == pytest.approx(5 / 6)
    assert result["overall"]["auroc"] == pytest.approx(7 / 8)


def test_macro_uses_eligible_query_denominators():
    result = evaluate_forecasts(*rows(labels=(True, True, False, True),
                                      queries=("all-positive", "mixed", "mixed", "single")))
    assert result["macro"]["query_count"] == 3
    assert result["macro"]["average_precision_eligible_queries"] == 3
    assert result["macro"]["auroc_eligible_queries"] == 1
    assert result["queries"]["all-positive"]["auroc"] is None
    assert result["macro"]["auroc"] == 1


def test_no_positive_query_has_null_ap_recall_auc_but_zero_precision():
    result = evaluate_forecasts(*rows(labels=(False, False, False, False)))
    assert result["overall"]["average_precision"] is None
    assert result["overall"]["auroc"] is None
    assert result["overall"]["at_k"]["5"]["precision"] == 0
    assert result["overall"]["at_k"]["5"]["recall"] is None
    assert result["macro"]["average_precision_eligible_queries"] == 0
    assert result["macro"]["at_k"]["5"]["recall_eligible_queries"] == 0
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("which", (0, 1, 2))
def test_duplicate_ids_are_rejected(which):
    arguments = list(rows())
    arguments[which].append(arguments[which][0].copy())
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_forecasts(*arguments)


@pytest.mark.parametrize("which", (1, 2))
def test_missing_and_extra_predictions_or_outcomes_reject_entire_comparison(which):
    arguments = list(rows())
    arguments[which][-1]["candidate_id"] = "unknown"
    with pytest.raises(ValueError, match="candidate mismatch; missing=.*c3.*extra=.*unknown"):
        evaluate_forecasts(*arguments)


def test_comparison_never_silently_drops_a_models_missing_rows():
    candidates, predictions, outcomes = rows()
    with pytest.raises(ValueError, match="candidate mismatch"):
        compare_forecasts(candidates, {"complete": predictions, "incomplete": predictions[:-1]}, outcomes)


@pytest.mark.parametrize("bad_score", (float("nan"), float("inf"), "0.8", True, None))
def test_nonfinite_or_non_numeric_scores_fail(bad_score):
    candidates, forecasts, outcomes = rows()
    forecasts[0]["score"] = bad_score
    with pytest.raises(ValueError, match="finite number"):
        evaluate_forecasts(candidates, forecasts, outcomes)


@pytest.mark.parametrize("bad_label", (0, "false", None))
def test_outcomes_require_explicit_boolean(bad_label):
    candidates, forecasts, outcomes = rows()
    outcomes[0]["observed"] = bad_label
    with pytest.raises(ValueError, match="explicit boolean"):
        evaluate_forecasts(candidates, forecasts, outcomes)


def test_future_outcomes_change_scores_but_not_ranking_or_candidate_fingerprint():
    candidates, forecasts, outcomes = rows()
    originals = deepcopy((candidates, forecasts, outcomes))
    first = evaluate_forecasts(candidates, forecasts, outcomes)
    assert (candidates, forecasts, outcomes) == originals
    changed_outcomes = [{**row, "observed": not row["observed"]} for row in outcomes]
    second = evaluate_forecasts(candidates, forecasts, changed_outcomes)
    assert [row["candidate_id"] for row in first["ranking"]] == [
        row["candidate_id"] for row in second["ranking"]]
    assert first["protocol"]["candidate_set_sha256"] == second["protocol"]["candidate_set_sha256"]
    assert first["protocol"]["outcome_set_sha256"] != second["protocol"]["outcome_set_sha256"]
    assert first["overall"]["average_precision"] != second["overall"]["average_precision"]


@pytest.mark.parametrize("which", (0, 1))
def test_labels_cannot_be_merged_into_prediction_inputs(which):
    arguments = list(rows())
    arguments[which][0]["observed"] = True
    with pytest.raises(ValueError, match="outcomes must be supplied separately"):
        evaluate_forecasts(*arguments)


def test_comparative_metadata_and_dataset_boundary():
    candidates, forecasts, outcomes = rows()
    metadata = {name: {"budget_tag": "10-lookups", "dataset_id": "civic"}
                for name in ("graph", "flat")}
    result = compare_forecasts(candidates, {"graph": forecasts, "flat": forecasts}, outcomes,
                               model_metadata=metadata, provenance={"dataset_id": "civic"})
    assert result["models"]["graph"]["overall"] == result["models"]["flat"]["overall"]
    assert result["protocol"]["budget_match"]["status"] == "declared_matched"
    assert result["protocol"]["budget_match"]["verified"] is False
    metadata["flat"]["dataset_id"] = "dyport"
    with pytest.raises(ValueError, match="different dataset"):
        compare_forecasts(candidates, {"graph": forecasts, "flat": forecasts}, outcomes,
                          model_metadata=metadata)


@pytest.mark.parametrize("ks", ((), (0,), (-1,), (True,), (1.5,)))
def test_invalid_k_fails(ks):
    with pytest.raises(ValueError, match="positive integers"):
        evaluate_forecasts(*rows(), ks=ks)


def test_cli_emits_report_and_bad_input_never_emits_partial_report(tmp_path):
    candidates, forecasts, outcomes = rows()
    scenario = {"id": "synthetic", "dataset": "synthetic", "cutoff": "2020-01-01",
                "horizon": "2021-01-01", "candidates": candidates}
    for name, value in (("scenario", scenario), ("outcomes", outcomes),
                        ("forecasts", {"fixture": forecasts})):
        (tmp_path / f"{name}.json").write_text(json.dumps(value))
    script = Path(__file__).resolve().parents[1] / "scripts/evaluate_forecasts.py"
    command = [sys.executable, str(script)]
    for name in ("scenario", "outcomes", "forecasts"):
        command += [f"--{name}", str(tmp_path / f"{name}.json")]
    success = subprocess.run(command, capture_output=True, text=True)
    assert success.returncode == 0, success.stderr
    result = json.loads(success.stdout)
    assert result["models"]["fixture"]["overall"]["auroc"] == .75
    assert result["protocol"]["context"]["cutoff"] == "2020-01-01"
    (tmp_path / "outcomes.json").write_text(json.dumps({
        "scenario_id": "another-scenario", "outcomes": outcomes}))
    mismatch = subprocess.run(command, capture_output=True, text=True)
    assert mismatch.returncode == 2
    assert "scenario_id does not match" in mismatch.stderr
    (tmp_path / "outcomes.json").write_text("[]")
    failure = subprocess.run(command, capture_output=True, text=True)
    assert failure.returncode == 2
    assert failure.stdout == ""
    assert "candidate mismatch" in failure.stderr
