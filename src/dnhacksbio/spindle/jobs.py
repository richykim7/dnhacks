"""Scoped durable jobs with bounded subprocess execution, cancellation and archives."""
from __future__ import annotations
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import time
from uuid import uuid4

from .protocol import canonical, digest, scope_key, validate_protocol
from .cytosim import configuration, export_run
from .analysis import analyze_ensemble
from .bundle import validate

TERMINAL={'completed','failed','canceled','resource_exhausted','interrupted'}


class SpindleStore:
    def __init__(self, directory):
        self.root=Path(directory).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/'spindle.sqlite3'
        with self.connect() as con:
            con.executescript('''CREATE TABLE IF NOT EXISTS jobs(
                receipt TEXT PRIMARY KEY, scope TEXT NOT NULL, idem TEXT NOT NULL,
                spec_hash TEXT NOT NULL, spec TEXT NOT NULL, budget TEXT NOT NULL,
                state TEXT NOT NULL, owner TEXT, cancel INTEGER NOT NULL DEFAULT 0,
                created REAL NOT NULL, updated REAL NOT NULL, UNIQUE(scope,idem));
                CREATE TABLE IF NOT EXISTS events(cursor INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS blobs(hash TEXT NOT NULL, receipt TEXT NOT NULL,
                name TEXT NOT NULL, bytes INTEGER NOT NULL, PRIMARY KEY(hash,receipt,name));''')

    @contextmanager
    def connect(self):
        con=sqlite3.connect(self.db,timeout=30);con.row_factory=sqlite3.Row
        try:
            con.execute('PRAGMA synchronous=FULL');con.execute('BEGIN IMMEDIATE')
            with con:yield con
        finally:con.close()

    def _job(self, con, receipt, scope):
        row=con.execute('SELECT * FROM jobs WHERE receipt=? AND scope=?',(receipt,scope_key(scope))).fetchone()
        if row is None:raise FileNotFoundError('Spindle receipt absent from this experiment')
        return dict(row)

    def _event(self, con, receipt, body):
        con.execute('INSERT INTO events(receipt,body) VALUES(?,?)',(receipt,canonical({**body,'recorded_at':time.time()}).decode()))

    def run_spindle_experiment(self, protocol, *, scope, idempotency_key, budget):
        validate_protocol(protocol);sc=scope_key(scope)
        if not isinstance(idempotency_key,str) or not 1<=len(idempotency_key)<=128:raise ValueError('Idempotency key required')
        if (not isinstance(budget,dict) or set(budget)!={'wall_seconds','artifact_bytes'}
            or type(budget['wall_seconds']) is not int or not 1<=budget['wall_seconds']<=1800
            or type(budget['artifact_bytes']) is not int or not 1024<=budget['artifact_bytes']<=200*1024*1024):
            raise ValueError('Bounded wall time and artifact budget required')
        h=digest(protocol);spec=canonical(protocol).decode();b=canonical(budget).decode()
        with self.connect() as con:
            old=con.execute('SELECT * FROM jobs WHERE scope=? AND idem=?',(sc,idempotency_key)).fetchone()
            if old:
                if old['spec_hash']!=h or old['budget']!=b:raise ValueError('Idempotency key reused with changed science or budget')
                return {'receipt':old['receipt'],'spec_ref':h,'state':old['state']}
            if con.execute("SELECT COUNT(*) FROM jobs WHERE state='queued'").fetchone()[0]>=4:raise ValueError('Spindle pending-job queue is full')
            receipt=uuid4().hex;t=time.time()
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,NULL,0,?,?)',(receipt,sc,idempotency_key,h,spec,b,'queued',t,t))
            self._event(con,receipt,{'state':'queued','spec_ref':h})
        return {'receipt':receipt,'spec_ref':h,'state':'queued'}

    def status(self, receipt, scope, after=0):
        if type(after) is not int or after<0:raise ValueError('Invalid event cursor')
        with self.connect() as con:
            job=self._job(con,receipt,scope)
            events=[{'cursor':r['cursor'],**json.loads(r['body'])} for r in con.execute('SELECT * FROM events WHERE receipt=? AND cursor>? ORDER BY cursor',(receipt,after))]
            blobs=[dict(r) for r in con.execute('SELECT * FROM blobs WHERE receipt=?',(receipt,))]
        return {'receipt':receipt,'state':job['state'],'cancel_requested':bool(job['cancel']),
                'spec_ref':job['spec_hash'],'updated_at':job['updated'],'events':events,'artifacts':blobs}

    def cancel(self, receipt, scope):
        with self.connect() as con:
            job=self._job(con,receipt,scope)
            if job['state'] in TERMINAL:return {'state':job['state']}
            state='canceled' if job['state']=='queued' else job['state']
            con.execute('UPDATE jobs SET cancel=1,state=?,updated=? WHERE receipt=?',(state,time.time(),receipt))
            self._event(con,receipt,{'state':state,'cancel_requested':True})
        return {'state':state,'cancel_requested':True}

    def interrupt(self, receipt, scope, reason):
        """Operator recovery after verifying an old worker is gone; never auto-relaunch."""
        if not isinstance(reason,str) or not reason.strip():raise ValueError('Recovery reason required')
        with self.connect() as con:
            job=self._job(con,receipt,scope)
            if job['state']!='running':raise ValueError('Only interrupted running jobs need recovery')
            con.execute("UPDATE jobs SET state='interrupted',cancel=1,updated=? WHERE receipt=?",(time.time(),receipt))
            self._event(con,receipt,{'state':'interrupted','reason':reason})

    def read_blob(self, receipt, scope, key):
        with self.connect() as con:
            self._job(con,receipt,scope)
            row=con.execute('SELECT * FROM blobs WHERE receipt=? AND hash=?',(receipt,key)).fetchone()
            if row is None:raise FileNotFoundError('Artifact not owned by this job')
        path=self.root/'blobs'/key
        if path.is_symlink():raise ValueError('Artifact symlink rejected')
        raw=path.read_bytes()
        if len(raw)!=row['bytes'] or digest(raw)!=key:raise ValueError('Artifact corruption')
        return raw

    def _publish(self, con, receipt, name, raw):
        key=digest(raw);directory=self.root/'blobs';directory.mkdir(exist_ok=True);path=directory/key
        if path.exists():
            if path.is_symlink() or path.read_bytes()!=raw:raise ValueError('Corrupt immutable artifact')
        else:
            with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        # Identical content can belong to several jobs; ownership is event-backed
        # and publication records require a separate per-job key.
        con.execute('INSERT OR IGNORE INTO blobs VALUES(?,?,?,?)',(key,receipt,name,len(raw)))
        return key

    def execute(self, receipt, scope, *, sim: Path, report: Path, build_manifest: dict, environment=None):
        """Operator worker entry. Executable paths never come from numerical protocols."""
        for key,path in [('sim_sha256',sim),('report_sha256',report)]:
            if not path.is_absolute() or not path.is_file() or digest(path.read_bytes())!=build_manifest.get(key):
                raise ValueError('Operator-pinned solver executable hash mismatch')
        from .protocol import CYTOSIM_COMMIT
        if build_manifest.get('solver_commit')!=CYTOSIM_COMMIT or build_manifest.get('dimensionality')!=3:
            raise ValueError('Pinned 3D build manifest required')
        owner=uuid4().hex
        with self.connect() as con:
            job=self._job(con,receipt,scope)
            if job['state']!='queued':raise ValueError('Job already claimed or terminal; no silent rerun')
            if con.execute("SELECT 1 FROM jobs WHERE state='running'").fetchone():raise ValueError('One worker per spindle store')
            protocol=json.loads(job['spec']);validate_protocol(protocol)
            if digest(protocol)!=job['spec_hash']:raise ValueError('Frozen protocol corruption')
            con.execute("UPDATE jobs SET state='running',owner=?,updated=? WHERE receipt=?",(owner,time.time(),receipt))
            self._event(con,receipt,{'state':'running','build':build_manifest})
        budget=json.loads(job['budget']);deadline=time.monotonic()+budget['wall_seconds']
        directory=self.root/'runs'/receipt
        terminal='failed';reason='Worker failed';archive={};runs=[]
        def check():
            with self.connect() as con:
                current=self._job(con,receipt,scope)
                if current['cancel'] or current['state']!='running':raise InterruptedError('Canceled or recovered by owner')
                con.execute('UPDATE jobs SET updated=? WHERE receipt=?',(time.time(),receipt))
            if time.monotonic()>deadline:raise TimeoutError('Wall-time budget exhausted')
            size=sum(p.stat().st_size for p in directory.rglob('*') if p.is_file())
            if size>budget['artifact_bytes']:raise OverflowError('Artifact budget exhausted')
        def command(args, cwd, output):
            check()
            with output.open('wb') as out, (cwd/'stderr.log').open('ab') as err:
                process=subprocess.Popen([str(x) for x in args],cwd=cwd,stdout=out,stderr=err,
                                         env=environment,start_new_session=True)
                try:
                    while process.poll() is None:
                        check();time.sleep(.05)
                    check()
                    if process.returncode:raise RuntimeError(f'Solver/export command failed with exit {process.returncode}')
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid,signal.SIGTERM)
                        try:process.wait(timeout=2)
                        except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
        try:
            directory.mkdir(parents=True,exist_ok=False)
            for seed in protocol['seeds']:
                for index,condition in enumerate(protocol['conditions']):
                    check();run_dir=directory/f'{seed}-{index}';run_dir.mkdir()
                    config=configuration(protocol,condition,seed);(run_dir/'config.cym').write_text(config)
                    command([sim,f'random_seed={seed}'],run_dir,run_dir/'stdout.log')
                    for kind,name in [('aster','asters.txt'),('fiber:points','fibers.txt'),('fiber','owners.txt')]:
                        command([report,kind,'precision=17','verbose=7'],run_dir,run_dir/name)
                    run=export_run(run_dir,protocol,condition,seed);runs.append(run)
                    with self.connect() as con:
                        self._event(con,receipt,{'state':'running','condition':condition['name'],'seed':seed,
                            'accepted_frames':len(run['frames']),'completed_replicates':len(runs),'configuration_sha256':digest(config.encode())})
            bundle={'schema_version':1,'dimensionality':3,'category':'simulation','model_id':protocol['model_id'],
                    'units':{'length':'um','time':'s'},'radius':protocol['radius_um'],'runs':runs}
            raw=canonical(bundle);validate(raw);(directory/'trajectory.json').write_bytes(raw)
            metrics=analyze_ensemble(bundle,protocol['analysis_plan'])
            (directory/'metrics.json').write_bytes(canonical(metrics))
            (directory/'analysis.py').write_bytes(Path(__file__).with_name('analysis.py').read_bytes())
            import csv
            with (directory/'metrics.csv').open('w',newline='') as f:
                fields=['seed','condition','time_to_bipolar_s','right_censored','observation_end_s','bipolar_dwell_s','final_pole_count']
                writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(metrics['runs'])
            from .chunks import export_chunks
            export_chunks(directory/'chunks',runs)
            check();terminal='completed';reason='All prespecified simulation replicates exported; uncalibrated model'
        except InterruptedError as exc:terminal='canceled';reason=str(exc)
        except (TimeoutError,OverflowError) as exc:terminal='resource_exhausted';reason=str(exc)
        except Exception as exc:terminal='failed';reason=f'{type(exc).__name__}: {exc}'
        # Preserve failures and raw solver files, bounded by the artifact quota.
        with self.connect() as con:
            current=self._job(con,receipt,scope)
            if current['state']=='interrupted':return self.status_unlocked(current)
            if current['cancel']:terminal='canceled';reason='Cancellation requested before publication'
            total=0
            for path in sorted(directory.rglob('*')):
                if path.is_file() and not path.is_symlink():
                    total+=path.stat().st_size
                    if total>budget['artifact_bytes']:continue
                    name=str(path.relative_to(directory));archive[name]=self._publish(con,receipt,name,path.read_bytes())
            manifest={'schema':'spindle_archive.v1','scope':scope,'protocol':protocol,'spec_ref':job['spec_hash'],
                      'build':build_manifest,'files':archive,'state':terminal,'reason':reason,
                      'raw_trajectory':'Cytosim objects.cmo retained byte-for-byte; display reports are separate',
                      'calibration':'not performed','export_precision':'native reporter; recorded build patch determines decimal precision'}
            key=self._publish(con,receipt,'archive.json',canonical(manifest))
            con.execute('UPDATE jobs SET state=?,updated=? WHERE receipt=?',(terminal,time.time(),receipt))
            self._event(con,receipt,{'state':terminal,'reason':reason,'archive_sha256':key})
        return self.status(receipt,scope)

    @staticmethod
    def status_unlocked(job):
        return {'receipt':job['receipt'],'state':job['state']}
