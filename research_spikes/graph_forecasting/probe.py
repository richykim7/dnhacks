"""Reproduce the planning probes. Reads cached public data; performs no LLM calls.

Run from the repository root: python research_spikes/graph_forecasting/probe.py
The downloaded Dyport table is at data/cache/graph-forecasting/dyport-2016.csv.
"""
from itertools import combinations, product
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tasks/research/graph-forecasting"
OUT.mkdir(parents=True, exist_ok=True)


def coverage_probe():
    worst, witness, checked, invalid_bounds = 1.0, None, 0, 0
    for masks in product(range(16), repeat=4):
        optimum = max((masks[a] | masks[b]).bit_count()
                      for a, b in combinations(range(4), 2))
        if not optimum:
            continue
        selected, covered = [], 0
        for _ in range(2):
            i = max((i for i in range(4) if i not in selected),
                    key=lambda i: ((covered | masks[i]).bit_count(), -i))
            selected.append(i)
            covered |= masks[i]
        value = covered.bit_count()
        if value / optimum < worst:
            worst = value / optimum
            witness = dict(candidate_facet_bitmasks=masks, greedy_indices=selected,
                           greedy_value=value, optimal_value=optimum)
        residual = sorted(((covered | masks[i]).bit_count() - value
                           for i in range(4) if i not in selected), reverse=True)
        upper = min((masks[0] | masks[1] | masks[2] | masks[3]).bit_count(),
                    value + sum(residual[:2]))
        invalid_bounds += upper < optimum
        checked += 1
    return dict(purpose="Finite coverage/certificate audit; not scientific prediction accuracy.",
                candidate_branches=4, evidence_facets=4, selected_branches=2,
                instances_including_zero=16**4, nonzero_instances_checked=checked,
                worst_greedy_to_optimum_ratio=worst, theoretical_k2_lower_bound=0.75,
                worst_case=witness, invalid_upper_bounds=invalid_bounds,
                current_repo_feasible_subsets=6)


def dyport_probe():
    import pandas as pd
    from sklearn.metrics import average_precision_score, roc_auc_score

    p = ROOT / "data/cache/graph-forecasting/dyport-2016.csv"
    frame = pd.read_csv(p)
    result = dict(source="https://github.com/IlyaTyagin/Dyport",
                  file=str(p.relative_to(ROOT)), bytes=p.stat().st_size,
                  sha256=hashlib.sha256(p.read_bytes()).hexdigest(), rows=len(frame),
                  columns=list(frame), label_counts=frame.label.value_counts().to_dict(),
                  duplicate_pair_rows=int(frame.duplicated(["subj", "obj"]).sum()),
                  baseline_metrics={},
                  notes=["Unfiltered authors' 2016 prediction table, including duplicate rows.",
                         "Not a reproduction of stratified paper tables or our model's result.",
                         "Missing/nonfinite scores excluded separately for each model."])
    for col in frame:
        if "score" not in col.lower():
            continue
        scores = pd.to_numeric(frame[col], errors="coerce")
        valid = scores.notna() & scores.abs().lt(float("inf")) & frame.label.isin([0, 1])
        if frame.loc[valid, "label"].nunique() != 2:
            continue
        result["baseline_metrics"][col] = dict(
            n=int(valid.sum()),
            auroc=float(roc_auc_score(frame.loc[valid, "label"], scores[valid])),
            average_precision=float(average_precision_score(frame.loc[valid, "label"], scores[valid])))
    return result


if __name__ == "__main__":
    for name, result in [("coverage-probe", coverage_probe()), ("dyport-access", dyport_probe())]:
        (OUT / f"{name}.json").write_text(json.dumps(result, indent=2) + "\n")
        print(name, "saved")
