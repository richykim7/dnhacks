#!/usr/bin/env python3
"""Plot existing measurements and explicitly defined controls; never train a model."""
import hashlib
import json
from pathlib import Path

import numpy as np
from matplotlib import pyplot as plt
from build_figures import style, GREEN, AMBER, MUTED, GRID, IVORY

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
OUT = ROOT / 'assets/revision/plots'


def build():
    style()
    OUT.mkdir(parents=True, exist_ok=True)
    source = REPO / 'research/learned-evalue-validation/real-expression'
    training = json.loads((source / 'training.json').read_text())
    evaluation = json.loads((source / 'evaluation.json').read_text())
    recorded = {}

    def canvas():
        fig, ax = plt.subplots(figsize=(10, 5.5), dpi=160)
        fig.subplots_adjust(left=.10, right=.97, top=.86, bottom=.18)
        ax.grid(axis='y', color=GRID, linewidth=.7)
        ax.set_axisbelow(True)
        return fig, ax

    def save(fig, name, description):
        for extension in ('png', 'pdf'):
            path = OUT / f'{name}.{extension}'
            fig.savefig(path, dpi=160)
            recorded[path.name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'description': description}
        plt.close(fig)

    fig, ax = canvas()
    loss = training['autoencoder']['training_loss']
    ax.plot(np.arange(1, len(loss)+1), loss, color=GREEN, linewidth=3, label='Masked encoder · TRAIN')
    # Each nonconstant gene has empirical TRAIN variance 1 after frozen standardization.
    # A predictor returning its TRAIN mean is zero in these coordinates. Uniform
    # masks therefore have expected MSE approximately 1, not a measured validation curve.
    ax.axhline(1, color=AMBER, linestyle='--', linewidth=2, label='TRAIN-mean predictor · expected ≈1')
    ax.set(xlabel='Training epoch', ylabel='Masked standardized MSE', ylim=(0, 1.3), xlim=(1,100))
    ax.legend(loc='upper right', frameon=False, fontsize=14)
    ax.annotate(f'{loss[-1]:.3f}', (100, loss[-1]), xytext=(-57, 12), textcoords='offset points', color=GREEN, weight='bold', fontsize=22)
    save(fig, 'training-baseline', 'Recorded 100-epoch TRAIN masked MSE; dashed line is the analytically defined TRAIN-mean predictor, expected MSE approximately 1 after standardization. Not a held-out result. No matched random-network experiment was run.')

    fig, ax = canvas()
    pairs = [8,12,16,20,24,28,30]
    methods = evaluation['primary']['methods']
    for key, label, col, lw in [('autoencoder','Learned encoder',GREEN,3.3), ('pca','PCA baseline',MUTED,2.2), ('scalar','IFIT3 comparator',AMBER,2.2)]:
        ax.plot(pairs, np.exp(methods[key]['log_wealth_path']), marker='o', markersize=4, color=col, linewidth=lw, label=label)
    ax.axhline(1, color=IVORY, alpha=.55, linestyle=':', linewidth=1.5, label='Constant critic · E = 1')
    ax.axhline(20, color=IVORY, alpha=.65, linestyle='--', linewidth=1.4)
    ax.text(8.5,25,'Anytime threshold: 20', fontsize=12, color=IVORY)
    ax.set(xlabel='Pairs observed · first 8 are burn-in', ylabel='Evidence wealth E · log scale', yscale='log', ylim=(.7,20000), xlim=(8,30))
    ax.legend(loc='upper left', frameon=False, fontsize=12, ncol=2)
    save(fig, 'evidence-baselines', 'Predeclared real-expression primary seed, 30 selected disjoint donor pairs, 8 unscored burn-in/22 scored. All three predeclared representation comparisons retained. Constant critic g=0 gives exactly E=1; it is an analytic no-information control, not an empirical random-model run. PCA64 vs learned128 are not dimension-matched. IFIT3 produces stronger final evidence than learned.')

    manifest = {'sources': {name: hashlib.sha256((source/name).read_bytes()).hexdigest() for name in ['training.json','evaluation.json']}, 'figures': recorded}
    (OUT/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    build()
