"""Operator-side BindCraft execution with a host-wide GPU lease and hard wall-time cap.

The checkout, environment and weight manifest are operator-owned deployment inputs.
This module never installs dependencies, downloads weights or orders molecules.
"""
from __future__ import annotations
import fcntl
import json
import os
import signal
import subprocess
import time
from pathlib import Path

from dnhacksbio.explorer.runtime import process_identity
from .geometry import canonical, digest
from .jobs import BINDCRAFT_COMMIT, DesignStore


def check_deployment(checkout: Path, python: Path, environment: Path, weights_manifest: Path,
                     filters: Path, advanced: Path, protocol: dict, *, license_reviewed: bool):
    if not license_reviewed:
        raise ValueError('Deployment eligibility including PyRosetta must be reviewed')
    head=subprocess.run(['git','rev-parse','HEAD'],cwd=checkout,capture_output=True,text=True,check=True).stdout.strip()
    dirty=subprocess.run(['git','status','--porcelain','--untracked-files=no'],cwd=checkout,capture_output=True,text=True,check=True).stdout
    if head!=BINDCRAFT_COMMIT or dirty:raise ValueError('BindCraft checkout differs from pinned clean commit')
    for path,key in ((environment,'environment_sha256'),(weights_manifest,'weights_sha256'),(filters,'filters_sha256'),(advanced,'advanced_sha256')):
        if digest(path.read_bytes())!=protocol[key]:raise ValueError(f'Deployment resource hash mismatch: {key}')
    weights=json.loads(weights_manifest.read_text())
    if not isinstance(weights,list) or not weights:raise ValueError('Weight file inventory required')
    for item in weights:
        path=checkout/item['path']
        if not path.resolve().is_relative_to(checkout.resolve()):raise ValueError('Weight escaped checkout')
        import hashlib
        h=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        if h.hexdigest()!=item['sha256']:raise ValueError('Weight file hash mismatch')
    # Environment identity is checked against actual installed distributions, not only a label file.
    actual=subprocess.run([str(python),'-m','pip','freeze','--all'],capture_output=True,check=True).stdout
    if actual!=environment.read_bytes():raise ValueError('Installed environment differs from pinned freeze')
    return {'commit':head,'weights':len(weights),'environment_sha256':digest(actual)}


def execute(store:DesignStore,receipt:str,scope:dict,*,checkout:Path,python:Path,target_pdb:Path,
            target:dict,epitope:dict,environment:Path,weights_manifest:Path,filters:Path,
            advanced:Path,license_reviewed:bool,lock_path:Path=Path('/tmp/dnhacks-shared-gpu.lock')):
    """Run a queued pilot; return terminal receipt. Outputs are retained for mapped import.

    Candidate collection is deliberately a separate mapping/validation step: engine chain
    renumbering cannot silently masquerade as the original target residue identity.
    """
    with store.connect() as con:row=store._job(con,receipt,scope)
    protocol=json.loads(row['protocol'])
    if digest(target)!=protocol['target_sha256'] or digest(epitope)!=protocol['epitope_sha256']:
        raise ValueError('Stale target or epitope')
    if digest(target_pdb.read_bytes())!=target['source_sha256']:
        raise ValueError('Target coordinate hash mismatch')
    check_deployment(checkout,python,environment,weights_manifest,filters,advanced,protocol,license_reviewed=license_reviewed)
    with lock_path.open('a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        owner=process_identity()
        if owner is None:raise RuntimeError('Cannot establish worker identity')
        protocol=store.claim(receipt,scope,owner)
        work=store.root/receipt;work.mkdir(exist_ok=False)
        settings={'design_path':str(work/'outputs'),'binder_name':'candidate','starting_pdb':str(target_pdb.resolve()),
                  'chains':','.join(sorted({r['chain'] for r in target['residues']})),
                  'target_hotspot_residues':protocol['hotspots'],'lengths':protocol['lengths'],
                  'number_of_final_designs':protocol['candidate_cap']}
        adv=json.loads(advanced.read_text());adv['max_trajectories']=protocol['trajectory_cap']
        (work/'settings.json').write_bytes(canonical(settings));(work/'advanced.json').write_bytes(canonical(adv))
        process=None
        try:
            with (work/'worker.log').open('wb') as log:
                process=subprocess.Popen([str(python),'-u',str(checkout/'bindcraft.py'),'--settings',str(work/'settings.json'),
                                          '--filters',str(filters.resolve()),'--advanced',str(work/'advanced.json')],
                                         cwd=checkout,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                                         pass_fds=(lease.fileno(),))
                start=time.monotonic();outcome='failed';reason='Generator exited unsuccessfully'
                while process.poll() is None:
                    current=store.collect_candidates(receipt,scope)['state']
                    if current=='canceled':outcome='canceled';reason='Canceled by owner';break
                    if time.monotonic()-start>=protocol['gpu_seconds']:
                        outcome='resource_exhausted';reason='GPU wall-time cap';break
                    # Upstream max_trajectories counts only relaxed successes; also bound all started trajectories.
                    log.flush()
                    starts=(work/'worker.log').read_text(errors='replace').count('Starting trajectory:')
                    if starts>protocol['trajectory_cap']:
                        outcome='resource_exhausted';reason='Trajectory start cap';break
                    size=sum(p.stat().st_size for p in work.rglob('*') if p.is_file())
                    if size>protocol['artifact_bytes']:
                        outcome='resource_exhausted';reason='Output byte budget';break
                    time.sleep(.25)
                else:
                    if process.returncode==0:
                        outcome='completed';reason='Generator finished; raw outputs await explicit residue mapping and validated import'
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGTERM)
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
            if outcome!='canceled':store.finish(receipt,scope,owner,outcome,reason)
        except BaseException:
            if process is not None and process.poll() is None:
                os.killpg(process.pid,signal.SIGKILL);process.wait()
            store.finish(receipt,scope,owner,'interrupted','Worker interrupted; explicit new receipt required to rerun')
            raise
    return store.collect_candidates(receipt,scope)
