import pytest
from dnhacksbio.ecosystem_cna_training import critic_folds, donor_groups


def test_critic_folds_hold_out_each_training_donor_once():
    donors = list(range(9))
    folds = critic_folds(donors)
    assert sorted(i for _, held in folds for i in held) == donors
    for fit, held in folds:
        assert len(fit) == 6 and len(held) == 3 and not set(fit) & set(held)
        assert set(fit) | set(held) == set(donors)
    with pytest.raises(ValueError, match="unique"):
        critic_folds([0, 0, 1, 2, 3, 4])


def test_donor_groups_rejects_cross_role_identity():
    with pytest.raises(ValueError, match="crosses"):
        donor_groups(
            [dict(donor="d", role="train"), dict(donor="d", role="validation")], [0]
        )


def test_nb_zero_count_likelihood_preserves_full_library_offset():
    torch = pytest.importorskip("torch")
    from dnhacksbio.ecosystem_cna_training import nb_loss

    # One measured gene plus residual library mass: gene probability is1/4.
    logits = torch.log(torch.tensor([[0.25, 0.75]], dtype=torch.float64))
    dispersion = torch.tensor([1.0], dtype=torch.float64)
    theta = torch.nn.functional.softplus(dispersion) + 1e-4
    actual = nb_loss(
        torch.zeros((1, 1), dtype=torch.float64),
        logits,
        torch.tensor([100.0]),
        dispersion,
    )
    assert torch.allclose(actual, theta * torch.log1p(torch.tensor(25.0) / theta))
    assert (
        nb_loss(torch.zeros((1, 1)), logits, torch.tensor([200.0]), dispersion) > actual
    ).all()


def test_direct_model_training_has_no_cpu_fallback(monkeypatch, tmp_path):
    torch = pytest.importorskip("torch")
    from dnhacksbio.ecosystem_cna_training import run, train_critics

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    for function in (run, train_critics):
        with pytest.raises(RuntimeError, match="CUDA required"):
            function(tmp_path, tmp_path / "output")
    assert not (tmp_path / "output").exists()
