"""Checks for the synthetic feasibility benchmark, not biological acceptance."""
import importlib.util
from pathlib import Path
import sys

import pytest


def test_native_nonlinear_factor_and_bilinear_reflection():
    torch=pytest.importorskip('torch')
    if not torch.cuda.is_available():pytest.skip('CUDA required')
    scripts=Path(__file__).parents[1]/'scripts'
    sys.path.insert(0,str(scripts))
    try:
        spec=importlib.util.spec_from_file_location('critic_benchmark',scripts/'validate_pharmacotype_critic_cuda.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    finally:sys.path.remove(str(scripts))
    rows=torch.tensor([[-2.,4.],[1.,1.],[-.5,.25],[3.,9.]],device='cuda')
    reflected=rows.clone();reflected[:,0]*=-1
    linear=lambda x:(x[:,0]*x[:,1]).tanh()
    assert torch.allclose(module.factors(linear,rows)+module.factors(linear,reflected),torch.full((2,),2.,device='cuda'))
    nonlinear=lambda x:(1-(x[:,1]-x[:,0].square()).square()).tanh()
    assert bool((module.factors(nonlinear,rows)>1).all())
    assert torch.allclose(module.factors(nonlinear,rows),module.factors(nonlinear,reflected))
    # Exercise the real native arithmetic cross-check on fresh streams.
    result=module.evaluate(torch,nonlinear,'nonlinear',streams=100,donors=4)
    assert 0<=result['anytime_rate']<=1
