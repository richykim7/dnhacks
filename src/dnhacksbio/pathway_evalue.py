"""Fixed weighted expression score; paired assignment evidence, never gene shuffles."""
from __future__ import annotations

import itertools
import math
import numpy as np
from .evalues import p_to_e
from .expression_design import normalized_scores, validate_arrays


def paired_randomization(differences, *, direction=1, exact_limit=65536, seed=0, permutations=9999):
    d = np.asarray(differences, dtype=float)
    if d.ndim != 1 or not len(d) or not np.isfinite(d).all() or direction not in (-1, 1):
        raise ValueError('Invalid differences/direction')
    if type(exact_limit) is not int or not 1 <= exact_limit <= 1048576 or type(seed) is not int or not 0 <= seed < 2**32 or permutations != 9999:
        raise ValueError('Invalid permutation settings')
    d = direction * d
    observed = math.fsum(d) / len(d)
    tolerance = 1e-12 * max(1., float(np.max(np.abs(d))))
    exact = len(d) <= 20 and 2**len(d) <= exact_limit
    rng = np.random.default_rng(seed)
    assignments = itertools.product((-1, 1), repeat=len(d)) if exact else (rng.choice((-1, 1), len(d)) for _ in range(permutations))
    b = sum(math.fsum(d * signs) / len(d) >= observed - tolerance for signs in assignments)
    size = 2**len(d) if exact else permutations
    p = b / size if exact else (1 + b) / (size + 1)
    return {'effect': observed * direction, 'p': p, 'e': p_to_e(p), 'exact': exact,
            'assignments': size, 'seed': seed, 'permutations': permutations, 'n_units': len(d),
            'null': 'No effect on the fixed score for any aliquot under paired random assignment; otherwise justified within-pair swap symmetry',
            'evidence_kind': 'fixed-data; retries are not increments'}


def score_pathway(arrays, protocol, resource):
    pairs = validate_arrays(arrays, protocol['input_scale'])
    if protocol['assignment'] not in {'randomized-pairs', 'swap-symmetry'} or not protocol['assignment_justification'].strip():
        return {'status': 'unavailable', 'reason': 'unsupported_assignment'}
    if len(pairs) < protocol['min_pairs']:
        return {'status': 'unavailable', 'reason': 'insufficient_pairs'}
    weights = resource['weights']
    if not isinstance(weights, dict) or not weights or any(not isinstance(g, str) or not g.strip() or type(w) not in (int, float) or not math.isfinite(w) for g, w in weights.items()):
        raise ValueError('Invalid frozen weights')
    genes = list(arrays['genes'])
    observed = sorted(set(genes) & set(weights))
    missing = sorted(set(weights) - set(genes))
    if len(observed) < protocol['min_targets']:
        return {'status': 'unavailable', 'reason': 'insufficient_coverage', 'observed_targets': len(observed), 'missing_targets': missing}
    z = normalized_scores(arrays['X'], protocol['input_scale'])
    scores = z[:, [genes.index(g) for g in observed]] @ np.array([weights[g] for g in observed])
    differences = [scores[t] - scores[c] for c, t in pairs]
    result = paired_randomization(differences, direction=protocol['direction'], exact_limit=protocol['exact_limit'], seed=protocol['seed'])
    return {**result, 'status': 'completed', 'scale': protocol['input_scale'], 'transformation': 'log1p(TPM)' if protocol['input_scale'] == 'TPM' else 'log1p(1e6*counts/library_total)',
            'observed_targets': len(observed), 'missing_targets': missing, 'statistic': 'mean paired difference of fixed weighted sums',
            'assignment': protocol['assignment'], 'assignment_justification': protocol['assignment_justification']}
