import json
import numpy as np
import pytest
openpyxl=pytest.importorskip("openpyxl")
from dnhacksbio.protein_external import read_fudan, annotation, unique


def fixture(root):
    w=openpyxl.Workbook();s=w.active;s.title="Table S1B"
    s.append(["Sample ID","Differentiation","Tumor purity (%)"])
    s.append(["PDAC_1","Poorly",60]);s.append(["PDAC_2","Moderately",40])
    s=w.create_sheet("Table S1A ");s.append(["header"]);s.append(["header2"])
    for donor in (1,2):
        s.append([None]*9+[f"PDAC_{donor}T",f"run-{donor}"])
    w.save(root/"supplement-23.xlsx")
    w=openpyxl.Workbook();s=w.active;s.title="Table S3A "
    s.append(["Symbol","PDAC_1T","PDAC_2T","PDAC_1N"])
    s.append(["ATM",1,2,4]);s.append(["ATR","NA",0,5])
    w.save(root/"supplement-25.xlsx")


def test_primary_tumor_grade_join_and_missingness(tmp_path):
    fixture(tmp_path)
    matrix,labels,audit=read_fudan(tmp_path)
    assert matrix.shape==(2,2)
    assert matrix.ATR.isna().all()
    assert audit["grade_pairs"]==1
    assert [r["grade"] for r in labels]==["G3","G2"]
    assert [r["experiment"] for r in labels]==["run-1","run-2"]


def test_duplicate_run_cannot_create_another_patient(tmp_path):
    fixture(tmp_path)
    path=tmp_path/"supplement-23.xlsx"
    w=openpyxl.load_workbook(path);w["Table S1A "]["K4"]="run-1";w.save(path)
    with pytest.raises(ValueError,match="duplicated experiments"):
        read_fudan(tmp_path)


def test_unjoined_tumor_rejected(tmp_path):
    fixture(tmp_path)
    path=tmp_path/"supplement-25.xlsx"
    w=openpyxl.load_workbook(path);w.active["C1"]="PDAC_3T";w.save(path)
    with pytest.raises(ValueError,match="Unjoined"):
        read_fudan(tmp_path)


def test_ambiguous_annotations_are_not_arbitrarily_collapsed(tmp_path):
    (tmp_path/"hgnc.tsv").write_text("symbol\tstatus\tensembl_gene_id\tprev_symbol\nA\tApproved\tENSG1\tOLD\nB\tApproved\tENSG1\tOLD\nC\tApproved\tENSG2\tPREV\n")
    ids,names=annotation(tmp_path)
    assert ids=={"ENSG2":"C"}
    assert "OLD" not in names
    assert names["PREV"]=="C"


def test_rank_ties_and_missingness_use_per_donor_transform():
    torch=pytest.importorskip("torch")
    import runpy
    from pathlib import Path
    module=runpy.run_path(str(Path(__file__).parents[1]/"scripts/evaluate_protein_external.py"))
    x=torch.tensor([[1.,1.,3.,float("nan")],[float("nan")]*4])
    actual=module["percentile"](x)
    torch.testing.assert_close(actual,torch.tensor([[.375,.375,.75,.5],[.5]*4]))
    assert torch.equal(actual[:1],module["percentile"](x[:1]))


def test_changed_predictions_cannot_be_evaluated_as_frozen(tmp_path):
    from dnhacksbio.protein_external import summarize
    path=tmp_path/"predictions.npz"
    path.write_bytes(b"changed after training")
    (tmp_path/"training.json").write_text(json.dumps({"predictions_sha256":"0"*64}))
    with pytest.raises(ValueError,match="provenance"):
        summarize(tmp_path,path,tmp_path/"report.json")
