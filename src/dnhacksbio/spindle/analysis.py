"""Prespecified connected-component clustering of simulation replicate trajectories.

Frames are observations along one replicate, never independent samples. No p-values.
"""
from __future__ import annotations
import math
from statistics import mean, stdev


def components(poles: list[dict], threshold: float) -> list[list[str]]:
    if not math.isfinite(threshold) or threshold <= 0:
        raise ValueError('Clustering threshold must be positive micrometers')
    parents = list(range(len(poles)))
    def root(i):
        while parents[i] != i:
            i = parents[i]
        return i
    for i, a in enumerate(poles):
        for j, b in enumerate(poles[:i]):
            if math.dist(a['position'], b['position']) <= threshold:
                parents[root(i)] = root(j)
    groups = {}
    for i, p in enumerate(poles):
        groups.setdefault(root(i), []).append(p['id'])
    return list(groups.values())


def analyze_run(run: dict, threshold_um: float, dwell_s: float) -> dict:
    if not math.isfinite(dwell_s) or dwell_s <= 0:
        raise ValueError('Required dwell must be positive seconds')
    frames = run['frames']
    counts = [len(components(f['poles'], threshold_um)) for f in frames]
    onset = None
    first = None
    total = 0.
    for i, (f, count) in enumerate(zip(frames, counts)):
        if count == 2:
            if onset is None:
                onset = f['time']
            if first is None and f['time'] - onset >= dwell_s:
                first = onset
            if i and counts[i-1] == 2:
                total += f['time'] - frames[i-1]['time']
        else:
            onset = None
    distances = [{ 'time_s': f['time'], 'pairs': [
        {'a': a['id'], 'b': b['id'], 'distance_um': math.dist(a['position'], b['position'])}
        for i, a in enumerate(f['poles']) for b in f['poles'][:i]]} for f in frames]
    return {'seed': run['seed'], 'condition': run['condition'], 'pole_counts': counts,
            'time_to_bipolar_s': first, 'right_censored': first is None,
            'observation_end_s': frames[-1]['time'], 'bipolar_dwell_s': total,
            'final_pole_count': counts[-1], 'pairwise_distances': distances}


def analyze_ensemble(bundle: dict, plan: dict) -> dict:
    threshold, dwell = plan['threshold_um'], plan['dwell_s']
    results = [analyze_run(r, threshold, dwell) for r in bundle['runs']]
    conditions = {}
    for condition in sorted({r['condition'] for r in results}):
        rows = [r for r in results if r['condition'] == condition]
        values = [r['bipolar_dwell_s'] for r in rows]
        conditions[condition] = {'simulation_replicates': len(rows),
            'uncensored_replicates': sum(not r['right_censored'] for r in rows),
            'mean_bipolar_dwell_s': mean(values),
            'replicate_sd_s': stdev(values) if len(values) > 1 else None,
            'final_pole_count_distribution': {str(k): sum(r['final_pole_count'] == k for r in rows)
                                             for k in sorted({r['final_pole_count'] for r in rows})}}
    sensitivity = {str(t): [analyze_run(r, t, dwell)['final_pole_count'] for r in bundle['runs']]
                   for t in plan.get('sensitivity_thresholds_um', [])}
    return {'schema_version': 1, 'status': 'exploratory_simulation_only',
            'classifier': 'single-linkage distance components; exactly two components; sampled dwell',
            'analysis_plan': plan, 'runs': results, 'conditions': conditions,
            'threshold_sensitivity': sensitivity,
            'uncertainty': 'Between simulation seeds only; biological uncertainty unassessed.'}
