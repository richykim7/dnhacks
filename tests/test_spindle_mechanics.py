"""Measured report semantics and opt-in native mechanical probes."""
import importlib.util
import json
import os
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('spindle_mechanics', Path(__file__).parents[1] / 'scripts/validate_spindle_mechanics.py')
mechanics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mechanics)


def test_report_measures_length_not_endpoint_and_requires_attachment(tmp_path):
    report = tmp_path / 'report.txt'
    report.write_text(''.join(f'% frame {i}\n1 1 {1+i*.05} 1 {20+i*.05} 0 0\n' for i in range(11)))
    values = mechanics.measure(report, 'growth')
    assert values[0] == 1 and values[-1] == 1.5
    report.write_text(''.join(f'% frame {i}\n1 1 0 0 0 0 0\n' for i in range(11)))
    with pytest.raises(ValueError, match='remain bound'):
        mechanics.measure(report, 'motor')


@pytest.mark.skipif(not os.environ.get('SPINDLE_CYTOSIM_BUILD'), reason='Opt-in pinned native build manifest required')
def test_native_motor_growth_and_timestep_refinement(tmp_path):
    build = json.loads(Path(os.environ['SPINDLE_CYTOSIM_BUILD']).read_bytes())
    result = mechanics.validate_native(Path(os.environ['SPINDLE_CYTOSIM_BIN']), build, tmp_path / 'validation')
    assert result['passed'], result['cases']
    assert len(result['cases']) == 6
    assert all(v <= result['tolerance_um'] for v in result['refinement_spread_um'].values())
    assert result['files']
