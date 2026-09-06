"""Sparse UMI counts and explicit specimen-to-donor provenance for development.

No cell, lane, section or modality is an independent biological replicate.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def names(values, *, unique=False):
    values = tuple(values)
    if not values or any(not isinstance(v, str) or not v or v.strip() != v for v in values):
        raise ValueError('Nonempty canonical string identifiers required')
    if unique and len(set(values)) != len(values):
        raise ValueError('Duplicate identifiers')
    return values


@dataclass
class CountData:
    """CSR cells × genes, with JSON cell metadata and an audited local crosswalk."""
    data: np.ndarray
    indices: np.ndarray
    indptr: np.ndarray
    genes: tuple
    cells: list[dict]
    manifest: dict

    def validate(self, *, roles=('training', 'development')):
        names(self.genes, unique=True)
        if not self.cells:
            raise ValueError('Empty cell collection')
        names([c['cell_id'] for c in self.cells], unique=True)
        for a in (self.data, self.indices, self.indptr):
            if a.ndim != 1 or a.dtype.kind not in 'iu':
                raise ValueError('CSR arrays must be one-dimensional integers')
        if (self.data < 0).any() or (self.data > 2**53).any():
            raise ValueError('Invalid counts or count precision overflow')
        if len(self.indices) != len(self.data) or self.indptr.shape != (len(self.cells) + 1,):
            raise ValueError('CSR dimensions differ')
        if self.indptr[0] != 0 or self.indptr[-1] != len(self.data) or np.any(self.indptr[1:] < self.indptr[:-1]):
            raise ValueError('Invalid CSR pointers')
        if np.any(self.indices < 0) or np.any(self.indices >= len(self.genes)):
            raise ValueError('Invalid gene index')
        for i in range(len(self.cells)):
            idx = self.indices[self.indptr[i]:self.indptr[i+1]]
            if np.any(idx[1:] <= idx[:-1]):
                raise ValueError('CSR indices must be sorted without duplicates')
        m = self.manifest
        if m.get('library_size_rule', 'sum-supplied-panel') not in ('sum-supplied-panel', 'measured-all-genes'):
            raise ValueError('Unsupported library measurement rule')
        if m.get('schema') != 'ecosystem-counts-v1' or m.get('scale') != 'UMI counts':
            raise ValueError('Explicit UMI count schema required; TPM is unsupported')
        for key in ('population', 'organism', 'tissue', 'assay', 'ontology', 'state_dictionary', 'sampling_justification', 'specimen_rule'):
            names([m[key]])
        if m['assay'] not in ('scRNA', 'snRNA'):
            raise ValueError('Only dissociated scRNA/snRNA counts supported')
        sources = m['sources']
        if not sources or len({s['accession'] for s in sources}) != len(sources):
            raise ValueError('Unique source inventory required')
        source_map = {s['accession']: s for s in sources}
        for s in sources:
            names([s[k] for k in ('accession', 'license', 'access_status', 'role')])
            if s['role'] not in roles or s['access_status'] != 'verified-local':
                raise ValueError('Source role or access unavailable for this operation')
            if len(s['sha256']) != 64 or any(c not in '0123456789abcdef' for c in s['sha256']):
                raise ValueError('Source checksum required')
        crosswalk = {}
        donor_roles = {}
        for row in m['crosswalk']:
            names([row[k] for k in ('accession', 'specimen', 'donor', 'timepoint')])
            key = (row['accession'], row['specimen'])
            if key in crosswalk or row.get('identity_reviewed') is not True:
                raise ValueError('Duplicate or unresolved specimen identity')
            if row['accession'] not in source_map:
                raise ValueError('Unknown source')
            role = source_map[row['accession']]['role']
            donor_roles.setdefault(row['donor'], set()).add(role)
            crosswalk[key] = row
        if any(len(v) != 1 for v in donor_roles.values()):
            raise ValueError('Canonical donor overlaps data roles')
        specimens = {}
        for cell in self.cells:
            names([cell[k] for k in ('cell_id', 'accession', 'specimen', 'compartment', 'state')])
            row = crosswalk.get((cell['accession'], cell['specimen']))
            if row is None:
                raise ValueError('Cell absent from crosswalk')
            specimens.setdefault(row['donor'], set()).add((row['accession'], row['specimen']))
        # Release one chooses one specimen explicitly; aggregation of repeated specimens
        # needs another versioned measurement rule, not an implicit sum.
        if m['specimen_rule'] != 'one-preselected-specimen-per-donor' or any(len(v) != 1 for v in specimens.values()):
            raise ValueError('Preselect exactly one specimen per canonical donor')
        return crosswalk

    def rows(self, rows):
        """Densify only a requested bounded batch; never the complete atlas."""
        rows = list(rows)
        if len(rows) * len(self.genes) > 8_000_000:
            raise ValueError('Dense batch exceeds memory bound')
        out = np.zeros((len(rows), len(self.genes)), dtype=np.float64)
        for j, i in enumerate(rows):
            if not 0 <= i < len(self.cells):
                raise ValueError('Invalid row')
            start, stop = self.indptr[i:i+2]
            out[j, self.indices[start:stop]] = self.data[start:stop]
        if (self.manifest.get('library_size_rule') != 'measured-all-genes' and np.any(out.sum(axis=1) <= 0)) or np.any(out.sum(axis=1) > 2**53):
            raise ValueError('Empty library or library precision overflow')
        if self.manifest.get('library_size_rule') == 'measured-all-genes':
            self.library_sizes(rows, out)
        return out

    def library_sizes(self, rows, counts=None):
        rows = list(rows)
        if self.manifest.get('library_size_rule') == 'measured-all-genes':
            totals = np.asarray([self.cells[i]['library_size'] for i in rows], dtype=float)
        else:
            totals = (self.rows(rows) if counts is None else counts).sum(axis=1)
        if not np.isfinite(totals).all() or np.any(totals <= 0) or np.any(totals > 2**53) or np.any(totals != np.floor(totals)):
            raise ValueError('Invalid measured library offsets')
        if counts is not None and np.any(totals < counts.sum(axis=1)):
            raise ValueError('Library offset below measured selected counts')
        return totals

    def identity(self):
        h = hashlib.sha256()
        for a in (self.data, self.indices, self.indptr):
            h.update(np.asarray(a, dtype='<u8').tobytes())
        h.update(digest({'genes': self.genes, 'cells': self.cells, 'manifest': self.manifest}).encode())
        return h.hexdigest()

    def save(self, path):
        self.validate()
        with Path(path).open('wb') as stream:
            np.savez_compressed(stream, data=self.data, indices=self.indices, indptr=self.indptr,
                                metadata=json.dumps(dict(genes=self.genes, cells=self.cells, manifest=self.manifest), sort_keys=True))

    @classmethod
    def load(cls, path, *, roles=('training', 'development')):
        arrays = safe_npz(path, {'data', 'indices', 'indptr', 'metadata'}, max_bytes=512*1024**2)
        meta = json.loads(str(arrays['metadata']))
        result = cls(arrays['data'], arrays['indices'], arrays['indptr'], tuple(meta['genes']), meta['cells'], meta['manifest'])
        result.validate(roles=roles)
        return result


def safe_npz(path, fields, *, max_bytes=128*1024**2):
    """Check headers and expansion before NumPy allocates attacker-declared shapes."""
    import zipfile
    import math
    path = Path(path)
    if path.stat().st_size > max_bytes:
        raise ValueError('Input archive too large')
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) != len(fields) or {i.filename for i in entries} != {k+'.npy' for k in fields}:
            raise ValueError('Invalid archive fields')
        if sum(i.file_size for i in entries) > max_bytes:
            raise ValueError('Expanded input too large')
        for entry in entries:
            with archive.open(entry) as stream:
                version = np.lib.format.read_magic(stream)
                reader = {(1,0):np.lib.format.read_array_header_1_0, (2,0):np.lib.format.read_array_header_2_0}.get(version)
                if reader is None:
                    raise ValueError('Unsupported array version')
                shape, _, dtype = reader(stream)
                if dtype.hasobject or dtype.kind not in 'iufUS' or math.prod(shape)*dtype.itemsize != entry.file_size-stream.tell():
                    raise ValueError('Invalid array storage')
    with np.load(path, allow_pickle=False) as arrays:
        return {k:arrays[k] for k in fields}


def bags(dataset, compartment, *, min_cells, cells_per_donor, seed, roles=('development',)):
    crosswalk = dataset.validate(roles=roles)
    if type(min_cells) is not int or type(cells_per_donor) is not int or not 1 <= min_cells <= cells_per_donor:
        raise ValueError('Freeze positive minimum and per-compartment subsample size')
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError('Invalid subsampling seed')
    groups = {r['donor']: [] for r in crosswalk.values()}
    for i, cell in enumerate(dataset.cells):
        if cell['compartment'] == compartment:
            groups[crosswalk[cell['accession'], cell['specimen']]['donor']].append(i)
    selected, missing = {}, {}
    for donor, rows in sorted(groups.items()):
        # Fixed size avoids exposing capture-depth variation as a view feature.
        if len(rows) < cells_per_donor:
            missing[donor] = {'available_cells': len(rows), 'reason': 'insufficient-compartment-coverage'}
            continue
        rows.sort(key=lambda i: dataset.cells[i]['cell_id'])
        local_seed = int(digest([seed, compartment, donor])[:16], 16)
        chosen = np.random.default_rng(local_seed).choice(rows, cells_per_donor, replace=False)
        selected[donor] = chosen.tolist()
    return selected, missing
