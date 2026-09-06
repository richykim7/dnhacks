"""Bounded private expression arrays and independently paired donor design."""
from __future__ import annotations

import io
import math
import zipfile
import numpy as np

FIELDS = {'X', 'genes', 'sample_ids', 'unit_ids', 'pair_ids', 'condition', 'batch'}


def load_arrays(raw):
    if len(raw) > 48 * 1024**2:
        raise ValueError('Input too large')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if len(entries) != len(FIELDS) or {e.filename for e in entries} != {f'{k}.npy' for k in FIELDS}:
            raise ValueError('Invalid NPZ fields')
        if sum(e.file_size for e in entries) > 256 * 1024**2:
            raise ValueError('Expanded input too large')
        for entry in entries:
            with archive.open(entry) as stream:
                version = np.lib.format.read_magic(stream)
                reader = {(1, 0): np.lib.format.read_array_header_1_0,
                          (2, 0): np.lib.format.read_array_header_2_0}.get(version)
                if reader is None:
                    raise ValueError('Unsupported NPY version')
                shape, _, dtype = reader(stream)
                if dtype.hasobject or dtype.kind not in 'iufUS' or math.prod(shape) * dtype.itemsize != entry.file_size - stream.tell():
                    raise ValueError('Invalid array storage')
    with np.load(io.BytesIO(raw), allow_pickle=False) as data:
        return {k: data[k] for k in FIELDS}


def validate_arrays(arrays, scale):
    if set(arrays) != FIELDS:
        raise ValueError('Invalid arrays')
    x = np.asarray(arrays['X'])
    if x.ndim != 2 or not all(x.shape) or x.dtype.kind not in 'iuf' or not np.isfinite(x).all() or (x < 0).any():
        raise ValueError('Invalid expression matrix')
    if scale not in {'TPM', 'counts'}:
        raise ValueError('Unsupported scale')
    if scale == 'counts' and (x != np.floor(x)).any():
        raise ValueError('Counts must be integers')
    for name in FIELDS - {'X'}:
        a = np.asarray(arrays[name])
        length = x.shape[1] if name == 'genes' else x.shape[0]
        if a.shape != (length,) or a.dtype.kind != 'U' or any(not v.strip() or v != v.strip() for v in a):
            raise ValueError('Invalid identifiers')
    for name in ('genes', 'sample_ids'):
        if len(set(arrays[name])) != len(arrays[name]):
            raise ValueError('Duplicate identifiers')
    if set(arrays['condition']) != {'control', 'treatment'}:
        raise ValueError('Unsupported conditions')
    pairs = []
    units = set()
    for pair in sorted(set(arrays['pair_ids'])):
        rows = np.flatnonzero(arrays['pair_ids'] == pair)
        if len(rows) != 2 or set(arrays['condition'][rows]) != {'control', 'treatment'}:
            raise ValueError('Incomplete or duplicated pair')
        donor = set(arrays['unit_ids'][rows])
        if len(donor) != 1 or units.intersection(donor):
            raise ValueError('Donor/pair mismatch or repeated donor')
        units.update(donor)
        if len(set(arrays['batch'][rows])) != 1:
            raise ValueError('Within-pair batch confounding unsupported')
        pairs.append(tuple(int(rows[np.flatnonzero(arrays['condition'][rows] == c)[0]]) for c in ('control', 'treatment')))
    return pairs


def normalized_scores(x, scale):
    x = np.asarray(x, dtype=float)
    if scale == 'counts':
        totals = x.sum(axis=1)
        if not np.isfinite(totals).all() or (totals <= 0).any():
            raise ValueError('Invalid library totals')
        x = x / totals[:, None] * 1e6
    return np.log1p(x)


def aggregate_counts(X, genes, sample_ids, unit_ids, pair_ids, condition, batch, *, cell_types=None, selected_cell_type=None):
    """Operator preparation: sum lanes/cells by donor/condition after external cell typing.

    Input sample IDs identify original lanes/cells. Cell-type selection must be frozen
    externally; this function never infers labels or treats cells as independent donors.
    """
    x = np.asarray(X)
    metadata = [np.asarray(a) for a in (sample_ids, unit_ids, pair_ids, condition, batch)]
    if x.ndim != 2 or x.dtype.kind not in 'iu' or (x < 0).any() or x.size == 0:
        raise ValueError('Raw nonnegative integer counts required')
    if any(a.shape != (len(x),) or a.dtype.kind != 'U' or any(not v.strip() for v in a) for a in metadata):
        raise ValueError('Invalid preparation metadata')
    if len(set(metadata[0])) != len(x):
        raise ValueError('Duplicated original sample IDs')
    if x.max() > np.iinfo(np.int64).max // max(1, x.size):
        raise ValueError('Count overflow')
    keep = np.ones(len(x), dtype=bool)
    if cell_types is not None:
        labels = np.asarray(cell_types)
        if labels.shape != (len(x),) or labels.dtype.kind != 'U' or not selected_cell_type:
            raise ValueError('Externally defined cell type required')
        keep = labels == selected_cell_type
    elif selected_cell_type is not None:
        raise ValueError('Missing external cell types')
    groups = {}
    for i in np.flatnonzero(keep):
        key = (str(metadata[1][i]), str(metadata[3][i]))
        groups.setdefault(key, []).append(int(i))
    output = {k: [] for k in FIELDS}
    output['genes'] = np.asarray(genes)
    for number, (key, rows) in enumerate(sorted(groups.items())):
        for name, column in [('pair_ids', metadata[2]), ('batch', metadata[4])]:
            values = set(column[rows])
            if len(values) != 1:
                raise ValueError('Inconsistent aggregation metadata')
            output[name].append(str(next(iter(values))))
        output['X'].append(x[rows].sum(axis=0, dtype=np.int64))
        output['sample_ids'].append(f'aggregate-{number}')
        output['unit_ids'].append(key[0]); output['condition'].append(key[1])
    output = {k: np.asarray(v) for k, v in output.items()}
    validate_arrays(output, 'counts')
    return output
