"""Run or assess a frozen, bounded native coupled-aster engineering study."""
from __future__ import annotations
import argparse
import copy
import json
import math
import os
import signal
import subprocess
import time
from pathlib import Path
from statistics import mean

from dnhacksbio.spindle.protocol import CYTOSIM_COMMIT, canonical, digest, validate_protocol
from dnhacksbio.spindle.cytosim import configuration, export_run
from dnhacksbio.spindle.analysis import analyze_run
from dnhacksbio.spindle.validation import assess_coupled


def run_study(plan, binary, build, output, wall_seconds=1800, max_bytes=1024**3):
    validate_protocol(plan['protocol'])
    assess_coupled(plan, [])  # Validate the fixed replicate/refinement design before work.
    binary = binary.resolve()
    if build.get('solver_commit') != CYTOSIM_COMMIT or build.get('dimensionality') != 3:
        raise ValueError('Pinned 3D build required')
    for name in ('sim', 'report'):
        if digest((binary / name).read_bytes()) != build.get(name + '_sha256'):
            raise ValueError('Native executable hash mismatch')
    if not 1 <= wall_seconds <= 1800 or not 1024 <= max_bytes <= 1024**3:
        raise ValueError('Invalid study resource budget')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'frozen-plan.json').write_bytes(canonical(plan))
    result = {'schema': 'spindle_coupled_validation.v1', 'plan': plan, 'plan_sha256': digest(plan),
              'build': build, 'runs': [], 'execution_script_sha256': digest(Path(__file__).read_bytes())}
    deadline = time.monotonic() + wall_seconds
    total_bytes = 0
    for dt in plan['timesteps_s']:
        for seed in plan['protocol']['seeds']:
            for condition in plan['protocol']['conditions']:
                folder = output / f'{dt}-{seed}-{condition["name"]}'
                folder.mkdir()
                protocol = copy.deepcopy(plan['protocol'])
                protocol['parameters']['time_step_s']['value'] = dt
                config = configuration(protocol, condition, seed)
                (folder / 'config.cym').write_text(config)
                record = {'dt_s': dt, 'seed': seed, 'condition': condition['name'],
                          'configuration_sha256': digest(config.encode())}
                started = time.monotonic()
                try:
                    if total_bytes >= max_bytes:
                        raise RuntimeError('Study artifact budget exhausted')
                    commands = [([str(binary / 'sim'), f'random_seed={seed}'], 'solver.txt')]
                    commands += [([str(binary / 'report'), kind, 'precision=17', 'verbose=7'], name)
                                 for kind, name in [('aster', 'asters.txt'), ('fiber:points', 'fibers.txt'),
                                 ('fiber', 'owners.txt'), ('single:position', 'motor-anchors.txt'),
                                 ('single:link', 'motor-links.txt')]]
                    for command, name in commands:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError('Study wall budget exhausted')
                        with (folder / name).open('wb') as out, (folder / 'stderr.txt').open('ab') as err:
                            process = subprocess.Popen(command, cwd=folder, stdout=out, stderr=err, start_new_session=True)
                            command_deadline = time.monotonic() + min(30, remaining)
                            try:
                                while process.poll() is None:
                                    if time.monotonic() >= command_deadline:
                                        raise TimeoutError('Native command time budget exhausted')
                                    if total_bytes + sum(p.stat().st_size for p in folder.iterdir() if p.is_file()) > max_bytes:
                                        raise OverflowError('Study artifact budget exhausted')
                                    time.sleep(.05)
                                if process.returncode:
                                    raise RuntimeError(f'Native command exited {process.returncode}')
                            finally:
                                if process.poll() is None:
                                    os.killpg(process.pid, signal.SIGKILL)
                                    process.wait()
                    run = export_run(folder, protocol, condition, seed)
                    (folder / 'trajectory.json').write_bytes(canonical(run))
                    analysis = analyze_run(run, protocol['analysis_plan']['threshold_um'], protocol['analysis_plan']['dwell_s'])
                    final = run['frames'][-1]
                    values = [mean(x['distance_um'] for x in analysis['pairwise_distances'][-1]['pairs']),
                              sum(math.dist(a, b) for f in final['filaments'] for a, b in zip(f['points'], f['points'][1:])),
                              sum(m['filament'] is not None for m in final['cortical_motors']),
                              analysis['bipolar_dwell_s'] / protocol['parameters']['duration_s']['value']]
                    record.update(status='completed', values=values, final_pole_count=analysis['final_pole_count'],
                                  right_censored=analysis['right_censored'], initial_poles=run['frames'][0]['poles'])
                except (OSError, ValueError, RuntimeError, OverflowError, subprocess.SubprocessError) as exc:
                    record.update(status='failed', error=f'{type(exc).__name__}: {exc}')
                record['wall_seconds'] = time.monotonic() - started
                record['files'] = {p.name: digest(p.read_bytes()) for p in folder.iterdir() if p.is_file()}
                total_bytes += sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
                result['runs'].append(record)
                (output / 'report.json').write_bytes(canonical(result))
                print(len(result['runs']), dt, seed, condition['name'], record['status'], flush=True)
                if total_bytes >= max_bytes or time.monotonic() >= deadline:
                    result['resource_exhausted'] = True
                    result['assessment'] = assess_coupled(plan, result['runs'])
                    (output / 'report.json').write_bytes(canonical(result))
                    return result
    result['assessment'] = assess_coupled(plan, result['runs'])
    (output / 'report.json').write_bytes(canonical(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--binary-dir', type=Path)
    parser.add_argument('--build-manifest', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--assess', type=Path, help='Assess an existing local report without rerunning its solver')
    args = parser.parse_args()
    if args.assess:
        result = json.loads(args.assess.read_bytes())
        if result['plan_sha256'] != digest(result['plan']):
            raise ValueError('Frozen plan hash mismatch')
        result['assessment'] = assess_coupled(result['plan'], result['runs'])
        args.assess.with_name('assessment.json').write_bytes(canonical(result['assessment']))
    else:
        if not all((args.plan, args.binary_dir, args.build_manifest, args.output)):
            parser.error('Run requires --plan, --binary-dir, --build-manifest and --output')
        result = run_study(json.loads(args.plan.read_bytes()), args.binary_dir,
                           json.loads(args.build_manifest.read_bytes()), args.output)
    print(json.dumps(result['assessment'], indent=2))
    return 0 if result['assessment']['equivalence_established'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
