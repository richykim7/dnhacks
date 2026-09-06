#!/usr/bin/env python3
"""JSON spindle experiment operations; operator execution requires pinned binaries."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from dnhacksbio.spindle.protocol import canonical, prepare_spindle_experiment
from dnhacksbio.spindle.jobs import SpindleStore
from dnhacksbio.spindle.bundle import validate
from dnhacksbio.spindle.analysis import analyze_ensemble


def dispatch(request):
    action=request['action'];args=request.get('args',{})
    if action=='prepare_spindle_experiment':return prepare_spindle_experiment(**args)
    if action=='analyze_spindle_ensemble':
        store=SpindleStore(request['store']);scope=args['scope'];receipt=args['receipt']
        status=store.status(receipt,scope)
        if status['state']!='completed':raise ValueError('Completed ensemble required')
        manifests=[a for a in status['artifacts'] if a['name']=='archive.json']
        if len(manifests)!=1:raise ValueError('Archive manifest missing or ambiguous')
        manifest=json.loads(store.read_blob(receipt,scope,manifests[0]['hash']))
        plan=manifest['protocol']['analysis_plan']
        if args.get('analysis_plan_ref')!=__import__('hashlib').sha256(canonical(plan)).hexdigest():
            raise ValueError('Analysis must use the frozen protocol plan hash')
        bundle=validate(store.read_blob(receipt,scope,manifest['files']['trajectory.json']))
        return analyze_ensemble(bundle,plan)
    if action in {'run_spindle_experiment','status','cancel'}:
        return getattr(SpindleStore(request['store']),action)(**args)
    if action=='export_artifact':
        store=SpindleStore(request['store']);scope=args['scope'];receipt=args['receipt'];status=store.status(receipt,scope)
        if status['state']!='completed':raise ValueError('Only complete ensembles may be collected')
        entry=next(a for a in status['artifacts'] if a['name']=='archive.json')
        archive=json.loads(store.read_blob(receipt,scope,entry['hash']))
        raw=store.read_blob(receipt,scope,archive['files']['trajectory.json']);validate(raw)
        output=Path(args['output']);output.mkdir(parents=True,exist_ok=True)
        # Exclusive output files avoid overwriting an unrelated experiment manifest.
        with (output/'spindle.json').open('xb') as f:f.write(raw)
        manifest={'schema_version':1,'artifacts':[{'kind':'filament_trajectory','format':'json','path':'spindle.json',
            'provenance':{'category':'derived_geometry','source_ids':archive['protocol']['source_ids'],
                          'tool':'Cytosim','tool_version':archive['build']['solver_commit'],
                          'archive_sha256':entry['hash'],'spec_ref':archive['spec_ref']}}]}
        with (output/'manifest.json').open('xb') as f:f.write(canonical(manifest))
        return {'manifest':str(output/'manifest.json'),'archive_sha256':entry['hash']}
    raise ValueError('Unknown spindle operation')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('request',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--worker',action='store_true',help='Operator-only execution of a queued job')
    parser.add_argument('--sim',type=Path);parser.add_argument('--report',type=Path);parser.add_argument('--build-manifest',type=Path)
    args=parser.parse_args();request=json.loads(args.request.read_text())
    try:
        if args.worker:
            if not all((args.sim,args.report,args.build_manifest)):raise ValueError('Pinned solver, reporter and build manifest required')
            result=SpindleStore(request['store']).execute(**request['args'],sim=args.sim,report=args.report,
                     build_manifest=json.loads(args.build_manifest.read_text()))
        else:result=dispatch(request)
        response={'ok':True,'output':result}
    except (ValueError,KeyError,FileNotFoundError,StopIteration) as exc:response={'ok':False,'error':str(exc)}
    if args.output:args.output.write_bytes(canonical(response))
    else:print(canonical(response).decode())
    return 0 if response['ok'] else 1

if __name__=='__main__':raise SystemExit(main())
