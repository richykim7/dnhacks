"""Private paired count effects; approximate NB/Wald inference, no e calibration."""
from __future__ import annotations

from importlib.metadata import version
import numpy as np
from .expression_design import validate_arrays

PYDESEQ2_VERSION = '0.5.4'


def paired_count_effects(arrays):
    pairs = validate_arrays(arrays, 'counts')
    if len(pairs) < 3:
        raise ValueError('At least three independent pairs required for approximate effects')
    if version('pydeseq2') != PYDESEQ2_VERSION:
        raise ValueError('Unsupported PyDESeq2 version')
    import pandas as pd
    from pydeseq2.dds import DeseqDataSet
    from pydeseq2.ds import DeseqStats
    x = arrays['X']
    if (x > np.iinfo(np.int64).max // max(1, x.shape[1])).any() or (x.sum(axis=1) <= 0).any():
        raise ValueError('Invalid count totals')
    metadata = pd.DataFrame({'donor': arrays['unit_ids'], 'condition': arrays['condition']}, index=arrays['sample_ids'])
    # Validate the declared paired design independently before fitting.
    design = np.column_stack([np.ones(len(x)), pd.get_dummies(metadata['donor'], drop_first=True).to_numpy(dtype=float),
                              (metadata['condition'] == 'treatment').to_numpy(dtype=float)])
    if np.linalg.matrix_rank(design) != design.shape[1] or design.shape[0] <= design.shape[1]:
        raise ValueError('Rank deficient or unreplicated design')
    counts = pd.DataFrame(x.astype(np.int64), index=arrays['sample_ids'], columns=arrays['genes'])
    dds = DeseqDataSet(counts=counts, metadata=metadata, design='~ donor + condition', refit_cooks=True, n_cpus=1, quiet=True)
    dds.deseq2()
    stats = DeseqStats(dds, contrast=['condition', 'treatment', 'control'], n_cpus=1, quiet=True)
    stats.summary()
    fields = ['baseMean', 'log2FoldChange', 'lfcSE', 'stat', 'pvalue', 'padj']
    records = [{'gene': str(g), **{k: float(row[k]) if np.isfinite(row[k]) else None for k in fields}}
               for g, row in stats.results_df.iterrows()]
    return {'method': 'PyDESeq2', 'version': PYDESEQ2_VERSION, 'design': '~ donor + condition',
            'inference': 'model-based approximate; no finite-sample e-value', 'lfc': 'unshrunk MLE',
            'independent_filtering': True, 'cooks_filter': True, 'results': records}
