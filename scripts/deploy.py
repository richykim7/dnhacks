"""Manual Linux/systemd deployment. No timer, no forced deploy, no data migrations."""
import argparse
import json
import os
from pathlib import Path
import socket
import re
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dnhacksbio.webui.deployment import Busy, lease


def run(*args, cwd=None, env=None):
    return subprocess.run(args, cwd=cwd, env=env, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.strip()


def activity(data, proc=Path('/proc')):
    """Fail closed on unreadable records and known standalone research processes.

    This scan supplements leases; it cannot interlock arbitrary shell launches.
    Operators must keep unmanaged CLI launchers quiet during maintenance.
    """
    reasons = []
    for p in (data / 'projects').glob('*/jobs/*.json'):
        job = json.loads(p.read_text())
        if job.get('status') not in {'done', 'failed', 'cancelled'}:
            reasons.append('nonterminal job record')
    journal = data / 'processed/runtime/journal.sqlite3'
    if journal.exists():
        con = sqlite3.connect(journal.as_uri() + '?mode=ro', uri=True, timeout=2)
        try:
            states = {row[0]: None for row in con.execute('SELECT run_id FROM manifests')}
            for row in con.execute('SELECT body FROM events ORDER BY investigation_id, sequence'):
                event = json.loads(row[0])
                if event['kind'] == 'attempt.started':
                    states[event['run_id']] = 'running'
                elif event['kind'] == 'lifecycle':
                    states[event['run_id']] = event['payload'].get('lifecycle')
            from dnhacksbio.explorer.runtime import TERMINAL
            if any(state not in TERMINAL for state in states.values()):
                reasons.append('nonterminal or uncertain runtime journal')
        finally:
            con.close()
    for p in proc.iterdir():
        if not p.name.isdigit() or int(p.name) == os.getpid():
            continue
        try:
            args = (p / 'cmdline').read_bytes().split(b'\0')
        except FileNotFoundError:
            continue
        markers = (b'run_explorer.py', b'ingest_frozen_corpus.py', b'dnhacksbio.litmap.corpus_build')
        if any(a.rsplit(b'/', 1)[-1] in markers for a in args):
            reasons.append('standalone investigation or ingestion process')
    if reasons:
        raise Busy('; '.join(sorted(set(reasons))))


def health(port, sha):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/deployment/health', timeout=2) as r:
            d = json.load(r)
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=2) as r:
            html = r.read()
        return d == {'status': 'ok', 'release': sha, 'guarded': True} and b'/assets/' in html
    except (OSError, ValueError):
        return False


def wait_health(port, sha):
    for _ in range(20):
        if health(port, sha):
            return
        time.sleep(0.5)
    raise RuntimeError('Release health check failed')


def link(target, destination):
    temp = destination.with_name(destination.name + '.next')
    if temp.is_symlink():
        temp.unlink()
    temp.symlink_to(target, target_is_directory=True)
    temp.replace(destination)


def activate(release, current, restart, verify):
    previous = current.resolve() if current.is_symlink() else None
    link(release, current)
    try:
        restart()
        verify(release.name)
    except BaseException:
        if previous:
            link(previous, current)
            restart()
            verify(previous.name)
        else:
            current.unlink()
        raise


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--home', type=Path, required=True, help='Dedicated persistent deployment directory')
    ap.add_argument('--data', type=Path, required=True, help='Existing persistent research data directory')
    ap.add_argument('--bootstrap', action='store_true', help='First install; port must be free')
    ap.add_argument('--port', type=int, default=8765)
    args = ap.parse_args()
    if Path('/proc/1/comm').read_text().strip() != 'systemd':
        raise RuntimeError('Run on the actual systemd VM, not a container/PID-isolated coding sandbox')
    home, data = args.home.resolve(), args.data.resolve()
    if not re.fullmatch(r'[A-Za-z0-9_./-]+', str(home)):
        raise ValueError('Deployment home must use simple path characters')
    source = Path(__file__).resolve().parents[1]
    if not data.is_dir() or data == home or home in data.parents or data in home.parents:
        raise ValueError('Use existing data separate from deployment home')
    home.mkdir(parents=True, exist_ok=True)
    with lease(exclusive=True, path=home / 'command.lock'):
        settings = {'data': str(data), 'port': args.port}
        config = home / 'installation.json'
        if config.exists() and json.loads(config.read_text()) != settings:
            raise ValueError('Installation data/port differs; migration requires separate review')
        activity(data)
        unit = 'dnhacks-web.service'
        def ctl(*a):
            return run('systemctl', '--user', *a)
        if args.bootstrap:
            if (home / 'current').exists():
                raise RuntimeError('Already initialized; omit --bootstrap')
            with socket.socket() as s:
                s.bind(('127.0.0.1', args.port))  # never kill an unmanaged server
        else:
            old = (home / 'current').resolve(strict=True)
            if not health(args.port, old.name):
                raise RuntimeError('Live service is unguarded or unhealthy; refusing deployment')
        repo = home / 'repository.git'
        if not repo.exists():
            run('git', 'clone', '--bare', run('git', 'remote', 'get-url', 'origin', cwd=source), str(repo))
        run('git', '--git-dir', str(repo), 'fetch', 'origin', 'refs/heads/main:refs/heads/main')
        sha = run('git', '--git-dir', str(repo), 'rev-parse', 'refs/heads/main')
        if not args.bootstrap and old.name == sha:
            print('Already serving', sha)
            return
        release = home / 'releases' / sha
        if release.exists():
            raise RuntimeError('Release directory already exists; retain for audit, review before retry')
        release.parent.mkdir(exist_ok=True)
        run('git', 'clone', '--no-hardlinks', str(repo), str(release))
        run('git', 'checkout', '--detach', sha, cwd=release)
        # Test against an isolated, initially empty data directory, never live data.
        env = {k:v for k,v in os.environ.items() if not k.startswith('DNHACKS_') and k != 'PYTHONPATH'}
        env['API_PROXY_TARGET'] = 'http://127.0.0.1:8766'
        env['PLAYWRIGHT_BASE_URL'] = 'http://127.0.0.1:5174'
        run('uv', 'sync', '--frozen', '--extra', 'dev', '--extra', 'llm', cwd=release, env=env)
        run('npm', '--prefix', 'frontend', 'ci', cwd=release, env=env)
        for task in ('build', 'test'):
            run('npm', '--prefix', 'frontend', 'run', task, cwd=release, env=env)
        run('uv', 'run', '--frozen', 'pytest', 'tests', cwd=release, env=env)
        # Browser tests require their own empty-data API server.
        for port in (8766, 5174):
            with socket.socket() as s:
                s.bind(('127.0.0.1', port))
        server = subprocess.Popen([str(release / '.venv/bin/python'), 'scripts/serve_ui.py', '--port', '8766'],
                                  cwd=release, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            run('npm', '--prefix', 'frontend', 'run', 'e2e', cwd=release, env=env)
        finally:
            server.terminate()
            server.wait(timeout=10)
        # Keep test data for audit. Live data is only attached AFTER all gates.
        if (release / 'data').exists():
            (release / 'data').rename(release / 'validation-data')
        (release / 'data').symlink_to(data, target_is_directory=True)
        launcher = home / 'launch.py'
        launcher.write_text('import os,pathlib\n'
            f'r=pathlib.Path({str(home / "current")!r}).resolve()\n'
            f'os.environ["DNHACKS_DEPLOY_LOCK"]={str(home / "research.lock")!r}\n'
            'os.environ["DNHACKS_RELEASE"]=r.name\n'
            'os.environ.pop("PYTHONPATH",None)\nos.chdir(r)\n'
            f'os.execv(str(r/".venv/bin/python"),[str(r/".venv/bin/python"),"scripts/serve_ui.py","--port",{str(args.port)!r}])\n')
        with lease(exclusive=True, path=home / 'research.lock'):
            activity(data)  # new managed launches now fail 503; prior launches hold leases
            if args.bootstrap:
                unit_path = Path.home() / '.config/systemd/user' / unit
                if unit_path.exists():
                    raise RuntimeError('Existing service unit needs review')
                unit_path.parent.mkdir(parents=True, exist_ok=True)
                unit_path.write_text('[Unit]\nDescription=DNHacks research web app\n[Service]\n'
                    f'ExecStart=/usr/bin/python3 "{launcher}"\nRestart=on-failure\nRestartSec=3\n'
                    'KillMode=process\nUMask=0077\n'
                    f'Environment="PATH={Path.home()}/.local/bin:/usr/local/bin:/usr/bin:/bin"\n'
                    '[Install]\nWantedBy=default.target\n')
                ctl('daemon-reload')
            try:
                activate(release, home / 'current', lambda: ctl('restart', unit),
                         lambda s: wait_health(args.port, s))
            except BaseException:
                if args.bootstrap:
                    ctl('stop', unit)
                raise
            config.write_text(json.dumps(settings) + '\n')
            ctl('enable', unit)
        print('Deployed', sha, 'on localhost port', args.port)


if __name__ == '__main__':
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Deployment interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    try:
        main()
    except subprocess.CalledProcessError as exc:
        # Build tools may echo environment/config; never dump captured logs blindly.
        print('Validation/service command failed with exit code', exc.returncode, file=sys.stderr)
        sys.exit(1)
    except (Busy, OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print('Deployment refused:', str(exc), file=sys.stderr)
        sys.exit(1)
