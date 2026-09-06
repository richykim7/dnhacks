import json
import os
import sys
import threading
import time
from pathlib import Path

from dnhacksbio.explorer.sandbox import run_code, run_many, SandboxPool, resolve_code_paths


def test_host_paths_scope_and_executed_code_are_recorded(tmp_path):
    from dnhacksbio.explorer.runtime import Journal
    data = tmp_path/'data'; data.mkdir(); (data/'input.txt').write_text('real input')
    cache, scratch = tmp_path/'cache', tmp_path/'scratch'
    seen = []; j = Journal(tmp_path/'trace')
    code = "import os,json,sys\nfrom pathlib import Path\nprint(Path('/data/input.txt').read_text())\nPath('/scratch/result.txt').write_text('saved')\nprint(json.dumps({'scope':json.loads(os.environ['DNHACKS_EXPERIMENT_SCOPE']),'python':sys.executable,'cwd':str(Path.cwd())}))"
    r = run_code(code, data_dir=data, cache_dir=cache, scratch_dir=scratch, scope={'experiment_id':'owned'},
                 journal=j, progress=lambda k,p:seen.append((k,p)), job_base=str(tmp_path))
    assert r.ok, r.stderr
    assert 'real input' in r.stdout and 'owned' in r.stdout
    assert (scratch/'result.txt').read_text() == 'saved'
    started = seen[0][1]
    assert started['execution_backend'] == 'host' and started['interpreter'] == sys.executable
    assert str(data/'input.txt') in j.read_blob(started['code']['storage_key']).decode()
    assert not list(tmp_path.glob('explorer-job-*'))


def test_host_cancel_stops_owned_child_processes(tmp_path):
    pidfile = tmp_path/'child.pid'; cancel = threading.Event()
    code = f"import subprocess,sys,time\nfrom pathlib import Path\np=subprocess.Popen([sys.executable,'-c','import time;time.sleep(300)'])\nPath({str(pidfile)!r}).write_text(str(p.pid))\nprint('child started',flush=True)\ntime.sleep(300)"
    timer = threading.Timer(.5, cancel.set); timer.start()
    try:
        r = run_code(code, cancel=cancel, data_dir=None, job_base=str(tmp_path))
    finally:
        timer.cancel()
    assert not r.ok and not r.timed_out
    pid = int(pidfile.read_text())
    for _ in range(20):
        p = Path('/proc')/str(pid)/'stat'
        if not p.exists(): break
        text = p.read_text()
        if text[text.rfind(')')+2:].split()[0] == 'Z': break
        time.sleep(.05)
    else: raise AssertionError('Owned child is still running')


def test_closed_output_does_not_impose_an_execution_timeout(tmp_path):
    t = time.monotonic()
    r = run_code('import os,time\nos.close(1);os.close(2);time.sleep(.2)', data_dir=None, job_base=str(tmp_path))
    assert r.ok and time.monotonic()-t >= .2


def test_parallel_host_scopes_do_not_leak_between_jobs(tmp_path):
    code = "import os,json\nprint(json.loads(os.environ['DNHACKS_EXPERIMENT_SCOPE'])['experiment_id'])"
    results = run_many([code,code], pool=SandboxPool(1), experiment_scopes=[{'experiment_id':'one'},{'experiment_id':'two'}], data_dir=None, job_base=str(tmp_path))
    assert [r.stdout.strip() for r in results] == ['one','two']
    assert all(r.ok for r in results)


def test_path_aliases_use_component_boundaries():
    resolved = resolve_code_paths("a='/data/x';b='/database/x';c=f'/scratch/{1}.txt'", {'/data':'/actual/data','/scratch':'/actual/scratch'})
    assert '/actual/data/x' in resolved and '/database/x' in resolved and '/actual/scratch/' in resolved


def test_host_job_stops_if_its_runner_dies(tmp_path):
    import subprocess
    pidfile=tmp_path/'native.pid'
    code=f"import os,time\nfrom pathlib import Path\nPath({str(pidfile)!r}).write_text(str(os.getpid()))\ntime.sleep(300)"
    supervisor=f"from dnhacksbio.explorer.sandbox import run_code\nrun_code({code!r},data_dir=None,job_base={str(tmp_path)!r})"
    env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
    p=subprocess.Popen([sys.executable,'-c',supervisor],env=env)
    try:
        for _ in range(100):
            if pidfile.exists():break
            time.sleep(.05)
        assert pidfile.exists()
        native_pid=int(pidfile.read_text())
        p.kill();p.wait()
        for _ in range(100):
            stat=Path('/proc')/str(native_pid)/'stat'
            if not stat.exists():break
            text=stat.read_text()
            if text[text.rfind(')')+2:].split()[0]=='Z':break
            time.sleep(.05)
        else:raise AssertionError('Native job survived its runner')
    finally:
        if p.poll() is None:p.kill()
        p.wait()
