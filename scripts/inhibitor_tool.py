#!/usr/bin/env python3
"""Scoped inhibitor CLI. JSON arguments are data; never arbitrary commands."""
import argparse
import json
from pathlib import Path

from dnhacksbio.explorer.runtime import Journal
from dnhacksbio.inhibitor.service import Workbench


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trace-dir',type=Path,default=Path('data/processed'))
    p.add_argument('--run',required=True)
    p.add_argument('--experiment',required=True)
    p.add_argument('--project')
    p.add_argument('--actor',choices=['agent','user'],default='user')
    p.add_argument('--request',type=Path,required=True,help='JSON operation, see inhibitor-interface skill')
    p.add_argument('--create-investigation',action='store_true',help='Explicitly create an isolated investigation for a new workflow')
    args=p.parse_args()
    j=Journal(args.trace_dir)
    if args.create_investigation:
        j.register(args.run,'Inhibitor preparation and known-ligand recovery',project=args.project)
        j.append(args.run,'inhibitor','attempt.started',{'original_question':'Inhibitor preparation and known-ligand recovery','lifecycle':'completed'})
    wb=Workbench(j,args.run,args.experiment,args.project)
    request=json.loads(args.request.read_text())
    if request.get('operation')=='inspect_scene_capture':
        import asyncio
        from dnhacksbio.inhibitor.review import inspect
        result,_=asyncio.run(inspect(wb,request['capture_id'],request.get('question','Describe geometry and propose a numerical countercheck.')))
    else:
        result=wb.dispatch(request,args.actor)
    print(json.dumps(result,allow_nan=False))


if __name__=='__main__': main()
