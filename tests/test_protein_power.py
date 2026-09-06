from pathlib import Path
import runpy
import pytest

module=runpy.run_path(str(Path(__file__).parents[1]/"scripts/validate_protein_power.py"))


def test_gaussian_information_budget_is_not_auroc():
    power=module["gaussian_oracle_power"]
    assert power(60,0)==pytest.approx(.05)
    assert power(44)<power(60)<.8
    assert power(78)>.8
    assert power(100)>power(78)


def test_binomial_uncertainty_does_not_certify_zero_errors():
    lo,hi=module["interval"](0,10000)
    assert lo==pytest.approx(0)
    assert 0<hi<.001
