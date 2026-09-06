import numpy as np
import pytest
torch = pytest.importorskip("torch")
from dnhacksbio.protein_native_diagnostics import factors, interval, streams


def test_actual_kernel_is_odd_and_positive():
    a = torch.tensor([[[1., 2.], [3., 4.]]])
    b = -a
    w = torch.tensor([[.3,.1]])
    forward = factors(a,b,w).exp()
    reverse = factors(b,a,w).exp()
    torch.testing.assert_close(forward+reverse,torch.full_like(forward,2.))
    assert (forward>0).all() and (forward<2).all()


def test_diagnostic_budget_and_invalid_control():
    valid = streams("normal_null",n=200,seed=4)
    invalid = streams("current_batch_leak",n=200,seed=4)
    assert valid["scored_pairs"] == 32
    assert invalid["invalid_control"]
    assert invalid["anytime_rate"] > valid["anytime_rate"]
    assert interval(0,10000)[1] > 0
