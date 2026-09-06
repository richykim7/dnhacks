import pytest


def test_fixed_bag_coverage_and_cell_order_invariance():
    torch = pytest.importorskip("torch")
    from dnhacksbio.ecosystem_snrna import fixed_bag_summary

    z = torch.arange(180, dtype=torch.float32).reshape(90, 2)
    labels = torch.zeros(90, dtype=torch.long)
    metadata = [
        dict(
            cell_id=f"c{i:03}",
            donor="low" if i < 26 else "enough",
            role="train",
            study="s",
        )
        for i in range(90)
    ]
    values, donors, roles, studies = fixed_bag_summary(z, labels, metadata, 0)
    assert donors == ["enough"] and roles == ["train"] and studies == ["s"]
    assert values.shape == (1, 4)
    order = list(reversed(range(90)))
    permuted = fixed_bag_summary(
        z[order], labels[order], [metadata[i] for i in order], 0
    )[0]
    assert torch.equal(values, permuted)
    assert fixed_bag_summary(z, labels, metadata, 1)[0].shape == (0, 4)


def test_fixed_bags_reject_donor_role_overlap():
    torch = pytest.importorskip("torch")
    from dnhacksbio.ecosystem_snrna import fixed_bag_summary

    metadata = [
        dict(
            cell_id=str(i),
            donor="d",
            role="train" if i < 16 else "validation",
            study="s",
        )
        for i in range(32)
    ]
    with pytest.raises(ValueError, match="crosses roles"):
        fixed_bag_summary(
            torch.zeros((32, 2)), torch.zeros(32, dtype=torch.long), metadata, 0
        )


def test_snrna_transfer_requires_cuda(monkeypatch, tmp_path):
    torch = pytest.importorskip("torch")
    from dnhacksbio.ecosystem_snrna import evaluate

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="CUDA required"):
        evaluate(tmp_path, tmp_path, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_summary_merge_refuses_repeated_donors(tmp_path):
    import numpy as np
    from dnhacksbio.ecosystem_snrna import combine_summaries

    for source in ("a", "b"):
        (tmp_path / source).mkdir()
        for compartment in ("epithelial-enriched", "fibroblast"):
            np.savez_compressed(
                tmp_path / source / f"{compartment}-donor-summaries.npz",
                values=np.ones((1, 2)),
                donors=np.array(["same"]),
                roles=np.array(["train"]),
                studies=np.array([source]),
            )
    with pytest.raises(ValueError, match="Repeated canonical donor"):
        combine_summaries(tmp_path / "a", tmp_path / "b", tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_source_partition_freezes_roles_and_rejects_treated_or_duplicate_samples():
    from dnhacksbio.ecosystem_snrna import partition_from_geo

    source = "".join(
        f"^SAMPLE = GSM{i}\n!Sample_title = PDAC Tumor Sample PDAC{i}\n"
        "!Sample_characteristics_ch1 = treatment: treatment-naive\n"
        "!Sample_characteristics_ch1 = tissue: Pancreas (tumor)\n"
        + "".join(f"!Sample_supplementary_file_{j} = https://ftp.ncbi.nlm.nih.gov/geo/samples/GSM{i}/file{j}.gz\n" for j in range(1, 4))
        for i in range(1, 18)
    )
    partition = partition_from_geo(source)
    assert sum(s["role"] == "train" for s in partition["samples"]) == 9
    assert sum(s["role"] == "development-validation" for s in partition["samples"]) == 8
    with pytest.raises(ValueError, match="population"):
        partition_from_geo(source.replace("treatment-naive", "treated", 1))
    with pytest.raises(ValueError, match="inventory"):
        partition_from_geo(source.replace("^SAMPLE = GSM17", "^SAMPLE = GSM16"))
