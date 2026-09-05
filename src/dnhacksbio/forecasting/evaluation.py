"""Deterministic evaluation of sealed, later-observed forecasting outcomes.

Scoring and evidence retrieval belong upstream. This module only joins complete
prediction sets to separately supplied outcomes; it never calls a model.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from hashlib import sha256
from itertools import groupby
import json
import math
from numbers import Real
from typing import Any


def _index(rows: Iterable[Mapping[str, Any]], key: str, name: str) -> dict:
    indexed = {}
    for row in rows:
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name}: {key} must be a nonempty string")
        if value in indexed:
            raise ValueError(f"{name}: duplicate {key} {value!r}")
        indexed[value] = dict(row)
    return indexed


def _same_ids(expected: set[str], actual: set[str], name: str) -> None:
    if expected != actual:
        missing, extra = sorted(expected - actual), sorted(actual - expected)
        raise ValueError(
            f"{name}: candidate mismatch; missing={missing[:5]!r} "
            f"({len(missing)} total), extra={extra[:5]!r} ({len(extra)} total)"
        )


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def _cohort(candidates, outcomes):
    candidates = _index(candidates, "id", "candidates")
    if not candidates:
        raise ValueError("candidates: at least one candidate is required")
    for row in candidates.values():
        for key in ("source", "target", "query_id"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"candidates: {key} must be a nonempty string")
        if "observed" in row or "outcomes" in row:
            raise ValueError("candidates: outcomes must be supplied separately")
    outcomes = _index(outcomes, "candidate_id", "outcomes")
    _same_ids(set(candidates), set(outcomes), "outcomes")
    for row in outcomes.values():
        if type(row.get("observed")) is not bool:
            raise ValueError("outcomes: observed must be an explicit boolean")
        evidence = row.get("evidence_ids")
        if not isinstance(evidence, list) or any(
            not isinstance(value, str) or not value.strip() for value in evidence
        ):
            raise ValueError("outcomes: evidence_ids must be a list of nonempty strings")
    return candidates, outcomes


def _metrics(ranking, ks):
    """Threshold-grouped AP and half-credit AUROC; ID ties for top-k lists."""
    n = len(ranking)
    positives = sum(row["observed"] for row in ranking)
    negatives = n - positives
    seen = true_positives = 0
    ap_numerator = auc_numerator = 0.0
    for _, group in groupby(ranking, key=lambda row: row["score"]):
        group = list(group)
        group_positives = sum(row["observed"] for row in group)
        group_negatives = len(group) - group_positives
        # Descending scores: preceding positives beat this group's negatives.
        auc_numerator += group_negatives * (true_positives + group_positives / 2)
        true_positives += group_positives
        seen += len(group)
        ap_numerator += group_positives * true_positives / seen
    at_k = {}
    for k in ks:
        selected = ranking[:k]
        hit_ids = [row["candidate_id"] for row in selected if row["observed"]]
        hit_set = set(hit_ids)
        at_k[str(k)] = {
            "requested_k": k,
            "eligible_candidates": n,
            "selected_count": len(selected),
            "precision_denominator": len(selected),
            "hits": len(hit_ids),
            "precision": len(hit_ids) / len(selected),
            "recall": len(hit_ids) / positives if positives else None,
            "selected_ids": [row["candidate_id"] for row in selected],
            "hit_ids": hit_ids,
            "unobserved_ids": [row["candidate_id"] for row in selected if not row["observed"]],
            "missed_ids": [row["candidate_id"] for row in ranking
                           if row["observed"] and row["candidate_id"] not in hit_set],
        }
    return {
        "candidate_count": n,
        "observed_count": positives,
        "unobserved_count": negatives,
        "observed_rate": positives / n,
        "average_precision": ap_numerator / positives if positives else None,
        "auroc": auc_numerator / (positives * negatives) if positives and negatives else None,
        "average_precision_eligible": bool(positives),
        "auroc_eligible": bool(positives and negatives),
        "at_k": at_k,
    }


def _evaluate(candidates, forecasts, outcomes, ks):
    forecasts = _index(forecasts, "candidate_id", "forecasts")
    _same_ids(set(candidates), set(forecasts), "forecasts")
    for row in forecasts.values():
        score = row.get("score")
        if isinstance(score, bool) or not isinstance(score, Real) or not math.isfinite(score):
            raise ValueError("forecasts: score must be a finite number")
        if "observed" in row or "outcomes" in row:
            raise ValueError("forecasts: outcomes must be supplied separately")
    ranking = sorted(({
        "candidate_id": candidate_id,
        "query_id": candidate["query_id"],
        "source": candidate["source"],
        "target": candidate["target"],
        "score": float(forecasts[candidate_id]["score"]),
        "observed": outcomes[candidate_id]["observed"],
        "outcome_evidence_ids": sorted(set(outcomes[candidate_id]["evidence_ids"])),
    } for candidate_id, candidate in candidates.items()),
        key=lambda row: (-row["score"], row["candidate_id"]))
    query_rows = defaultdict(list)
    for row in ranking:
        query_rows[row["query_id"]].append(row)
    queries = {query_id: _metrics(rows, ks) for query_id, rows in sorted(query_rows.items())}
    macro = {"query_count": len(queries)}
    for metric in ("average_precision", "auroc"):
        eligible = [row[metric] for row in queries.values() if row[metric] is not None]
        macro[metric] = sum(eligible) / len(eligible) if eligible else None
        macro[f"{metric}_eligible_queries"] = len(eligible)
    macro["at_k"] = {}
    for k in ks:
        values = [row["at_k"][str(k)] for row in queries.values()]
        eligible_recalls = [row["recall"] for row in values if row["recall"] is not None]
        macro["at_k"][str(k)] = {
            "precision": sum(row["precision"] for row in values) / len(values),
            "precision_eligible_queries": len(values),
            "recall": sum(eligible_recalls) / len(eligible_recalls) if eligible_recalls else None,
            "recall_eligible_queries": len(eligible_recalls),
        }
    return {"overall": _metrics(ranking, ks), "macro": macro,
            "queries": queries, "ranking": ranking}


def compare_forecasts(candidates, model_forecasts, outcomes, *, ks=(5, 10),
                      provenance=None, protocol=None, model_metadata=None):
    """Compare complete model predictions on exactly the same candidate rows.

    ``model_forecasts`` maps a model ID to [{candidate_id, score}, ...].
    Metadata is descriptive: matching budget tags are declarations, not proof
    of equal executed work. Dataset IDs, when declared per model, must agree.
    """
    ks = tuple(ks)
    if not ks or any(type(k) is not int or k < 1 for k in ks):
        raise ValueError("ks must contain positive integers")
    ks = sorted(set(ks))
    candidates, outcomes = _cohort(candidates, outcomes)
    if not isinstance(model_forecasts, Mapping) or not model_forecasts:
        raise ValueError("model_forecasts must map at least one model ID to predictions")
    if any(not isinstance(name, str) or not name.strip() for name in model_forecasts):
        raise ValueError("model IDs must be nonempty strings")
    model_metadata = dict(model_metadata or {})
    if set(model_metadata) - set(model_forecasts):
        raise ValueError("model_metadata contains unknown model IDs")
    provenance = dict(provenance or {})
    dataset_ids = {metadata["dataset_id"] for metadata in model_metadata.values()
                   if metadata.get("dataset_id")}
    if provenance.get("dataset_id"):
        dataset_ids.add(provenance["dataset_id"])
    if len(dataset_ids) > 1:
        raise ValueError("cannot compare predictions from different dataset IDs")
    models = {}
    for name, predictions in sorted(model_forecasts.items()):
        models[name] = _evaluate(candidates, predictions, outcomes, ks)
        models[name]["metadata"] = dict(model_metadata.get(name, {}))
    candidate_rows = [{key: row[key] for key in ("id", "source", "target", "query_id")}
                      for _, row in sorted(candidates.items())]
    outcome_rows = [{"candidate_id": candidate_id, "observed": row["observed"],
                     "evidence_ids": sorted(set(row["evidence_ids"]))}
                    for candidate_id, row in sorted(outcomes.items())]
    budget_tags = [models[name]["metadata"].get("budget_tag") for name in models]
    return {
        "schema_version": "forecast-evaluation/v1",
        "provenance": provenance,
        "protocol": {
            "context": dict(protocol or {}),
            "candidate_set_sha256": _digest(candidate_rows),
            "outcome_set_sha256": _digest(outcome_rows),
            "candidate_count": len(candidates),
            "query_count": len({row["query_id"] for row in candidates.values()}),
            "ks": ks,
            "comparison": "identical complete candidate and outcome rows for every model",
            "outcome_meaning": "recorded by the horizon; unobserved does not mean disproved",
            "ranking_ties": "descending score, then ascending candidate_id",
            "average_precision": "score-threshold grouped, non-interpolated; null without positives",
            "auroc": "positive-negative pair concordance; ties receive half credit; null without both classes",
            "precision_at_k": "hits / min(k, eligible candidates); denominator reported per query",
            "macro": "equal query weights, excluding undefined values with eligibility counts",
            "budget_match": {
                "status": "unspecified" if not all(budget_tags) else
                          "declared_matched" if len(set(budget_tags)) == 1 else "different",
                "verified": False,
                "tags": dict(zip(models, budget_tags)),
            },
        },
        "models": models,
    }


def evaluate_forecasts(candidates, forecasts, outcomes, *, ks=(5, 10),
                       provenance=None, protocol=None):
    """Single-model form of :func:`compare_forecasts`, without a models wrapper."""
    report = compare_forecasts(candidates, {"forecast": forecasts}, outcomes,
                               ks=ks, provenance=provenance, protocol=protocol)
    result = report.pop("models")["forecast"]
    return {**report, **result}
