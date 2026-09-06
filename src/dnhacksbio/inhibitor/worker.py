"""Bounded subprocess supervision; cancellations/timeouts never publish partial bundles."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from dnhacksbio.explorer.runtime import Journal, process_identity
from .service import Workbench, atomic, lock


def main(trace_dir, job_id):
    j=Journal(Path(trace_dir))
    directory=j.directory/'inhibitor'/'jobs'/job_id
    with lock(directory/'lock'):
        receipt=json.loads((directory/'receipt.json').read_text())
        if receipt['status'] not in ('queued','running'):
            return
    workbench=Workbench(j,receipt['run'],receipt['experiment'],receipt['project'])
    started=time.monotonic()
    timeout=receipt['spec']['timeout_s']
    # A separate lifetime lock prevents duplicate supervisors/publication after retries.
    import fcntl
    lifetime=open(directory/'supervisor.lock','a')
    try: fcntl.flock(lifetime,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: lifetime.close(); return
    receipt.update(status='running',pid=os.getpid(),worker_identity=process_identity(),started_at=time.time())
    atomic(directory/'receipt.json',receipt)
    try:
        # One CPU scientific job on this host. Queue wait counts against wall budget.
        import fcntl
        with open('/tmp/dnhacks-inhibitor-cpu.lock','a') as cpu_lock:
            while True:
                if (directory/'cancel.json').exists(): raise InterruptedError('Cancelled while queued')
                if time.monotonic()-started>timeout: raise TimeoutError('Queue timeout')
                try:
                    fcntl.flock(cpu_lock,fcntl.LOCK_EX|fcntl.LOCK_NB); break
                except BlockingIOError: time.sleep(.1)
            lease_fd=os.environ.get('DNHACKS_INHIBITOR_LEASE_FD')
            proc=subprocess.Popen([sys.executable,'-m','dnhacksbio.inhibitor.worker','--science',trace_dir,job_id],
                                  pass_fds=(int(lease_fd),) if lease_fd else ())
            try:
                while proc.poll() is None:
                    if (directory/'cancel.json').exists(): raise InterruptedError('Cancelled')
                    if time.monotonic()-started>timeout: raise TimeoutError('Declared wall budget exceeded')
                    time.sleep(.1)
                if proc.returncode:
                    failure=directory/'failure.json'
                    message=json.loads(failure.read_text())['error'] if failure.exists() else f'Scientific worker failed (exit {proc.returncode})'
                    raise ValueError(message)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try: proc.wait(timeout=3)
                    except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        if (directory/'cancel.json').exists(): raise InterruptedError('Cancelled before publication')
        raw=(directory/'output'/'bundle.json').read_bytes()
        # Persist complete output files in content-addressed storage; hash manifest is the receipt.
        files={p.name:j.store_bytes(p.read_bytes()) for p in (directory/'output').iterdir() if p.is_file()}
        bundle=json.loads(raw)
        bundle['files']=files
        from .science import encode
        artifact=workbench.attach(encode(bundle),'Docking bundle','inhibitor_bundle','json',
                                 {'category':'derived_geometry','source_ids':[receipt['source_hash']],
                                  'tool':'AutoDock Vina / Meeko / RDKit','tool_version':bundle['protocol']['versions']})
        receipt.update(status='completed',artifact=artifact,files=files)
    except BaseException as exc:
        receipt.update(status='cancelled' if isinstance(exc,InterruptedError) else 'timed_out' if isinstance(exc,TimeoutError) else 'failed',
                       error=f'{type(exc).__name__}: {exc}')
    receipt.update(finished_at=time.time(),elapsed_s=time.monotonic()-started)
    atomic(directory/'receipt.json',receipt)
    workbench.event('inhibitor.job',receipt,receipt['actor'])
    lifetime.close()


def science(trace_dir,job_id):
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    from .science import dock
    j=Journal(Path(trace_dir))
    directory=j.directory/'inhibitor'/'jobs'/job_id
    receipt=json.loads((directory/'receipt.json').read_text())
    resource.setrlimit(resource.RLIMIT_CPU,(receipt['spec']['timeout_s'],receipt['spec']['timeout_s']+1))
    out=directory/'output'
    def progress(stage,message):
        atomic(directory/'progress.json',{'stage':stage,'message':message,'time':time.time()})
    try:
        dock(j.read_blob(receipt['source_hash']),receipt['spec'],out,progress)
    except Exception as exc:
        atomic(directory/'failure.json',{'error':f'{type(exc).__name__}: {str(exc)[:1500]}'})
        raise


if __name__=='__main__':
    if sys.argv[1]=='--science': science(*sys.argv[2:])
    else: main(*sys.argv[1:])
