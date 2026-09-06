import copy
import pytest
from dnhacksbio.spindle.validation import assess_coupled


def study():
    plan = {'protocol': {'seeds': list(range(16)), 'conditions': [{'name': 'control'}]},
            'timesteps_s': [.002, .001, .0005], 'engineering_equivalence_margins': [.25, 5, 2, .1],
            'metrics': ['distance', 'length', 'bound', 'dwell']}
    rows = [{'dt_s': dt, 'seed': seed, 'condition': 'control', 'status': 'completed',
             'values': [4, 50, 2, .5], 'initial_poles': [{'id': 'C1', 'position': [0, 0, 0]}]}
            for dt in plan['timesteps_s'] for seed in range(16)]
    return plan, rows


def test_equivalence_requires_complete_replicates_and_unchanged_initial_states():
    plan, rows = study()
    assert assess_coupled(plan, rows)['equivalence_established']
    assert not assess_coupled(plan, rows[:-1])['equivalence_established']
    failed = copy.deepcopy(rows); failed[-1]['status'] = 'failed'
    report = assess_coupled(plan, failed)
    assert not report['equivalence_established'] and len(report['failed_or_missing']) == 1
    changed = copy.deepcopy(rows); changed[-1]['initial_poles'][0]['position'][0] = 1
    assert not assess_coupled(plan, changed)['equivalence_established']


def test_large_bias_or_uncertainty_cannot_be_called_convergence():
    plan, rows = study()
    for r in rows:
        if r['dt_s'] == .0005: r['values'][0] += 1
    endpoint = assess_coupled(plan, rows)['conditions'][0]['endpoints'][0]
    assert endpoint['approximate_90pct_interval'] == [1, 1] and not endpoint['equivalent']
    plan, rows = study()
    for r in rows:
        if r['dt_s'] == .0005: r['values'][0] += 4 if r['seed'] % 2 else -4
    endpoint = assess_coupled(plan, rows)['conditions'][0]['endpoints'][0]
    assert endpoint['fine_minus_middle'] == 0 and not endpoint['equivalent']
    with pytest.raises(ValueError, match='duplicate'):
        assess_coupled(plan, rows + [rows[0]])
