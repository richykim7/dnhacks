"""Importer and frozen-view tests without external downloads."""
import numpy as np
import pandas as pd
import pytest

from dnhacksbio import protein_data
from dnhacksbio.protein_encoder import ProteinEncoder
from dnhacksbio.protein_validation import ranks


def test_duplicate_donor_headers_and_features_rejected(tmp_path):
    path = tmp_path / "matrix.txt"
    path.write_text("idx\ta\ta\nENSG.1\t1\t2\n")
    with pytest.raises(ValueError, match="donor"):
        protein_data.read_matrix(path)
    path.write_text("idx\ta\tb\nENSG.1\t1\t2\nENSG.1\t3\t4\n")
    with pytest.raises(ValueError, match="feature"):
        protein_data.read_matrix(path)


def test_exact_versions_and_missingness_preserved(tmp_path):
    path = tmp_path / "matrix.txt"
    path.write_text("idx\ta\tb\nENSG.1\t1\tNA\nENSG.2\t3\t4\n")
    out = protein_data.read_matrix(path)
    assert list(out.columns) == ["ENSG.1", "ENSG.2"]
    assert np.isnan(out.loc["b", "ENSG.1"])


def test_build_uses_only_train_features_and_rejects_cross_cohort_donor(tmp_path, monkeypatch):
    monkeypatch.setattr(protein_data, "acquire", lambda _: [])
    for name in ("BRCA", "COAD", "LUAD", "PDAC"):
        pd.DataFrame({name+"1": [1, 2], name+"2": [3, 4]}, index=["A.1", "B.2"]).to_csv(tmp_path/f"{name}_proteomics.txt", sep="\t")
        pd.DataFrame({"Histologic_Grade": ["G1 Well differentiated", "G3 Poorly differentiated"]}, index=[name+"1", name+"2"]).to_csv(tmp_path/f"{name}_meta.txt", sep="\t")
    cohorts, report = protein_data.build(tmp_path, max_features=1)
    assert cohorts["TRAIN"]["feature_ids"] == ["A.1"]
    assert cohorts["DEV"]["observations"][0]["treatment"] == "unknown"
    frame = pd.read_csv(tmp_path/"LUAD_proteomics.txt", sep="\t", index_col=0)
    frame.loc["A.1"] = np.nan
    frame.to_csv(tmp_path/"LUAD_proteomics.txt", sep="\t")
    changed, _ = protein_data.build(tmp_path, max_features=1)
    assert changed["TRAIN"] == cohorts["TRAIN"]
    frame.columns = ["BRCA1", "LUAD2"]
    frame.to_csv(tmp_path/"LUAD_proteomics.txt", sep="\t")
    with pytest.raises(ValueError, match="overlap"):
        protein_data.build(tmp_path, max_features=1)


def test_rank_transform_is_per_donor_and_masks_hide_values():
    x = np.array([[1., 5., 3.], [100., 10., 0.]])
    mask = np.array([[True, False, True], [True, True, True]])
    original = ranks(x, mask)
    x[0, 1] = -100000
    np.testing.assert_array_equal(original, ranks(x, mask))
    x[1] += 12345
    np.testing.assert_array_equal(original[0], ranks(x, mask)[0])


def test_reconstruction_does_not_reveal_masked_values():
    encoder = ProteinEncoder({"kind": "pca", "feature_ids": ["a", "b"]},
        {"input_center": np.zeros(4), "components": np.eye(4)[:2]})
    x = np.array([[1., 0., 1., 0.]])
    np.testing.assert_array_equal(encoder.reconstruct_inputs(x), [[1., 0.]])
