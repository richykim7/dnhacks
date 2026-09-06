"""Measured native CPU probes; no biological calibration or coupled-model certification."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess

from dnhacksbio.spindle.protocol import CYTOSIM_COMMIT, canonical, digest
from dnhacksbio.spindle.cytosim import read_report


def configuration(kind: str, dt: float) -> str:
    steps = round(1 / dt)
    header = f'''set simul system {{ time_step = {dt}; viscosity = 1; kT = 0; tolerance = 0.000001; }}
set space cell {{ shape = sphere; }}
new cell {{ radius = 20; }}
'''
    if kind == 'motor':
        return header + f'''set fiber track {{ rigidity = 20; segmentation = 0.2; }}
new track {{ length = 10; position = 0 0 0; direction = 1 0 0; }}
set hand motor {{ activity = move; binding_rate = 100; binding_range = 0.1; unloaded_speed = -1; stall_force = 5; unbinding_rate = 0; unbinding_force = 5; }}
set single walker {{ hand = motor; stiffness = 100; diffusion = 0; }}
new walker {{ position = 0 0 0; }}
run {round(.1 / dt)} system {{ solve = 0; }}
set system time {{ 0 }}
change motor {{ binding_rate = 0; }}
run {steps} system {{ solve = 0; nb_frames = 10; }}
'''
    if kind != 'growth':
        raise ValueError('Unknown isolated mechanics case')
    return header + f'''set fiber track {{ rigidity = 20; segmentation = 0.2; activity = classic; growing_speed = 0.5; growing_force = 1.67; shrinking_speed = -0.85; catastrophe_rate = 0; rescue_rate = 0; min_length = 0.1; }}
new track {{ length = 1; plus_end = grow; position = 0 0 0; direction = 1 0 0; }}
run {steps} system {{ nb_frames = 10; }}
'''


def measure(path: Path, kind: str) -> list[float]:
    frames = read_report(path)
    if sorted(frames) != list(range(11)):
        raise ValueError('Expected eleven complete sampled frames')
    result = []
    for rows in frames.values():
        if kind == 'motor':
            if len(rows) != 1 or len(rows[0]) != 7 or int(rows[0][5]) != 1:
                raise ValueError('Motor must remain bound to the sole filament')
            result.append(float(rows[0][6]))
        else:
            # fiber:end starts with class, identity, length, stateP, then plus endpoint.
            if len(rows) != 1 or len(rows[0]) < 5:
                raise ValueError('Expected one intact dynamic filament')
            result.append(float(rows[0][2]))
    return result


def validate_native(binary_dir: Path, build: dict, output: Path) -> dict:
    binary_dir = binary_dir.resolve()
    if build.get('solver_commit') != CYTOSIM_COMMIT or build.get('dimensionality') != 3:
        raise ValueError('Pinned 3D build required')
    for name in ('sim', 'report'):
        if digest((binary_dir / name).read_bytes()) != build.get(name + '_sha256'):
            raise ValueError('Native executable hash mismatch')
    output.mkdir(parents=True, exist_ok=False)
    result = {'schema': 'spindle_mechanics_validation.v1', 'build': build,
              'source': ['upstream cym/motor_race.cym', 'upstream cym/fiber_classic.cym'],
              'assumptions': 'Athermal isolated probes; solve=0 freezes motor track; growth is unopposed. Values are engineering test inputs.',
              'tolerance_um': 1e-5, 'cases': [],
              'limits': 'Does not validate loaded force-velocity, binding statistics, coupled aster convergence, HSET, PDAC or biological calibration.'}
    for kind, speed in [('motor', -1.), ('growth', .5)]:
        deltas = []
        for dt in (.002, .001, .0005):
            folder = output / f'{kind}-{dt}'; folder.mkdir()
            (folder / 'config.cym').write_text(configuration(kind, dt))
            commands = [[str(binary_dir / 'sim'), 'random_seed=41'],
                        [str(binary_dir / 'report'), 'single:position' if kind == 'motor' else 'fiber:end', 'precision=17', 'verbose=7']]
            for command, name in zip(commands, ['solver', 'measurement']):
                with (folder / f'{name}.txt').open('wb') as out, (folder / f'{name}.stderr').open('wb') as err:
                    subprocess.run(command, cwd=folder, stdout=out, stderr=err, timeout=20, check=True)
            values = measure(folder / 'measurement.txt', kind)
            change = [v - values[0] for v in values]
            error = max(abs(v - speed * i / 10) for i, v in enumerate(change))
            deltas.append(change[-1])
            result['cases'].append({'kind': kind, 'dt_s': dt, 'values_um': values,
                                    'max_analytic_error_um': error, 'passed': error <= result['tolerance_um']})
        result.setdefault('refinement_spread_um', {})[kind] = max(deltas) - min(deltas)
    result['passed'] = all(c['passed'] for c in result['cases'])
    result['files'] = {str(p.relative_to(output)): digest(p.read_bytes()) for p in sorted(output.rglob('*')) if p.is_file()}
    (output / 'validation.json').write_bytes(canonical(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary-dir', type=Path, required=True)
    parser.add_argument('--build-manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = validate_native(args.binary_dir, json.loads(args.build_manifest.read_bytes()), args.output)
    print(json.dumps({k: report[k] for k in ('passed', 'cases', 'refinement_spread_um')}, indent=2))
    return 0 if report['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
