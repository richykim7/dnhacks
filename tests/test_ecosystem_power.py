import numpy as np
import pytest

from dnhacksbio.ecosystem_power import bounded_kernel


def test_kernel_is_bounded_and_swapping_one_view_reverses_it():
    from dnhacksbio.native_evidence import association_factor

    rng = np.random.default_rng(11)
    c = rng.uniform(-1, 1, size=(7, 7))
    for i in range(7):
        for j in range(7):
            h = bounded_kernel(c, i, i, j, j)
            assert -1 <= h <= 1
            assert h == pytest.approx(-bounded_kernel(c, i, j, j, i))
            assert 1 + 0.9 * h > 0
            assert 1 + 0.9 * h == pytest.approx(
                association_factor([c[i, i], c[j, j], c[i, j], c[j, i]])
            )


def test_product_null_kernel_mean_is_exactly_zero_for_arbitrary_frozen_critic():
    # Exhaust the product distribution, including repeats; not just Monte Carlo.
    c = np.array([[0.9, -0.3, 0.4], [-0.7, 0.2, 0.5], [0.6, -0.1, -0.8]])
    p, q = np.array([0.2, 0.3, 0.5]), np.array([0.1, 0.7, 0.2])
    expectation = sum(
        p[i] * q[j] * p[k] * q[l] * bounded_kernel(c, i, j, k, l)
        for i in range(3)
        for j in range(3)
        for k in range(3)
        for l in range(3)
    )
    assert expectation == pytest.approx(0, abs=1e-15)


def test_power_diagnostic_does_not_fall_back_to_cpu(monkeypatch, tmp_path):
    torch = pytest.importorskip("torch")
    from dnhacksbio.ecosystem_power import diagnose

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="CUDA required"):
        diagnose(tmp_path, tmp_path / "report.json")
    assert not (tmp_path / "report.json").exists()


def test_growth_training_does_not_fall_back_to_cpu(monkeypatch, tmp_path):
    torch = pytest.importorskip("torch")
    from dnhacksbio.ecosystem_power_training import run

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="CUDA required"):
        run(tmp_path, tmp_path / "new-models")
    assert not (tmp_path / "new-models").exists()
