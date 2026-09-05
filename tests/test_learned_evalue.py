"""Contract, leakage, exact-null, artifact and replay tests for diagnostics."""
import itertools
import json
import math
from dataclasses import replace

import numpy as np
import pytest

torch = pytest.importorskip("torch", reason="install the evalue extra for learned-bettor tests")

from dnhacksbio import learned_evalue as le
from dnhacksbio.evalues import e_bh, e_to_p, from_log, mean_merge, p_to_e, product_merge
from dnhacksbio.expr_encoder import FrozenEncoder, fit_autoencoder, fit_pca


CONTRACT = le.SamplingContract("synthetic", "test fixture", "independent Gaussian rows")
CONFIG = le.LearnedEConfig(batch_pairs=2, hidden=(4,), max_epochs=4, patience=2, lr=0.01)


def run(a, b, **kwargs):
    return le.learned_two_sample_e(a, b, genes=[f"g{i}" for i in range(a.shape[1])],
                                  sampling=kwargs.pop("sampling", CONTRACT),
                                  config=kwargs.pop("config", CONFIG), **kwargs)


def data(n=16):
    rng = np.random.default_rng(91)
    return rng.normal(size=(n, 3)), rng.normal(size=(n, 3))


def test_replay_rng_and_final_not_max():
    a, b = data()
    state = torch.random.get_rng_state().clone()
    first, second = run(a, b), run(a, b)
    assert first.to_dict() == second.to_dict()
    assert torch.equal(state, torch.random.get_rng_state())
    assert first.e_value == pytest.approx(math.exp(first.log_wealth_path[-1]))
    assert first.n_scored == 6 and first.metadata["scored_pairs"] == 12
    json.dumps(first.to_dict(), allow_nan=False)


def test_future_batch_cannot_change_earlier_scores():
    a, b = data()
    original = run(a, b)
    # Modify only the last two pairs in the predeclared permutation.
    order = np.random.default_rng(CONFIG.seed).permutation(len(a))
    changed = a.copy()
    changed[order[-2:]] += 100
    later = run(changed, b)
    assert later.per_batch[:-1] == original.per_batch[:-1]
    for update in original.metadata["training_updates"]:
        assert max(update["training_batches"]) < update["validation_batch"] < update["before_scoring_batch"]


def test_exact_null_swap_average_of_product_is_one():
    a, b = data(3)
    model = torch.nn.Linear(3, 1, dtype=torch.float64)
    with torch.no_grad():
        model.weight.copy_(torch.tensor([[0.3, -0.2, 0.1]], dtype=torch.float64))
        model.bias.zero_()
    wealth = []
    for swaps in itertools.product([False, True], repeat=3):
        mask = np.array(swaps)[:, None]
        x = torch.tensor(np.where(mask, b, a))
        y = torch.tensor(np.where(mask, a, b))
        with torch.no_grad():
            logs = le._log_payoffs(model, x, y, 4)
            opposite = le._log_payoffs(model, y, x, 4)
        assert torch.allclose(torch.exp(logs) + torch.exp(opposite), torch.full((3,), 2.0, dtype=torch.float64))
        wealth.append(float(torch.exp(logs.sum())))
    assert np.mean(wealth) == pytest.approx(1, abs=1e-12)


def test_scored_rows_have_never_entered_training_or_validation(monkeypatch):
    a, b = data()
    original_fit, original_payoffs = le._fit, le._log_payoffs
    seen, scored = set(), []
    fitting = False

    def fit(model, train_a, train_b, val_a, val_b, config):
        nonlocal fitting
        for x in (train_a, train_b, val_a, val_b):
            seen.update(map(tuple, x.tolist()))
        fitting = True
        try:
            return original_fit(model, train_a, train_b, val_a, val_b, config)
        finally:
            fitting = False

    def payoff(model, x, y, clip):
        if not fitting:
            rows = set(map(tuple, x.tolist())) | set(map(tuple, y.tolist()))
            assert rows.isdisjoint(seen), "scored data already influenced fitting or early stopping"
            scored.append(rows)
        return original_payoffs(model, x, y, clip)

    monkeypatch.setattr(le, "_fit", fit)
    monkeypatch.setattr(le, "_log_payoffs", payoff)
    result = run(a, b)
    assert len(scored) == result.n_scored


def test_adaptive_wealth_is_fair_over_all_pair_orientations(monkeypatch):
    # Condition on six unordered pairs and fix their pairing/order in advance.
    # Under an iid common null, their independent orientations are fair coins.
    # Enumerating all 64 orientations checks the whole adaptive learner, not
    # just a single frozen model. It is a finite conditional audit, not a proof
    # for every distribution or an endorsement of arbitrary dependent groups.
    a = np.arange(1, 13, dtype=float).reshape(6, 2)
    b = -a

    class FixedPairing:
        def permutation(self, n):
            return np.arange(n)

    monkeypatch.setattr(le.np.random, "default_rng", lambda seed: FixedPairing())
    config = replace(CONFIG, batch_pairs=1, hidden=(), max_epochs=2, patience=1, lr=0.1)
    wealth = []
    for swaps in itertools.product([False, True], repeat=6):
        mask = np.array(swaps)[:, None]
        r = run(np.where(mask, b, a), np.where(mask, a, b), config=config)
        wealth.append(r.e_value)
    assert max(wealth) - min(wealth) > 0.1  # genuine adaptive bets, not all ones
    assert np.mean(wealth) == pytest.approx(1, abs=1e-10)


def test_insufficient_and_unused_units():
    a, b = data(11)
    r = run(a, b)
    assert r.status == "unavailable" and r.e_value is None and r.n_scored == 0
    a, b = data(17)
    r = run(a, b[:15])
    assert r.n_pairs == 15 and len(r.metadata["unused_a"]) == 2
    assert r.n_scored == 6 and r.metadata["scored_pairs"] == 11  # final partial batch scored


@pytest.mark.parametrize("case", ["nan", "genes", "duplicate", "overlap", "missing_ids", "null_id", "scale"])
def test_invalid_inputs(case):
    a, b = data()
    kw = {}
    if case == "nan":
        a[0, 0] = np.nan
    elif case == "genes":
        b = b[:, :2]
    elif case == "duplicate":
        kw["unit_a"] = ["same"] * len(a)
    elif case == "overlap":
        kw.update(unit_a=list(map(str, range(len(a)))), unit_b=list(map(str, range(len(b)))))
    elif case == "missing_ids":
        kw["sampling"] = le.SamplingContract("aggregated", "cohort", "one independent row per donor", "donor")
    elif case == "null_id":
        kw["unit_a"] = [None, *map(str, range(1, len(a)))]
    else:
        kw["sampling"] = replace(CONTRACT, input_scale="counts")
    with pytest.raises(ValueError):
        run(a, b, **kw)


def fixture_encoder(tmp_path, kind="pca"):
    rng = np.random.default_rng(88)
    X = np.exp(rng.normal(size=(30, 3)))
    kw = dict(genes=["g0", "g1", "g2"], units=[f"train-{i}" for i in range(30)],
              source="independent synthetic training cohort", sampling="iid lognormal",
              unit_namespace="fixture", components=2)
    if kind == "pca":
        encoder = fit_pca(X, **kw)
    else:
        encoder = fit_autoencoder(X, **kw, hidden=4, epochs=3, batch_size=10)
    p = tmp_path / f"{kind}.npz"
    encoder.save(p)
    return FrozenEncoder.load(p), p


@pytest.mark.parametrize("kind", ["pca", "autoencoder"])
def test_encoder_roundtrip_alignment_and_frozen_statistics(tmp_path, kind):
    encoder, path = fixture_encoder(tmp_path, kind)
    X = np.ones((4, 3))
    expected = encoder.transform(X, genes=["g0", "g1", "g2"])
    assert np.allclose(expected, encoder.transform(X[:, ::-1], genes=["g2", "g1", "g0"]))
    assert np.array_equal(expected, FrozenEncoder.load(path).transform(X, genes=["g0", "g1", "g2"]))
    other = np.concatenate([X, 1e6 * X])
    assert np.allclose(expected, encoder.transform(other, genes=["g0", "g1", "g2"])[:4])
    assert not encoder.mean.flags.writeable
    # Missing gene equals imputation in log1p(TPM) space.
    imputed = X.copy()
    imputed[:, 2] = np.expm1(encoder.mean[2])
    assert np.allclose(encoder.transform(X[:, :2], genes=["g0", "g1"], max_missing_fraction=0.4),
                       encoder.transform(imputed, genes=["g0", "g1", "g2"]))
    with pytest.raises(ValueError, match="missing"):
        encoder.transform(X[:, :2], genes=["g0", "g1"])


def test_real_contract_overlap_and_aggregation(tmp_path):
    _, path = fixture_encoder(tmp_path)
    a, b = data()
    a, b = np.exp(a), np.exp(b)
    contract = le.SamplingContract("expression", "fixture", "independent donors; matched technical replicates",
                                   "fixture", "TPM", "mean_tpm")
    kw = dict(config=replace(CONFIG, encoder=str(path)), sampling=contract,
              unit_a=[f"a{i}" for i in range(len(a))], unit_b=[f"b{i}" for i in range(len(b))])
    original = run(a, b, **kw)
    replicated = run(np.repeat(a, 2, axis=0), np.repeat(b, 2, axis=0),
                     **{**kw, "unit_a": np.repeat(kw["unit_a"], 2), "unit_b": np.repeat(kw["unit_b"], 2)})
    assert original.e_value == replicated.e_value
    kw["unit_a"][0] = "train-0"
    with pytest.raises(ValueError, match="overlap"):
        run(a, b, **kw)


def test_utility_contracts_and_edges():
    assert p_to_e(1) == 0 and p_to_e(0.01) == 9
    assert e_to_p(0) == 1 and e_to_p(100) == 0.01
    assert e_bh([100, 50, 1], alpha=0.05) == [0, 1]
    assert e_bh([], alpha=0.05) == []
    assert mean_merge([0, 2]) == 1
    assert product_merge([0, 2], validity="conditional") == 0
    assert math.isfinite(from_log(1000)) and from_log(-1000) == 0
    for p in [0, -1, float("nan"), float("inf")]:
        with pytest.raises(ValueError):
            p_to_e(p)
    for e in [-1, float("nan"), float("inf")]:
        with pytest.raises(ValueError):
            e_to_p(e)
    with pytest.raises(ValueError):
        product_merge([2, 3], validity="dependent")


@pytest.mark.parametrize("changes", [{"burn_in": 1}, {"tanh_clip": 100}, {"batch_pairs": 0},
                                     {"seed": -1}, {"hidden": (0,)}, {"max_epochs": 0}])
def test_invalid_config(changes):
    a, b = data()
    with pytest.raises(ValueError):
        run(a, b, config=replace(CONFIG, **changes))
