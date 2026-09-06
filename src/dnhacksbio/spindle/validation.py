"""Prespecified paired-seed numerical diagnostics, never biological calibration."""
from __future__ import annotations
import math
from statistics import mean, stdev


def assess_coupled(plan: dict, runs: list[dict]) -> dict:
    """Retain incomplete cells and judge equivalence, not failure to reject difference.

    The fixed pilot uses sixteen independent simulation streams. Intervals are
    marginal, approximate 90% paired Student-t intervals, not simultaneous claims.
    """
    seeds = plan['protocol']['seeds']
    conditions = [c['name'] for c in plan['protocol']['conditions']]
    timesteps = plan['timesteps_s']
    margins = plan['engineering_equivalence_margins']
    if (len(seeds) != 16 or len(set(seeds)) != 16 or len(timesteps) != 3
            or not timesteps[0] > timesteps[1] > timesteps[2] > 0
            or len(margins) != 4 or any(not math.isfinite(x) or x <= 0 for x in margins)):
        raise ValueError('Expected frozen sixteen-seed, three-refinement pilot')
    expected = {(dt, seed, condition) for dt in timesteps for seed in seeds for condition in conditions}
    indexed = {}
    for run in runs:
        key = (run['dt_s'], run['seed'], run['condition'])
        if key not in expected or key in indexed:
            raise ValueError('Unexpected or duplicate replicate')
        if run['status'] == 'completed':
            if len(run['values']) != 4 or any(not math.isfinite(x) for x in run['values']):
                raise ValueError('Nonfinite or incomplete numerical endpoint')
        indexed[key] = run
    failures = [{'dt_s': dt, 'seed': seed, 'condition': condition,
                 'status': indexed.get((dt, seed, condition), {}).get('status', 'missing')}
                for dt, seed, condition in sorted(expected)
                if indexed.get((dt, seed, condition), {}).get('status') != 'completed']
    rows = []
    for condition in conditions:
        groups = [[indexed.get((dt, seed, condition)) for seed in seeds] for dt in timesteps]
        complete = all(r is not None and r['status'] == 'completed' for group in groups for r in group)
        row = {'condition': condition, 'complete': complete, 'equivalence_established': False}
        if complete:
            # A timestep change must not change the saved initial centrosome state.
            initial_matches = all(groups[0][i]['initial_poles'] == groups[j][i]['initial_poles']
                                  for i in range(16) for j in (1, 2))
            row['matched_initial_centrosomes'] = initial_matches
            endpoints = []
            for k, margin in enumerate(margins):
                differences = [fine['values'][k] - middle['values'][k]
                               for fine, middle in zip(groups[2], groups[1])]
                estimate = mean(differences)
                half_width = 1.7530503557 * stdev(differences) / math.sqrt(16)
                interval = [estimate - half_width, estimate + half_width]
                endpoints.append({'metric': plan['metrics'][k], 'margin': margin,
                                  'mean_by_dt': {str(dt): mean(r['values'][k] for r in group)
                                                 for dt, group in zip(timesteps, groups)},
                                  'fine_minus_middle': estimate, 'approximate_90pct_interval': interval,
                                  'equivalent': interval[0] >= -margin and interval[1] <= margin})
            row['endpoints'] = endpoints
            row['equivalence_established'] = initial_matches and all(e['equivalent'] for e in endpoints)
        rows.append(row)
    return {'schema': 'spindle_coupled_assessment.v1', 'conditions': rows,
            'failed_or_missing': failures,
            'equivalence_established': not failures and all(r['equivalence_established'] for r in rows),
            'interval_scope': 'Marginal approximate paired-seed 90% t intervals; no simultaneous coverage claim.',
            'biological_calibration': {'status': 'unavailable', 'reason':
                'No compatible audited training/held-out observations for the provisional 3D interaction model.'}}
