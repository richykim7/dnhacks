#!/usr/bin/env python3
"""Create an explicit, isolated real 3VQU recovery investigation and optionally serve it."""
import argparse
import json
from pathlib import Path
import time
from urllib.parse import urlencode

from dnhacksbio.explorer.runtime import Journal
from dnhacksbio.inhibitor.science import digest
from dnhacksbio.inhibitor.service import Workbench


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trace-dir',type=Path,required=True)
    p.add_argument('--serve',action='store_true')
    p.add_argument('--port',type=int,default=8787)
    args=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    j=Journal(args.trace_dir.resolve())
    run='inhibitor-demo';experiment='recovery';project='inhibitor-demo'
    j.register(run,'Can this frozen protocol recover the deposited 3VQU ligand?',project=project)
    w=Workbench(j,run,experiment,project)
    source=json.loads((root/'frontend/e2e/inhibitor/source.json').read_text())
    raw=(root/'frontend/e2e/inhibitor/3vqu.cif').read_bytes()
    if digest(raw)!=source['sha256']: raise ValueError('Reference source hash mismatch')
    w.event('experiment.queued',{'title':'3VQU known-ligand recovery','method':'exploratory docking','status':'completed'},'user',event_id='inhibitor-demo-experiment')
    artifact=w.attach(raw,'3VQU.cif','molecular_structure','cif',
        {'category':'experimental_reference','source_ids':['PDB:3VQU','doi:10.1371/journal.pone.0174863'],
         'url':source['url'],'revision':source['revision'],'retrieved_at':source['retrieved_at'],
         'title':source['title'],'limitation':'O22 is not AZ3146. PDAC paper supplies target rationale, not efficacy evidence for this ligand.'})
    spec={'spec_version':1,'chain':'A','ligand_sequence':'909','ligand_name':'O22',
          'assembly':'deposited-chain','protonation':'meeko-standard-templates','repair_policy':'pdbfixer-missing-atoms',
          'water_policy':'exclude','cofactor_policy':'reject','exclude_additives':[f'A:{i}:IOD' for i in range(901,909)],
          'altloc':'A','margin_angstrom':5,'seeds':[17,29,41],'exhaustiveness':4,'pose_count':5,'timeout_s':600,
          'rationale':'Dry receptor benchmark; explicit iodide exclusion and seeded missing-sidechain repair. Waters/ions not claimed biologically dispensable'}
    receipt=w.start(artifact['storage_key'],spec,'user','known-ligand-recovery-v1')
    print('Running bounded real docking:',receipt['job_id'],flush=True)
    while True:
        receipt=json.loads((w.directory/'jobs'/receipt['job_id']/'receipt.json').read_text())
        if receipt['status'] not in ('queued','running'): break
        time.sleep(1)
    if receipt['status']!='completed': raise RuntimeError(f"{receipt['status']}: {receipt.get('error')}")
    bundle=w.bundle(receipt['artifact']['storage_key'])
    # Operator-generated bookmarks are explicitly separate from agent-authored actions.
    own=[s for s in w.scenes(artifact['storage_key']) if s['actor']=='user']
    if not own:
        w.scene(artifact['storage_key'],{'bundle':receipt['artifact']['storage_key'],'pose':bundle['poses'][0]['id'],
                'ligand':bundle['ligand_residue'],'shot':'pocket','clip':True},0,'user','Operator opened real recovery result')
    query=urlencode({'project':project,'experiment':experiment,'artifact':artifact['storage_key'],'sceneTool':'inhibitor'})
    print(json.dumps(bundle['report']['recovery'],indent=2),flush=True)
    print(f'http://127.0.0.1:{args.port}/?{query}#investigations/{run}',flush=True)
    print('Agent replay appears when an agent uses the inhibitor-interface skill to record scene actions.',flush=True)
    if args.serve:
        from dnhacksbio.webui import data,server
        data.PROCESSED=args.trace_dir.resolve()
        server.serve(port=args.port)


if __name__=='__main__': main()
