"""Synthetic design checks, never biological confirmation data."""
from copy import deepcopy
from itertools import permutations
import math

import numpy as np
import pytest

from dnhacksbio.drug_response import VERSION, prepare, score, validate_protocol


def protocol(**changes):
    return {"version": VERSION, "drug": "synthetic-drug", "exposure_hours": 72,
        "biomarker": "synthetic-marker", "dose_min_molar": 1e-9, "dose_max_molar": 1e-6,
        "input_scale": "fraction", "normalization": "vehicle_normalized", "clipping": "reject",
        "aggregation": "mean_replicates_then_plates_then_donor", "missing_coverage": "reject",
        "direction": "two-sided", "permutations": "exact", "seed": 123, "min_units": 3,
        "assumptions": "Synthetic independent donors; exchangeable within declared strata; frozen marker",
        **changes}


def cohort(x=(1, 2, 3), response=(0.1, 0.5, 0.9), strata=None):
    return {"source": "Synthetic test fixture only", "units": {
        f"u{i}": {"donor_id": f"d{i:03}", "stratum": (strata or ["a"] * len(x))[i]}
        for i in range(len(x))}, "rows": [
            {"unit_id": f"u{i}", "plate_id": "p", "replicate_id": "r",
             "dose_molar": d, "viability": 1 - a, "biomarker": float(b)}
            for i, (b, a) in enumerate(zip(x, response)) for d in (1e-9, 1e-6)]}


def test_orientation_scale_and_log_dose_integral():
    c = cohort(response=(0, 0.5, 1))
    assert prepare(c, protocol())["inhibition_area"] == pytest.approx([0, 0.5, 1])
    for row in c["rows"]:
        row["viability"] *= 100
    assert prepare(c, protocol(input_scale="percent"))["inhibition_area"] == pytest.approx([0, 0.5, 1])
    # Unequal log-dose spacing: two decades at mean viability .75, one decade at .25.
    c = cohort()
    c["rows"][:2] = [{**c["rows"][0], "dose_molar": d, "viability": v}
                      for d, v in ((1e-9, 1), (1e-7, .5), (1e-6, 0))]
    assert prepare(c, protocol())["inhibition_area"][0] == pytest.approx(1 - 1.75 / 3)


def test_exact_tiny_and_ties():
    r = score(cohort(), protocol())
    assert r["effect"] == pytest.approx(1)
    assert r["p"] == pytest.approx(2 / 6)
    assert r["e"] == pytest.approx(math.sqrt(3) - 1)
    r = score(cohort(x=(1, 1, 3), response=(.1, .1, .9)), protocol())
    assert r["p"] == pytest.approx(1 / 3)


def test_strata_preserve_confounded_association():
    # Biomarker is a pure stratum indicator; all allowed permutations give same correlation.
    c = cohort(x=(0, 0, 0, 1, 1, 1), response=(.1, .2, .3, .7, .8, .9),
               strata=["a"] * 3 + ["b"] * 3)
    result = score(c, protocol())
    assert result["p"] == 1 and result["e"] == 0
    assert result["permutations"] == 36


def test_exact_null_calibration_over_all_outcomes():
    ps, es = [], []
    for y in permutations((.1, .3, .6, .9)):
        r = score(cohort(x=(1, 2, 3, 4), response=y), protocol())
        ps.append(r["p"])
        es.append(r["e"])
    for alpha in sorted(set(ps)):
        assert sum(p <= alpha for p in ps) / len(ps) <= alpha + 1e-12
    assert np.mean(es) <= 1


def test_monte_carlo_reproducibility_and_power():
    c = cohort(x=range(12), response=np.linspace(.05, .95, 12))
    p = protocol(permutations=9999)
    result = score(c, p)
    assert result == score(c, p)
    assert result["p"] == .0001 and result["e"] == 99
    assert result["n_units"] == 12


def test_donor_aliases_collapse_with_equal_plate_weight():
    c = cohort()
    c["units"]["alias"] = deepcopy(c["units"]["u0"])
    c["rows"] += [{**r, "unit_id": "alias", "plate_id": "second", "viability": .1}
                  for r in c["rows"][:2]]
    # Many technical curves in first plate cannot overweight the second plate.
    c["rows"] += [{**r, "replicate_id": "extra"} for r in c["rows"][:2]]
    result = prepare(c, protocol())
    assert len(result["unit_ids"]) == 3
    assert result["inhibition_area"][0] == pytest.approx(.5)
    c["rows"][-1]["biomarker"] = 100
    with pytest.raises(ValueError, match="Inconsistent donor"):
        prepare(c, protocol())


@pytest.mark.parametrize("mutation", [
    lambda c: c["rows"].pop(0),
    lambda c: c["rows"].append(dict(c["rows"][0])),
    lambda c: c["rows"][0].update(viability=1.01),
    lambda c: c["rows"][0].update(viability=float("nan")),
    lambda c: c["rows"][0].update(biomarker=True),
    lambda c: c["rows"][0].update(dose_molar=0),
    lambda c: c["rows"][0].update(unit_id="unregistered"),
    lambda c: c["units"]["u1"].update(donor_id="d000", stratum="other"),
    lambda c: c["units"].update(unobserved={"donor_id": "x", "stratum": "a"}),
])
def test_invalid_observations_rejected(mutation):
    c = cohort()
    mutation(c)
    with pytest.raises(ValueError):
        prepare(c, protocol())


@pytest.mark.parametrize("changes", [
    {"direction": "positive"}, {"clipping": "clip"}, {"permutations": True},
    {"min_units": True}, {"input_scale": "log"}, {"seed": -1}, {"dose_min_molar": 0},
    {"missing_coverage": "extrapolate"}, {"p": .01},
])
def test_protocol_cannot_sneak_analysis_changes(changes):
    with pytest.raises(ValueError):
        validate_protocol(protocol(**changes))


@pytest.mark.parametrize("c", [cohort(x=(1, 1, 1)), cohort(response=(.1, .1, .1)),
                                cohort(strata=["a", "b", "c"])])
def test_degenerate_test_fails(c):
    with pytest.raises(ValueError):
        score(c, protocol())


def test_exact_budget_and_small_cohort_fail():
    with pytest.raises(ValueError, match="budget"):
        score(cohort(range(10), np.linspace(.1, .9, 10)), protocol())
    with pytest.raises(ValueError, match="Insufficient"):
        score(cohort(), protocol(min_units=8))


def test_adaptive_marker_selection_does_not_create_a_valid_fixed_test():
    # Searching all candidate rank orders guarantees a nominally small fixed-test p under null.
    # The registry must freeze marker choice before response access; calibration cannot repair it.
    x = tuple(range(5))
    candidates = list(permutations(x))
    response = (.1, .2, .4, .7, .9)
    chosen = min(score(cohort(marker, response), protocol())["p"] for marker in candidates)
    assert chosen == pytest.approx(2 / math.factorial(5))
    assert chosen < .05


def test_null_and_signal_across_unit_counts_and_noise():
    rng = np.random.default_rng(523)
    for n in (8, 16, 32):
        x = rng.normal(size=n)
        null_ps, signal_ps = [], []
        for _ in range(12):
            noise = rng.normal(size=n)
            # Smooth bounded responses preserve ranks, with a strong fixed marker effect.
            null_y = 1 / (1 + np.exp(-noise))
            signal_y = 1 / (1 + np.exp(-(3 * x + noise)))
            p = protocol(permutations=9999)
            null_ps.append(score(cohort(x, null_y), p)["p"])
            signal_ps.append(score(cohort(x, signal_y), p)["p"])
        assert np.median(null_ps) > .1
        assert np.median(signal_ps) < .05
