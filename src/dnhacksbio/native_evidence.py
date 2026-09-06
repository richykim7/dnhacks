"""Versioned native association kernel and operator-only frozen-critic ledger.

This module has no discovery read surface. Put its directory behind a real OS
permission boundary. Append mode is deliberately limited to a fully frozen
bilinear critic; adaptive optimizer/RNG state is not supported in v1.
"""
from __future__ import annotations

import json
import hashlib
import math
import os
from pathlib import Path
import sqlite3
from contextlib import contextmanager

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


KERNEL = 'native-two-view-four-term-v1'


def association_factor(scores, stake=0.9):
    """One factor from (c11,c22,c12,c21), evaluated by one predictable critic."""
    scores = np.asarray(scores, dtype=float)
    if scores.shape != (4,) or not np.isfinite(scores).all() or np.any(np.abs(scores) > 1):
        raise ValueError('Four finite critic scores in [-1,1] required')
    if not np.isfinite(stake) or not 0 <= stake <= 0.9:
        raise ValueError('Stake must be in [0,0.9]')
    h = float((scores[0]+scores[1]-scores[2]-scores[3])/4)
    return 1 + stake*h


def frozen_scores(x, y, weights):
    x, y, w = (np.asarray(v, dtype=float) for v in (x, y, weights))
    if x.ndim != 2 or y.ndim != 2 or len(x) != 2 or len(y) != 2 or w.shape != (x.shape[1], y.shape[1]):
        raise ValueError('Invalid frozen critic dimensions')
    if not all(np.isfinite(v).all() for v in (x, y, w)):
        raise ValueError('Nonfinite frozen critic input')
    with np.errstate(over='raise', invalid='raise'):
        matrix = np.tanh(x @ w @ y.T)
    return [float(matrix[0, 0]), float(matrix[1, 1]), float(matrix[0, 1]), float(matrix[1, 0])]


class PrivateProcessStore:
    """Atomic score/cursor/ledger transition, with globally disjoint donor use.

    More permissive investigation-level reuse requires a separately reviewed
    policy. Global disjointness is deliberately conservative. Receipt aliases
    resolve to the same immutable process and cannot reset its wealth.
    """
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        self.path = self.directory / 'native.sqlite3'
        with self.connect() as con:
            con.executescript('''
              CREATE TABLE IF NOT EXISTS processes (
                id TEXT PRIMARY KEY, spec TEXT NOT NULL, cursor INTEGER NOT NULL DEFAULT 0,
                log_wealth REAL NOT NULL DEFAULT 0);
              CREATE TABLE IF NOT EXISTS aliases (receipt TEXT PRIMARY KEY, process TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS consumed (donor TEXT PRIMARY KEY, process TEXT NOT NULL, block INTEGER NOT NULL);
              CREATE TABLE IF NOT EXISTS blocks (
                process TEXT NOT NULL, number INTEGER NOT NULL, digest TEXT NOT NULL,
                factor REAL NOT NULL, log_wealth REAL NOT NULL, snapshot TEXT NOT NULL,
                PRIMARY KEY(process,number));
            ''')
        os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=30)
        try:
            with con:
                con.execute('PRAGMA synchronous=FULL')
                yield con
        finally:
            con.close()

    def register(self, receipt, spec):
        from .experiment_transport import REQUEST_ID
        if not isinstance(receipt, str) or not REQUEST_ID.fullmatch(receipt):
            raise ValueError('Invalid receipt')
        required = {'kernel', 'null', 'population', 'panel', 'model_hashes', 'qc_hash', 'data_hash',
                    'crosswalk_hash', 'acquisition_hash', 'family', 'parent', 'sampling', 'exclusions',
                    'weights', 'stake', 'eligible_donors', 'reuse_policy', 'schedule'}
        if set(spec) != required or spec['kernel'] != KERNEL or spec['schedule'] != 'fully-frozen-v1':
            raise ValueError('Unsupported process specification')
        if spec['reuse_policy'] != 'globally-disjoint-canonical-donors-v1':
            raise ValueError('Unsupported investigation reuse policy')
        names([spec[k] for k in ('null', 'population', 'panel', 'family', 'parent', 'sampling')])
        for value in [spec[k] for k in ('qc_hash', 'data_hash', 'crosswalk_hash', 'acquisition_hash')] + list(spec['model_hashes']):
            if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
                raise ValueError('Immutable references must be SHA256')
        if len(spec['model_hashes']) != 2:
            raise ValueError('Two separately frozen models required')
        donors = names(spec['eligible_donors'], unique=True)
        exclusions = names(spec['exclusions'], unique=True) if spec['exclusions'] else ()
        if len(donors) < 2 or set(donors) & set(exclusions):
            raise ValueError('Invalid eligible donor ledger')
        w = np.asarray(spec['weights'], dtype=float)
        if w.ndim != 2 or not all(w.shape) or w.size > 1_000_000 or not np.isfinite(w).all():
            raise ValueError('Invalid critic')
        association_factor([0, 0, 0, 0], spec['stake'])
        process = digest(spec)
        value = json.dumps(spec, sort_keys=True, allow_nan=False)
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            old = con.execute('SELECT process FROM aliases WHERE receipt=?', (receipt,)).fetchone()
            if old and old[0] != process:
                raise ValueError('Conflicting receipt retry')
            con.execute('INSERT OR IGNORE INTO processes(id,spec) VALUES (?,?)', (process, value))
            con.execute('INSERT OR IGNORE INTO aliases VALUES (?,?)', (receipt, process))
        return {'receipt': receipt, 'status': 'accepted'}

    def advance(self, receipt, number, donors, x, y, *, before_commit=None):
        """Private operator supplies the next two measured bags, in locked order.

        A retry must supply identical observations. Callback is a fault-injection
        seam for crash tests; any exception rolls back the entire transition.
        """
        donors = names(donors, unique=True)
        if len(donors) != 2 or type(number) is not int or number < 0:
            raise ValueError('Exactly two fresh donors per block')
        block_hash = digest(dict(donors=donors, x=np.asarray(x).tolist(), y=np.asarray(y).tolist()))
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT p.id,p.spec,p.cursor,p.log_wealth FROM processes p JOIN aliases a ON a.process=p.id WHERE a.receipt=?', (receipt,)).fetchone()
            if row is None:
                raise ValueError('Unknown receipt')
            process, raw, cursor, log_wealth = row
            spec = json.loads(raw)
            old = con.execute('SELECT digest FROM blocks WHERE process=? AND number=?', (process, number)).fetchone()
            if old:
                if old[0] != block_hash:
                    raise ValueError('Conflicting replay')
                return
            if number != cursor or list(donors) != spec['eligible_donors'][2*cursor:2*cursor+2]:
                raise ValueError('Donor cursor/order mismatch')
            for donor in donors:
                if con.execute('SELECT 1 FROM consumed WHERE donor=?', (donor,)).fetchone():
                    raise ValueError('Canonical donor already consumed, including another modality/process')
            factor = association_factor(frozen_scores(x, y, spec['weights']), spec['stake'])
            log_wealth += math.log(factor)
            snapshot = json.dumps({'critic': spec['weights'], 'optimizer': None, 'rng': None,
                                   'schedule': spec['schedule'], 'spec_hash': process, 'donors': donors,
                                   'x': np.asarray(x).tolist(), 'y': np.asarray(y).tolist()}, allow_nan=False)
            con.execute('INSERT INTO blocks VALUES (?,?,?,?,?,?)', (process, number, block_hash, factor, log_wealth, snapshot))
            con.executemany('INSERT INTO consumed VALUES (?,?,?)', [(d, process, number) for d in donors])
            con.execute('UPDATE processes SET cursor=?,log_wealth=? WHERE id=?', (cursor+1, log_wealth, process))
            if before_commit:
                before_commit()

    def export(self, receipt):
        """Private operator only; never attach this result to a discovery artifact."""
        with self.connect() as con:
            row = con.execute('SELECT p.id,p.spec,p.cursor,p.log_wealth FROM processes p JOIN aliases a ON a.process=p.id WHERE a.receipt=?', (receipt,)).fetchone()
            if row is None:
                raise ValueError('Unknown receipt')
            process, spec, cursor, wealth = row
            blocks = con.execute('SELECT number,factor,log_wealth FROM blocks WHERE process=? ORDER BY number', (process,)).fetchall()
        return dict(process=process, spec=json.loads(spec), cursor=cursor, log_wealth=wealth,
                    blocks=[dict(number=n, factor=f, log_wealth=w) for n, f, w in blocks])
