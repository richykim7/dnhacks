"""Deterministic historical-evidence acquisition and forecast replay. No outcome reader."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from .scoring import active_claims, score_candidates
from .selection import select_branches


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _date(value) -> date:
    text = str(value)
    return date(int(text), 12, 31) if len(text) == 4 else date.fromisoformat(text[:10])


def _branches(scenario: dict) -> tuple[list[dict], dict[str, float]]:
    """Freeze acquisition facets from historical indexing metadata, before selection."""
    facets = defaultdict(set)
    weights = {}
    for claim in scenario.get("claims", []):
        features = {f"source:{claim['source']}", f"target:{claim['target']}",
                    f"relation:{claim['relation']}"}
        contexts = claim.get("contexts") or []
        if isinstance(contexts, dict):
            contexts = [contexts]
        for evidence_id in claim.get("evidence_ids", []):
            facets[evidence_id].update(features)
            for context in contexts:
                if context.get("evidence_id", evidence_id) != evidence_id:
                    continue
                for key in ("gene", "gene_id", "disease", "disease_id"):
                    if context.get(key):
                        facets[evidence_id].add(f"{key}:{context[key]}")
    items = []
    for evidence in scenario.get("evidence", []):
        evidence_id = evidence["id"]
        unique = f"evidence:{evidence_id}"
        features = facets[evidence_id] | {unique}
        for feature in features:
            weights[feature] = 0.25 if feature.startswith("evidence:") else 1.0
        item = {"id": evidence_id, "title": evidence.get("title", evidence_id),
                "evidence_ids": [evidence_id], "facets": sorted(features)}
        if "fixture_judge_score" in evidence:
            item["fixture_judge_score"] = evidence["fixture_judge_score"]
        items.append(item)
    return sorted(items, key=lambda item: item["id"]), weights


def run_scenario(scenario: dict, *, policy: str = "greedy", batch_size: int = 8,
                 rounds: int = 4, initial_evidence_ids=None, seed: int = 0) -> dict:
    """Build revisions and rank a fixed candidate pool, using only this historical packet.

    Acquisitions load already-historical evidence in a selected order. These are
    graph-construction revisions, not successive real-world publication years.
    Every acquisition costs one abstract unit; this is not measured token cost.
    """
    if batch_size < 1 or rounds < 0:
        raise ValueError("batch_size must be positive and rounds must be nonnegative")
    if "outcomes" in scenario:
        raise ValueError("runner accepts a historical scenario, not a combined outcome packet")
    cutoff = _date(scenario["cutoff"])
    evidence = scenario.get("evidence", [])
    by_id = {row["id"]: row for row in evidence}
    if len(by_id) != len(evidence):
        raise ValueError("historical evidence IDs must be unique")
    for row in evidence:
        if not row.get("available_at") or _date(row["available_at"]) > cutoff:
            raise ValueError(f"evidence {row['id']} is not dated on or before the cutoff")
    candidates = scenario.get("candidates", [])
    if len({row["id"] for row in candidates}) != len(candidates):
        raise ValueError("candidate IDs must be unique")
    ordered = sorted(evidence, key=lambda row: (row["available_at"], row["id"]))
    if initial_evidence_ids is None:
        # A deterministic seed graph; selection never consults later outcomes.
        initial_evidence_ids = [row["id"] for row in ordered[:max(1, len(ordered) // 4)]]
    acquired = set(initial_evidence_ids)
    if not acquired <= by_id.keys():
        raise ValueError("initial evidence must belong to the historical scenario")
    items, weights = _branches(scenario)
    items_by_id = {item["id"]: item for item in items}
    covered = set().union(*(set(items_by_id[item_id]["facets"]) for item_id in acquired))
    events, revisions = [], []
    selections = []
    revision = 0

    def emit(kind, title, description, payload):
        events.append({"seq": len(events) + 1, "type": kind, "revision": revision,
                       "title": title, "description": description, "payload": payload})

    def record_graph(added):
        claims = active_claims(scenario, acquired)
        visible_nodes = {node_id for claim in claims for node_id in (claim["source"], claim["target"])}
        emit("graph_updated", f"Graph revision {revision}",
             f"{len(acquired)} historical evidence records now support {len(claims)} associations.",
             {"node_ids": sorted(visible_nodes), "claim_ids": sorted(claim["id"] for claim in claims),
              "evidence_ids": sorted(acquired), "added_evidence_ids": sorted(added),
              "claim_count": len(claims), "node_count": len(visible_nodes)})
        forecasts = score_candidates(scenario, evidence_ids=acquired)
        previous = {row["candidate_id"]: row["rank"] for row in revisions[-1]["forecasts"]} if revisions else {}
        for row in forecasts:
            row["previous_rank"] = previous.get(row["candidate_id"])
            row["rank_change"] = previous.get(row["candidate_id"], row["rank"]) - row["rank"]
        revisions.append({"revision": revision, "evidence_ids": sorted(acquired),
                          "claim_count": len(claims), "forecasts": forecasts})
        emit("forecast_recorded", f"Ranked {len(forecasts)} eligible associations",
             "Historical graph paths determine the ranking. Later outcomes remain unopened.",
             {"candidate_ids": [row["candidate_id"] for row in forecasts],
              "candidate_count": len(forecasts), "revision": revision})

    record_graph(acquired)
    initial_count = len(acquired)
    for revision in range(1, rounds + 1):
        remaining = [item for item in items if item["id"] not in acquired]
        if not remaining:
            break
        selection = select_branches(remaining, batch_size, policy=policy, weights=weights,
                                    covered=covered, seed=seed + revision)
        selections.append(selection)
        added = set(selection["selected_ids"])
        selected = [items_by_id[item_id] for item_id in selection["selected_ids"]]
        emit("branches_selected", f"Selected {len(selected)} evidence acquisitions",
             f"{policy}: {selection['value']:.2f} additional weighted evidence facets.",
             {**selection, "branches": selected})
        acquired |= added
        covered |= set().union(*(set(item["facets"]) for item in selected))
        record_graph(added)

    packet = {
        "schema_version": "forecast-run-v1", "scenario_id": scenario["id"],
        "scenario_sha256": sha256(_canonical(scenario).encode()).hexdigest(),
        "origin": "fixture" if policy == "judge_fixture" else "computed",
        "model": "Historical degree-normalized path heuristic (no LLM)", "policy": policy,
        "events": events, "forecasts": revisions[-1]["forecasts"], "revisions": revisions,
        "comparisons": {
            "initial_graph": revisions[0]["forecasts"],
            "popularity": score_candidates(scenario, evidence_ids=acquired, method="popularity"),
            "full_historical_graph": score_candidates(scenario),
        },
        "comparison_protocol": {
            "popularity": "Same candidates and final acquired evidence; target-degree baseline.",
            "initial_graph": "Progress diagnostic with less evidence; not a matched-information ablation.",
            "full_historical_graph": "All historical evidence; retrieval-budget reference, not equal-budget.",
        },
        "metrics": {},
        "costs": {"llm_calls": 0, "initial_evidence_records": initial_count,
                  "evidence_acquisitions": len(acquired) - initial_count,
                  "selection_rounds": len(selections),
                  "unit": "one abstract acquisition per evidence record; not measured compute"},
        "config": {"batch_size": batch_size, "rounds": rounds, "seed": seed,
                   "initial_evidence_ids": revisions[0]["evidence_ids"]},
        "disclosure": ("Computed historical graph-only ranking. Acquisition order changes available graph "
                       "evidence; coverage certificates do not guarantee scientific truth or forecast accuracy."),
    }
    packet["id"] = f"{scenario['id']}-{policy}-{sha256(_canonical(packet).encode()).hexdigest()[:12]}"
    return packet


def save_run(packet: dict, path: str | Path) -> Path:
    """Serialize committed predictions without overwriting an existing run."""
    path = Path(path)
    serialized = _canonical(packet) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        handle.write(serialized)
    return path
