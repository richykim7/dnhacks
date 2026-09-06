#!/usr/bin/env python3
"""Synthetic paired-score operating curves; an implementation check, not a validity proof."""
import argparse
import json
import math
import numpy as np
from dnhacksbio.pathway_evalue import paired_randomization


def evaluate(replicates=100, seed=20260906):
    rng = np.random.default_rng(seed)
    rows = []
    for n in (4, 8, 12):
        for effect in (0., .5, 1.):
            for heterogeneous in (False, True):
                rejects = 0
                es = []
                for _ in range(replicates):
                    scale = np.linspace(.5, 2., n) if heterogeneous else np.ones(n)
                    d = rng.normal(size=n)*scale + effect
                    result = paired_randomization(d)
                    rejects += result['e'] >= 20
                    es.append(result['e'])
                rate = rejects / replicates
                # Wilson interval reports simulation uncertainty even for zero rejections.
                z = 1.96
                center = (rate + z*z/(2*replicates))/(1 + z*z/replicates)
                half = z*math.sqrt(rate*(1-rate)/replicates + z*z/(4*replicates**2))/(1+z*z/replicates)
                rows.append({'donors': n, 'effect_sd_units': effect, 'heterogeneous_noise': heterogeneous,
                             'rejection_e_ge_20': rate, 'wilson_95': [max(0., center-half), min(1., center+half)],
                             'mean_e': float(np.mean(es)), 'mean_e_mc_se': float(np.std(es, ddof=1)/math.sqrt(replicates)) if replicates > 1 else None})
    return {'seed': seed, 'replicates_per_cell': replicates, 'results': rows,
            'scope': 'Gaussian independent paired differences; fixed one-sided direction; synthetic only. Unequal/incomplete pairs rejected, not imputed. Feature missingness/coverage checked separately.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replicates', type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.replicates <= 10000:
        parser.error('replicates must be between 1 and 10000')
    print(json.dumps(evaluate(args.replicates), indent=2, allow_nan=False))
