"""JSON request CLI for exploratory binder tools; no implicit inference or wet-lab action."""
import argparse
import json
from pathlib import Path

from .bundle import make_bundle, validate_bundle
from .geometry import canonical, define_interface, evaluate_interface
from .jobs import DesignStore, plan_design
from .tools import prepare_target, compare, propose_followup


def dispatch(request):
    action=request['action'];args=request.get('args',{})
    if action in {'binder.open_scene','binder.set_scene_view','binder.capture_scene','binder.inspect_scene_capture','binder.pick'}:
        import asyncio
        from dnhacksbio.explorer.runtime import Journal
        from .scenes import SceneService
        from .render import browser_renderer
        service=SceneService(Journal(request['journal_directory'],create=False),request['scope'])
        args={**args}
        if action in {'binder.capture_scene','binder.pick'}:
            args['renderer']=browser_renderer(request['base_url'],service.manifest['investigation_id'])
        result=getattr(service,action.split('.')[1])(**args)
        return asyncio.run(result) if action=='binder.inspect_scene_capture' else result
    if action=='binder.prepare_target':
        args={**args};raw=Path(args.pop('structure_path')).read_bytes()
        return prepare_target(raw,**args)
    if action=='binder.define_interface':return define_interface(**args)
    if action=='binder.evaluate_interface':return evaluate_interface(**args)
    if action=='binder.import_candidate':
        args={**args};raw=Path(args.pop('structure_path')).read_bytes()
        bundle=make_bundle(raw,**args);validate_bundle(canonical(bundle));return bundle
    if action=='binder.plan_design':return plan_design(**args)
    if action=='binder.compare':return compare(**args)
    if action=='binder.propose_followup':return propose_followup(**args)
    if action in {'binder.start_design','binder.collect_candidates','binder.cancel','binder.recover','binder.attach_candidate'}:
        store=DesignStore(request['store'])
        if action=='binder.attach_candidate':
            args={**args};args['bundle_raw']=Path(args.pop('bundle_path')).read_bytes()
        return getattr(store,action.split('.')[1])(**args)
    raise ValueError('Unknown binder operation; execution is an operator-side adapter action')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:result={'ok':True,'output':dispatch(json.loads(args.request.read_text()))}
    except (ValueError,KeyError,FileNotFoundError) as exc:result={'ok':False,'error':str(exc)}
    raw=canonical(result)
    if args.output:args.output.write_bytes(raw)
    else:print(raw.decode())
    return 0 if result['ok'] else 1

if __name__=='__main__':raise SystemExit(main())
