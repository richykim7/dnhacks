"""Render the actual owning workbench in a disposable read-only local browser server."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

from .science import encode
from .service import lock


def capture(wb,key,revision,actor,viewport):
    wb.source(key)
    if not isinstance(viewport,list) or len(viewport)!=2 or any(type(n) is not int for n in viewport) or not 320<=viewport[0]<=1920 or not 320<=viewport[1]<=1080:
        raise ValueError('Viewport outside 320x320–1920x1080')
    own=[s for s in wb.scenes(key) if s['actor']==actor]
    if not own or own[-1]['recipe']['revision']!=revision:
        raise ValueError('Stale capture revision')
    recipe=own[-1]['recipe']
    wb.directory.mkdir(exist_ok=True)
    with lock(wb.directory/'capture.lock'):
        previous=[e for e in wb.history() if e['kind']=='scene.capture']
        if len(previous)>=24: raise ValueError('Experiment image budget exhausted (24 captures); numerical tools remain available')
        result=subprocess.run([sys.executable,'-m','dnhacksbio.inhibitor.vision',str(wb.j.directory.parent),
                               wb.run,wb.experiment,wb.project or '',key,str(revision),actor,str(viewport[0]),str(viewport[1])],
                              capture_output=True,timeout=90,check=False)
        if result.returncode:
            raise ValueError('Scene capture failed: '+result.stderr.decode(errors='replace')[-1500:])
        raw=result.stdout
        from PIL import Image
        import io
        with Image.open(io.BytesIO(raw)) as im:
            if im.format!='PNG' or im.size!=tuple(viewport) or len(raw)>8*1024*1024:
                raise ValueError('Invalid rendered capture')
            im.verify()
        own=[s for s in wb.scenes(key) if s['actor']==actor]
        if own[-1]['recipe']!=recipe: raise ValueError('Scene changed during capture; image discarded')
        image_hash=wb.j.store_bytes(raw)
        receipt={'image_hash':image_hash,'source_hash':key,'recipe':recipe,'recipe_hash':__import__('hashlib').sha256(encode(recipe)).hexdigest(),
                 'viewport':viewport,'dpr':1,'frame':0,'media_type':'image/png','byte_length':len(raw),
                 'renderer':'React Three Fiber / Chromium','scene_sequence':own[-1]['sequence']}
        from dnhacksbio.webui.server import FRONTEND
        receipt['frontend_build_hash']=__import__('hashlib').sha256((FRONTEND/'index.html').read_bytes()).hexdigest()
        receipt['browser_version']=next((line.split('=',1)[1] for line in result.stderr.decode(errors='replace').splitlines() if line.startswith('INHIBITOR_BROWSER_VERSION=')),'unreported')
        receipt['quality_tier']='WebGL2 / SwiftShader / DPR 1 / reduced motion'
        wb.event('scene.capture',receipt,actor)
        return receipt


def render(trace_dir,run,experiment,project,key,revision,actor,width,height):
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from urllib.parse import urlencode
    from dnhacksbio.webui import data
    from dnhacksbio.webui.server import Handler, FRONTEND
    if not (FRONTEND/'index.html').exists(): raise ValueError('Build frontend before scene capture')
    data.PROCESSED=Path(trace_dir)
    class ReadOnly(Handler):
        def do_POST(self): self._error(405,'Capture server is read-only')
    server=ThreadingHTTPServer(('127.0.0.1',0),ReadOnly)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
            print('INHIBITOR_BROWSER_VERSION='+browser.version,file=sys.stderr)
            try:
                page=browser.new_page(viewport={'width':int(width),'height':int(height)},device_scale_factor=1,reduced_motion='reduce')
                query=urlencode({'project':project,'experiment':experiment,'artifact':key,'sceneTool':'inhibitor',
                                 'sceneRevision':revision,'sceneActor':actor})
                page.goto(f'http://127.0.0.1:{server.server_port}/?{query}#investigations/{run}')
                page.wait_for_function('(revision)=>window.inhibitorScene?.recipe()?.revision===revision',arg=int(revision),timeout=30000)
                page.evaluate('()=>window.inhibitorScene.ready()')
                page.evaluate('()=>document.fonts.ready')
                image=page.screenshot(animations='disabled')
                if page.evaluate('()=>window.inhibitorScene.recipe().revision')!=int(revision):
                    raise ValueError('Stale browser capture')
                sys.stdout.buffer.write(image)
            finally: browser.close()
    finally:
        server.shutdown();server.server_close()


if __name__=='__main__': render(*sys.argv[1:])
