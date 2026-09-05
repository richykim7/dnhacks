"""Build a bounded historical input before consulting any later evidence."""
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path

from .records import OutcomePacket, Scenario
from .sources.civic import load_release, stable_id


def source_manifest(path: str | Path, available_at: str) -> dict:
    release = date.fromisoformat(available_at).strftime("%d-%b-%Y")
    content = Path(path).read_bytes()
    return {"available_at": available_at, "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "url": f"https://civicdb.org/downloads/{release}/{release}-ClinicalEvidenceSummaries.tsv"}


def historical_snapshot(rows: list[dict], *, cutoff: str, horizon: str,
                        max_variants: int = 24, max_therapies: int = 36,
                        source: dict | None = None) -> Scenario:
    """This function accepts historical rows only. Cohort selection cannot see outcomes."""
    if date.fromisoformat(cutoff) >= date.fromisoformat(horizon):
        raise ValueError("cutoff must precede horizon")
    if max_variants < 1 or max_therapies < 1:
        raise ValueError("cohort limits must be positive")
    if any(row["evidence"]["available_at"] > cutoff for row in rows):
        raise ValueError("historical inputs contain later evidence")
    eligible = sorted((row for row in rows if row["eligible"]), key=lambda row: row["evidence"]["id"])
    adjacency = defaultdict(set)
    for row in eligible:
        adjacency[row["source"]].add(row["target"])
    variants = sorted(adjacency, key=lambda v: (-len(adjacency[v]), v))[:max_variants]
    frequencies = Counter(row["target"] for row in eligible if row["source"] in variants)
    therapies = sorted(frequencies, key=lambda t: (-frequencies[t], t))[:max_therapies]
    selected = [row for row in eligible if row["source"] in variants and row["target"] in therapies]
    nodes, claims, evidence = {}, {}, {}
    for row in selected:
        for node_id, label, kind in [(row["source"], row["variant_label"], "variant"),
                                     (row["target"], row["therapy_label"], "therapy"),
                                     (row["gene_id"], row["gene_label"], "gene")]:
            nodes.setdefault(node_id, {"id": node_id, "label": label, "type": kind})
        ev = row["evidence"]
        evidence[ev["id"]] = ev
        for start, end, relation in [(row["source"], row["target"], "associated_with"),
                                      (row["gene_id"], row["source"], "has_variant")]:
            claim_id = stable_id("civic:association", start, relation, end)
            claim = claims.setdefault(claim_id, {"id": claim_id, "source": start, "target": end,
                "relation": relation, "evidence_ids": [], "contexts": []})
            if ev["id"] not in claim["evidence_ids"]:
                claim["evidence_ids"].append(ev["id"])
                claim["contexts"].append(row["context"])
    # Only endpoints represented in the historical scene are eligible.
    candidates = [{"id": stable_id("civic:candidate", v, t), "source": v, "target": t, "query_id": v}
                  for v in variants if v in nodes for t in therapies if t in nodes and t not in adjacency[v]]
    policy = {"variant_limit": max_variants, "therapy_limit": max_therapies,
              "variant_order": "descending distinct historical therapy-group degree, then stable ID",
              "therapy_order": "descending historical evidence-row count within chosen variants, then stable ID",
              "candidate_rule": "cartesian product of retained historical variants and therapy groups, excluding all historical predictive associations",
              "therapy_identity": "whole group split only on commas outside parentheses, whitespace/case normalized, sorted; no synonym expansion",
              "eligibility": "accepted, unflagged Predictive evidence with variant, gene and therapy identifiers"}
    snapshot_id = stable_id("civic:snapshot", cutoff, policy, source, list(claims.values()),
                            sorted(evidence.values(), key=lambda x: x["id"]), candidates)
    return {"id": f"civic-{cutoff}-{horizon}",
            "title": "Which cancer variant–therapy associations will enter CIViC next?",
            "dataset": "CIViC historical releases", "cutoff": cutoff, "horizon": horizon,
            "manifest": {"schema_version": 1, "origin": "computed", "snapshot_id": snapshot_id,
                "task": "later CIViC variant–therapy-group associations", "candidate_policy": policy,
                "date_semantics": "release availability, not first publication or worldwide discovery",
                "source": source or {}, "license": "CC0-1.0",
                "license_url": "https://docs.civicdb.org/en/latest/about.html",
                "claim_namespace": "CIViC imported association IDs; not litmap normalized Claim atom IDs",
                "association_semantics": "An association may describe sensitivity, resistance, or conflicting findings; inspect contexts.",
                "unknown_interaction": "2018 therapy groups lack interaction type; no combination or efficacy inference."},
            "nodes": sorted(nodes.values(), key=lambda x: x["id"]),
            "claims": sorted(claims.values(), key=lambda x: x["id"]),
            "evidence": sorted(evidence.values(), key=lambda x: x["id"]),
            "candidates": candidates}


def future_outcomes(scenario: Scenario, historical_rows: list[dict], later_rows: list[dict],
                    *, source: dict | None = None) -> OutcomePacket:
    known_ids = {row["evidence"]["id"] for row in historical_rows}
    by_pair = defaultdict(list)
    for row in later_rows:
        ev = row["evidence"]
        if (row["eligible"] and ev["id"] not in known_ids
                and scenario["cutoff"] < ev["available_at"] <= scenario["horizon"]):
            by_pair[row["source"], row["target"]].append(ev)
    outcomes, evidence = [], {}
    for candidate in scenario["candidates"]:
        matched = by_pair[candidate["source"], candidate["target"]]
        evidence.update((ev["id"], ev) for ev in matched)
        outcomes.append({"candidate_id": candidate["id"], "observed": bool(matched),
                         "evidence_ids": sorted({ev["id"] for ev in matched})})
    return {"scenario_id": scenario["id"], "horizon": scenario["horizon"],
            "manifest": {"source": source or {}, "snapshot_id": scenario["manifest"]["snapshot_id"],
                "label_rule": "eligible association with an evidence ID absent from the earlier release, present by horizon",
                "unobserved_meaning": "not observed under this release and identity protocol; not experimentally disproved",
                "limitations": "Curation additions may cite older publications. Therapy aliases are not resolved; altered old evidence IDs are excluded."},
            "outcomes": outcomes, "evidence": sorted(evidence.values(), key=lambda x: x["id"])}


def build_civic_scenario(historical_path: str | Path, future_path: str | Path, *,
                         cutoff: str = "2018-01-01", horizon: str = "2022-03-01",
                         max_variants: int = 24, max_therapies: int = 36) -> tuple[Scenario, OutcomePacket]:
    historical_rows = load_release(historical_path, cutoff)
    scenario = historical_snapshot(historical_rows, cutoff=cutoff, horizon=horizon,
        max_variants=max_variants, max_therapies=max_therapies,
        source=source_manifest(historical_path, cutoff))
    # Later rows are first opened only after the historical graph and candidates exist.
    outcomes = future_outcomes(scenario, historical_rows, load_release(future_path, horizon),
                               source=source_manifest(future_path, horizon))
    return scenario, outcomes


def load_scenario(path: str | Path) -> Scenario:
    """Load historical input only; never opens sibling outcome files."""
    scenario = json.loads(Path(path).read_text())
    if "outcomes" in scenario or any(ev["available_at"] > scenario["cutoff"] for ev in scenario["evidence"]):
        raise ValueError("scenario must contain only historical input")
    return scenario
