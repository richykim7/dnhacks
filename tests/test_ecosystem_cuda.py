import json
import numpy as np
import pytest


def test_cuda_training_refuses_cpu_fallback(monkeypatch, tmp_path):
    torch = pytest.importorskip("torch")
    from dnhacksbio.ecosystem_cuda import run

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="CPU training fallback"):
        run(tmp_path / "prepared", tmp_path / "models", epochs=1)
    assert not (tmp_path / "models").exists()


def test_cuda_requires_canonical_lease_before_work(tmp_path):
    pytest.importorskip("torch")
    from dnhacksbio.ecosystem_cuda import run

    with pytest.raises(ValueError, match="Canonical"):
        run(tmp_path / "prepared", tmp_path / "models", lease="/tmp/wrong-gpu.lock")


def test_expansion_alignment_sums_duplicate_symbols_without_imputation(tmp_path):
    sparse = pytest.importorskip("scipy.sparse")
    from dnhacksbio.ecosystem_expansion import align, save_pack

    x = sparse.csr_matrix([[2, 3, 5], [7, 11, 13]])
    y = align(x, ["A", "B", "A"], ["A", "B"])
    assert y.toarray().tolist() == [[7, 3], [20, 11]]
    cells = [dict(donor="d1"), dict(donor="d2")]
    save_pack(
        tmp_path / "x.npz", y, ["A", "B"], cells, dict(schema="ecosystem-expanded-v1")
    )
    with np.load(tmp_path / "x.npz", allow_pickle=False) as z:
        assert json.loads(str(z["cells"])) == cells
        assert z["data"].dtype.kind == "i"


def test_expansion_original_10x_units_and_shape(tmp_path):
    import gzip

    pytest.importorskip("scipy")
    from scipy import sparse, io
    from dnhacksbio.ecosystem_expansion import read_10x

    paths = [
        tmp_path / n for n in ("barcodes.tsv.gz", "features.tsv.gz", "matrix.mtx.gz")
    ]
    with gzip.open(paths[0], "wt") as f:
        f.write("cell1\ncell2\n")
    with gzip.open(paths[1], "wt") as f:
        f.write("ENSG1\tA\nENSG2\tB\n")
    with gzip.open(paths[2], "wb") as f:
        io.mmwrite(f, sparse.coo_matrix([[1, 2], [3, 4]]))
    counts, genes, cells = read_10x(paths)
    assert (
        counts.toarray().tolist() == [[1, 3], [2, 4]]
        and genes == ["A", "B"]
        and cells == ["cell1", "cell2"]
    )
    with gzip.open(paths[2], "wb") as f:
        io.mmwrite(f, sparse.coo_matrix([[1, 0.5], [2, 3]]))
    with pytest.raises(ValueError, match="integer count"):
        read_10x(paths)
