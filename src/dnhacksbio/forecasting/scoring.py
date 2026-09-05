"""Transparent graph heuristics over the historical packet, with inspectable paths."""
from __future__ import annotations

from collections import defaultdict
from math import sqrt


def active_claims(scenario: dict, evidence_ids=None) -> list[dict]:
    """A claim is visible once any of its historical evidence has been acquired."""
    available = {row["id"] for row in scenario.get("evidence", [])}
    visible = available if evidence_ids is None else set(evidence_ids)
    if not visible <= available:
        raise ValueError("evidence IDs must belong to the historical scenario")
    claims = []
    for claim in scenario.get("claims", []):
        supporting = set(claim.get("evidence_ids", [])) & visible
        if not supporting:
            continue
        contexts = claim.get("contexts") or []
        if isinstance(contexts, list):
            contexts = [context for context in contexts
                        if not context.get("evidence_id") or context["evidence_id"] in supporting]
        claims.append({**claim, "evidence_ids": sorted(supporting), "contexts": contexts})
    return claims


def score_candidates(scenario: dict, *, evidence_ids=None, method: str = "typed_paths") -> list[dict]:
    """Rank the fixed candidates using degree-normalized length-2/3 graph paths.

    Paths retain their relation and node-type signatures. This is an undirected
    association heuristic, not causal inference or an LLM forecast. ``popularity``
    is target degree over exactly the same acquired evidence.
    """
    if method not in ("typed_paths", "popularity"):
        raise ValueError(f"unknown scoring method: {method}")
    nodes = {node["id"]: node for node in scenario.get("nodes", [])}
    adjacency = defaultdict(set)
    edge_evidence = defaultdict(set)
    edge_relations = defaultdict(set)
    visible = {row["id"] for row in scenario.get("evidence", [])} if evidence_ids is None else set(evidence_ids)
    for claim in active_claims(scenario, visible):
        a, b = claim["source"], claim["target"]
        if a == b:
            continue
        adjacency[a].add(b)
        adjacency[b].add(a)
        edge = tuple(sorted((a, b)))
        edge_evidence[edge].update(set(claim.get("evidence_ids", [])) & visible)
        edge_relations[edge].add(claim["relation"])

    results = []
    for candidate in scenario.get("candidates", []):
        source, target = candidate["source"], candidate["target"]
        paths = []
        for middle in sorted(adjacency[source] & adjacency[target]):
            if middle not in (source, target):
                paths.append(([source, middle, target], 1.0 / len(adjacency[middle])))
        for first in sorted(adjacency[source] - {target}):
            for second in sorted((adjacency[first] & adjacency[target]) - {source, first, target}):
                paths.append(([source, first, second, target],
                              1.0 / sqrt(len(adjacency[first]) * len(adjacency[second]))))
        paths.sort(key=lambda pair: (-pair[1], pair[0]))
        support = set()
        path_records = []
        for path, contribution in paths:
            edges = [tuple(sorted((a, b))) for a, b in zip(path, path[1:])]
            evidence = sorted(set().union(*(edge_evidence[edge] for edge in edges)))
            support.update(evidence)
            path_records.append({
                "nodes": path,
                "labels": [nodes.get(node_id, {}).get("label", node_id) for node_id in path],
                "types": [nodes.get(node_id, {}).get("type", "entity") for node_id in path],
                "relations": [sorted(edge_relations[edge]) for edge in edges],
                "contribution": contribution, "evidence_ids": evidence,
            })
        score = float(len(adjacency[target])) if method == "popularity" else sum(v for _, v in paths)
        if method == "popularity":
            support = set().union(*(edge_evidence[tuple(sorted((target, neighbor)))]
                                    for neighbor in adjacency[target]))
        results.append({
            "candidate_id": candidate["id"], "query_id": candidate.get("query_id", source),
            "source": source, "target": target, "score": score,
            "reason": (f"{len(adjacency[target])} historical neighbors of the target."
                       if method == "popularity" else
                       f"{len(paths)} historical paths of length 2 or 3; intermediate-degree normalized."),
            "evidence_ids": sorted(support), "paths": path_records[:5],
            "path_count": len(paths), "method": method,
        })
    results.sort(key=lambda row: (-row["score"], row["candidate_id"]))
    query_ranks = defaultdict(int)
    for rank, result in enumerate(results, 1):
        query_ranks[result["query_id"]] += 1
        result["rank"] = rank
        result["query_rank"] = query_ranks[result["query_id"]]
    return results
