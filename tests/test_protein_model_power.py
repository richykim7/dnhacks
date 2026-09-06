from pathlib import Path
import runpy
import pytest
torch=pytest.importorskip("torch")


def test_injected_module_effect_uses_covariance_not_gene_count():
    m=runpy.run_path(str(Path(__file__).parents[1]/"scripts/validate_protein_model_power.py"))
    load=torch.tensor([[1.,0.],[1.,0.],[0.,2.]])
    residual=torch.tensor([1.,1.,4.])
    sd=m["module_sd"](load,residual,[0,1])
    assert float(sd)==pytest.approx(1.5**.5)
    shift=.4*sd
    assert float(torch.tensor([shift,shift]).mean()/sd)==pytest.approx(.4)
