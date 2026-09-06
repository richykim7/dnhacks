"""Durable bounded design receipts. An interrupted worker never silently reruns inference."""
from __future__ import annotations
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .geometry import canonical, digest

BINDCRAFT_COMMIT = "efb5bfeb8b4b1a5944256f979c34e0c8e6a82d9d"
TERMINAL = {"completed", "failed", "canceled", "resource_exhausted", "interrupted"}


def plan_design(target: dict, epitope: dict, *, lengths: list[int], seeds: list[int],
                candidate_cap: int, gpu_seconds: int, trajectory_cap: int, artifact_bytes: int,
                environment_sha256: str, weights_sha256: str, filters_sha256: str,
                advanced_sha256: str) -> dict:
    if epitope["target_sha256"] != digest(target):
        raise ValueError("Epitope target hash is stale")
    if len(lengths) != 2 or any(type(n) is not int for n in lengths) or not 30 <= lengths[0] <= lengths[1] <= 250:
        raise ValueError("Binder length range must be 30–250 residues")
    if seeds:
        raise ValueError("Pinned upstream BindCraft samples seeds internally; explicit seed control unsupported")
    for value, cap in ((candidate_cap,20),(gpu_seconds,3600),(trajectory_cap,100),(artifact_bytes,100*1024*1024)):
        if type(value) is not int or not 1 <= value <= cap:
            raise ValueError("Resource budget outside supported pilot bounds")
    for value in (environment_sha256,weights_sha256,filters_sha256,advanced_sha256):
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError("Pinned environment, weights and settings hashes required")
    ids={r['id']:r for r in target['residues']}
    if not set(epitope['selected'])<=ids.keys():
        raise ValueError("Target residues absent")
    if any(ids[r]['insertion_code'] or len(ids[r]['chain'])!=1 for r in epitope['selected']):
        raise ValueError("BindCraft hotspot notation cannot preserve this insertion code or chain alias")
    return {"schema":"binder_design_protocol.v1","engine":"BindCraft","commit":BINDCRAFT_COMMIT,
            "target_sha256":digest(target),"epitope_sha256":digest(epitope),"lengths":lengths,
            "seed_policy":"upstream-random-recorded-in-output","candidate_cap":candidate_cap,
            "gpu_seconds":gpu_seconds,"trajectory_cap":trajectory_cap,"artifact_bytes":artifact_bytes,
            "simultaneous_jobs":1,"environment_sha256":environment_sha256,"weights_sha256":weights_sha256,
            "filters_sha256":filters_sha256,"advanced_sha256":advanced_sha256,
            "hotspots":','.join(f"{ids[r]['chain']}{ids[r]['auth_seq_id']}" for r in epitope['selected']),
            "resource_estimate":{"status":"unmeasured","pilot_required":True}}


def validate_protocol(p):
    if p.get('schema')!='binder_design_protocol.v1' or p.get('engine')!='BindCraft' or p.get('commit')!=BINDCRAFT_COMMIT:
        raise ValueError('Unsupported immutable protocol')
    for key,cap in (('candidate_cap',20),('gpu_seconds',3600),('trajectory_cap',100),('artifact_bytes',100*1024*1024)):
        if type(p.get(key)) is not int or not 1<=p[key]<=cap:raise ValueError('Invalid resource cap')
    if p.get('simultaneous_jobs')!=1 or p.get('seed_policy')!='upstream-random-recorded-in-output':
        raise ValueError('Unsupported launch settings')
    if len(p.get('lengths',[]))!=2 or any(type(n) is not int for n in p['lengths']) or not 30<=p['lengths'][0]<=p['lengths'][1]<=250:
        raise ValueError('Invalid length range')
    for key in ('target_sha256','epitope_sha256','environment_sha256','weights_sha256','filters_sha256','advanced_sha256'):
        value=p.get(key)
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Missing immutable dependency hash')
    if not isinstance(p.get('hotspots'),str) or not p['hotspots']:raise ValueError('Missing hotspots')
    canonical(p)


class DesignStore:
    def __init__(self,directory):
        self.root=Path(directory);self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/'binder.sqlite3'
        with self.connect() as con:
            con.executescript('''CREATE TABLE IF NOT EXISTS jobs(
              receipt TEXT PRIMARY KEY, scope TEXT NOT NULL, idem TEXT NOT NULL,
              protocol_hash TEXT NOT NULL, protocol TEXT NOT NULL, status TEXT NOT NULL,
              owner TEXT, updated REAL NOT NULL, UNIQUE(scope,idem));
              CREATE TABLE IF NOT EXISTS events(
              cursor INTEGER PRIMARY KEY AUTOINCREMENT,receipt TEXT NOT NULL,
              event_key TEXT NOT NULL,body TEXT NOT NULL,UNIQUE(receipt,event_key));''')

    @contextmanager
    def connect(self):
        con=sqlite3.connect(self.db,timeout=30);con.row_factory=sqlite3.Row
        try:
            con.execute('PRAGMA synchronous=FULL')
            con.execute('BEGIN IMMEDIATE')
            with con:yield con
        finally:con.close()

    def _job(self,con,receipt,scope):
        row=con.execute('SELECT * FROM jobs WHERE receipt=? AND scope=?',(receipt,canonical(scope).decode())).fetchone()
        if row is None:raise FileNotFoundError('Receipt not in this experiment scope')
        return dict(row)

    def start_design(self,protocol,*,scope,idempotency_key):
        if set(scope)!={'project_id','run_id','experiment_id'} or any(not isinstance(v,str) or not v for v in scope.values()):
            raise ValueError('Complete experiment scope required')
        if not isinstance(idempotency_key,str) or not 1<=len(idempotency_key)<=128:
            raise ValueError('Invalid idempotency key')
        validate_protocol(protocol)
        p=canonical(protocol).decode();sc=canonical(scope).decode();h=digest(protocol)
        with self.connect() as con:
            old=con.execute('SELECT receipt,protocol_hash FROM jobs WHERE scope=? AND idem=?',(sc,idempotency_key)).fetchone()
            if old:
                if old['protocol_hash']!=h:raise ValueError('Idempotency key reused for different protocol')
                return {'receipt':old['receipt'],'protocol_sha256':h}
            receipt=uuid4().hex
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)',(receipt,sc,idempotency_key,h,p,'queued',None,time.time()))
            con.execute('INSERT INTO events(receipt,event_key,body) VALUES(?,?,?)',(receipt,'queued',canonical({'state':'queued'}).decode()))
            return {'receipt':receipt,'protocol_sha256':h}

    def claim(self,receipt,scope,owner):
        if not owner:raise ValueError('Worker identity required')
        with self.connect() as con:
            row=self._job(con,receipt,scope)
            if row['status']!='queued':raise ValueError('Job already claimed or terminal; explicit new protocol run required')
            if con.execute("SELECT COUNT(*) FROM jobs WHERE status='running'").fetchone()[0]:
                raise ValueError('Simultaneous job cap reached')
            con.execute("UPDATE jobs SET status='running',owner=?,updated=? WHERE receipt=?",(owner,time.time(),receipt))
            con.execute('INSERT INTO events(receipt,event_key,body) VALUES(?,?,?)',(receipt,'running',canonical({'state':'running'}).decode()))
            return json.loads(row['protocol'])

    def recover(self,receipt,scope):
        """Mark a demonstrably dead local worker interrupted; never reclaim or rerun it.

        Different PID namespaces cannot establish absence. An operator must recover those
        receipts from the original host/namespace instead of relying on an elapsed lease.
        """
        from dnhacksbio.explorer.runtime import process_identity
        with self.connect() as con:
            row=self._job(con,receipt,scope)
            if row['status']!='running':return {'receipt':receipt,'state':row['status']}
            here=process_identity()
            try:
                boot,namespace,pid,ticks=row['owner'].split('|')
                current_boot,current_namespace,_,_=here.split('|')
                pid=int(pid)
                if pid<=0 or not ticks.isdigit():raise ValueError()
            except (AttributeError,TypeError,ValueError):
                raise ValueError('Worker process identity cannot be verified') from None
            if boot!=current_boot:
                raise ValueError('Original boot differs; explicit operator reconciliation required')
            if namespace!=current_namespace:
                raise ValueError('Recover from the original worker PID namespace')
            actual=process_identity(pid)
            if actual==row['owner']:
                raise ValueError('Worker is still alive; cancel it explicitly')
            if actual is None and Path(f'/proc/{pid}').exists():
                raise ValueError('Worker identity inaccessible; absence is not established')
            reason='Original local worker exited; partial outputs retained; no automatic retry'
            con.execute("UPDATE jobs SET status='interrupted',updated=? WHERE receipt=?",(time.time(),receipt))
            con.execute('INSERT INTO events(receipt,event_key,body) VALUES(?,?,?)',
                        (receipt,'terminal',canonical({'state':'interrupted','reason':reason}).decode()))
            return {'receipt':receipt,'state':'interrupted'}

    def attach_candidate(self,receipt,scope,bundle_raw:bytes,*,mapping_review,rejection_reason=None):
        """Attach explicitly reviewed raw output after generation ends, including partial failures."""
        return self._publish_candidate(receipt,scope,None,bundle_raw,rejection_reason=rejection_reason,
                                       mapping_review=mapping_review)

    def candidate(self,receipt,scope,owner,bundle_raw:bytes,*,rejection_reason=None):
        return self._publish_candidate(receipt,scope,owner,bundle_raw,rejection_reason=rejection_reason)

    def _publish_candidate(self,receipt,scope,owner,bundle_raw:bytes,*,rejection_reason=None,mapping_review=None):
        from .bundle import validate_bundle
        bundle=validate_bundle(bundle_raw,scope);key=digest(bundle_raw)
        with self.connect() as con:
            row=self._job(con,receipt,scope)
            protocol=json.loads(row['protocol'])
            if mapping_review is None:
                if row['status']!='running' or row['owner']!=owner:raise ValueError('Worker no longer owns running job')
            else:
                if row['status'] not in TERMINAL:raise ValueError('Mapped import requires a terminal generator receipt')
                if not isinstance(mapping_review,dict) or set(mapping_review)!={'source_sha256','target_sha256','policy'}:
                    raise ValueError('Explicit source/target mapping review required')
                if (mapping_review['source_sha256']!=bundle['structure']['source_sha256'] or
                    mapping_review['target_sha256']!=protocol['target_sha256'] or
                    not isinstance(mapping_review['policy'],str) or not 1<=len(mapping_review['policy'].strip())<=2000):
                    raise ValueError('Mapping review source/target identity mismatch')
            if rejection_reason is not None and (not isinstance(rejection_reason,str) or not 1<=len(rejection_reason.strip())<=2000):
                raise ValueError('Rejection reason must be a concise nonempty string')
            if bundle['protocol']!=protocol:raise ValueError('Candidate protocol mismatch')
            event_key='candidate:'+key
            if con.execute('SELECT 1 FROM events WHERE receipt=? AND event_key=?',(receipt,event_key)).fetchone():return key
            previous=[json.loads(r[0]) for r in con.execute('SELECT body FROM events WHERE receipt=?',(receipt,))]
            emitted=[e for e in previous if e.get('bundle_sha256')]
            if len(emitted)>=protocol['candidate_cap'] or sum(e['byte_length'] for e in emitted)+len(bundle_raw)>protocol['artifact_bytes']:
                raise ValueError('Candidate or artifact budget exhausted')
            destination=self.root/key
            # Content addressing plus exclusive create makes retry after an interrupted publication safe.
            if destination.exists():
                if digest(destination.read_bytes())!=key:raise ValueError('Corrupt candidate blob')
            else:
                with destination.open('xb') as f:
                    f.write(bundle_raw);f.flush()
                    import os
                    os.fsync(f.fileno())
            body={'state':'candidate','bundle_sha256':key,'byte_length':len(bundle_raw),
                  'candidate_id':bundle['manifest']['candidate_id'],'rejection_reason':rejection_reason,
                  'mapping_review':mapping_review,'generator_state':row['status']}
            con.execute('INSERT INTO events(receipt,event_key,body) VALUES(?,?,?)',(receipt,event_key,canonical(body).decode()))
        return key

    def finish(self,receipt,scope,owner,state,reason,*,preserve_terminal=False):
        if state not in TERMINAL or not reason:raise ValueError('Explicit terminal state and reason required')
        with self.connect() as con:
            row=self._job(con,receipt,scope)
            if row['status'] in TERMINAL:
                if row['status']==state or preserve_terminal:return
                raise ValueError('Terminal state immutable')
            if row['owner']!=owner:raise ValueError('Worker identity mismatch')
            con.execute('UPDATE jobs SET status=?,updated=? WHERE receipt=?',(state,time.time(),receipt))
            con.execute('INSERT INTO events(receipt,event_key,body) VALUES(?,?,?)',(receipt,'terminal',canonical({'state':state,'reason':reason}).decode()))

    def cancel(self,receipt,scope):
        with self.connect() as con:row=self._job(con,receipt,scope)
        self.finish(receipt,scope,row['owner'],'canceled','Canceled by experiment owner; partial candidates retained')

    def collect_candidates(self,receipt,scope,after=0):
        if type(after) is not int or after<0:raise ValueError('Invalid event cursor')
        with self.connect() as con:
            row=self._job(con,receipt,scope)
            events=[{'cursor':r[0],**json.loads(r[1])} for r in con.execute('SELECT cursor,body FROM events WHERE receipt=? AND cursor>? ORDER BY cursor',(receipt,after))]
            return {'receipt':receipt,'state':row['status'],'events':events,'cursor':events[-1]['cursor'] if events else after}
