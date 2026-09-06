import pytest
from dnhacksbio.ecosystem_cna import ARCHIVE, GeoRangeReader, partition


def source_fixture():
    clinical = {
        f"PN{i}": dict(neoadjuvant=int(i < 5), lpWGS=int(i > 4)) for i in range(1, 22)
    }
    text = "".join(
        f"^SAMPLE = GSM{8000000 + i}\n!Sample_title = PDAC snRNAseq [PN{i}]\n"
        f"!Sample_supplementary_file_1 = https://ftp.ncbi.nlm.nih.gov/geo/samples/GSM8000nnn/GSM{8000000 + i}/suppl/GSM{8000000 + i}_PN{i}_filtered_feature_bc_matrix.h5\n"
        for i in range(1, 22)
    )
    return text, clinical


def test_partition_is_metadata_only_and_keeps_treatment():
    text, clinical = source_fixture()
    r = partition(text, clinical, "source-hash")
    assert not r["private_confirmation"]
    assert sum(s["role"] == "train" for s in r["samples"]) == 11
    assert sum(s["neoadjuvant"] == 0 for s in r["samples"]) == 17
    reversed_text = "".join(
        "^SAMPLE = " + s for s in reversed(text.split("^SAMPLE = ")[1:])
    )
    assert partition(reversed_text, clinical, "source-hash") == r


def test_partition_rejects_donor_count_swap_and_missing_donor():
    text, clinical = source_fixture()
    with pytest.raises(ValueError, match="count file mismatch"):
        partition(text.replace("GSM8000001_PN1_", "GSM8000001_PN2_"), clinical, "hash")
    with pytest.raises(ValueError, match="missing original donor"):
        partition(text.split("^SAMPLE = GSM8000021")[0], clinical, "hash")


def test_range_reader_rejects_wrong_response_and_unapproved_source(monkeypatch):
    import requests

    class Response:
        status_code = 200
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, size):
            raise AssertionError("Must reject before consuming body")

    monkeypatch.setattr(requests, "get", lambda *a, **kw: Response())
    with pytest.raises(ValueError, match="wrong byte range"):
        GeoRangeReader(ARCHIVE)
    with pytest.raises(ValueError, match="audited public"):
        GeoRangeReader("https://example.com/large.zip")


def test_cna_training_requires_cuda_before_output(monkeypatch, tmp_path):
    torch = pytest.importorskip("torch")
    from dnhacksbio.ecosystem_cna import train_malignancy, evaluate_existing_critic

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="CUDA required"):
        train_malignancy(tmp_path, tmp_path / "out")
    with pytest.raises(RuntimeError, match="CUDA required"):
        evaluate_existing_critic(tmp_path, tmp_path, tmp_path, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_frozen_critic_uses_original_training_scale_and_no_new_donor_fit():
    torch = pytest.importorskip("torch")
    from dnhacksbio.ecosystem_cna import frozen_critic_scores

    old = [torch.tensor([[2.0], [4.0], [100.0]]), torch.tensor([[3.0], [7.0], [200.0]])]
    train = torch.tensor([0, 1])
    new = [torch.tensor([[3.0], [5.0]]), torch.tensor([[4.0], [8.0]])]
    state = {
        "x_mean": torch.tensor([0.2]),
        "y_mean": torch.tensor([-0.1]),
        "x_scale": torch.tensor([2.0]),
        "y_scale": torch.tensor([3.0]),
        "left.0.weight": torch.ones(1, 1),
        "right.0.weight": torch.ones(1, 1),
        "left.0.bias": torch.zeros(1),
        "right.0.bias": torch.zeros(1),
        "weight": torch.ones(1),
        "offset": torch.tensor(0.0),
    }
    actual = frozen_critic_scores(old, train, new, state)
    x = ((new[0] - 3) / torch.sqrt(torch.tensor(2.0)) - 0.2) / 2
    y = ((new[1] - 5) / torch.sqrt(torch.tensor(8.0)) + 0.1) / 3
    assert torch.allclose(actual, torch.tanh(x.tanh() @ y.tanh().T))
    extended = [torch.cat([v, torch.tensor([[10000.0]])]) for v in new]
    assert torch.allclose(
        frozen_critic_scores(old, train, extended, state)[:2, :2], actual
    )


def test_original_count_join_retains_full_library_and_reports_missing_cells(
    monkeypatch, tmp_path
):
    import json
    import numpy as np

    h5py = pytest.importorskip("h5py")
    from dnhacksbio import ecosystem_cna as cna

    raw = tmp_path / "raw"
    raw.mkdir()
    audit = tmp_path / "audit"
    audit.mkdir()
    source = raw / "original.h5"
    with h5py.File(source, "w") as f:
        m = f.create_group("matrix")
        m["data"] = np.array([2, 3, 5, 7], dtype=np.int32)
        m["indices"] = np.array([0, 2, 1, 2], dtype=np.int32)
        m["indptr"] = np.array([0, 2, 4], dtype=np.int32)
        m["shape"] = np.array([3, 2])
        m["barcodes"] = np.array([b"cancer-1", b"fibro-1"])
        m.create_group("features")["name"] = np.array([b"A", b"B", b"C"])
    frozen = {
        "samples": [
            dict(
                sample="GSM1",
                donor="GSE253429:PN1",
                files=["https://example.org/original.h5"],
                role="train",
                neoadjuvant=0,
                lpWGS=1,
            )
        ]
    }
    monkeypatch.setattr(cna, "freeze", lambda root: frozen)
    (audit / "partition.json").write_text(json.dumps(frozen))
    (audit / "acquisition.json").write_text(
        json.dumps([dict(file=source.name, sha256=cna.digest(source))])
    )
    reports = []
    for name, rows in {
        "cancer": [("cancer-1_1", "Classical"), ("absent-1_1", "Classical")],
        "CAF": [("fibro-1_1", "myofibroblast")],
        "exocrine": [],
    }.items():
        path = audit / f"{name}-labels.tsv"
        path.write_text(
            "author_cell_id\torig.ident\tcell_type\thistology\tsubcompartment\ttreatment\n"
            + "".join(
                f"{cell}\tPN1\t{kind}\t{name}\t{name}\tuntreated\n"
                for cell, kind in rows
            )
        )
        reports.append(
            dict(member=f"compartments/{name}.RData", sha256=cna.digest(path))
        )
    (audit / "annotations.json").write_text(json.dumps(reports))
    panel = tmp_path / "panel.json"
    panel.write_text(json.dumps({"genes": ["A", "B"]}))
    with pytest.raises(ValueError, match="1 author cells missing"):
        cna.prepare(tmp_path, panel)
    report = cna.prepare(tmp_path, panel, allow_missing_author_cells=True)
    assert report["cells"] == 2 and report["missing_author_cells"] == {"PN1:cancer": 1}
    with np.load(tmp_path / "prepared/GSM1.npz", allow_pickle=False) as z:
        cells = json.loads(str(z["cells"]))
        assert [c["library_size"] for c in cells] == [5, 12]
        assert [c["label"] for c in cells] == [0, 1]
    panel.write_text(json.dumps({"genes": ["A", "unmeasured"]}))
    with pytest.raises(ValueError, match="unmeasured"):
        cna.prepare(tmp_path, panel, allow_missing_author_cells=True)
