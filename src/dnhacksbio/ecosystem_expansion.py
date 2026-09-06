"""Sparse preparation for expanded, exposed cellular development cohorts.

This module performs data loading/alignment, not model fitting. CUDA owns all
learned annotation, dimensionality reduction and encoder/scorer training.
"""

from __future__ import annotations
import gzip, json, re, hashlib
from pathlib import Path
import numpy as np
from scipy import sparse, io
from .ecosystem_data import count_rows, sha256

CLASS_NAMES = ("epithelial", "fibroblast", "immune", "endothelial", "other")
PENG_LABELS = {
    "Ductal cell type 2": 0,
    "Ductal cell type 1": 0,
    "Fibroblast cell": 1,
    "Macrophage cell": 2,
    "T cell": 2,
    "B cell": 2,
    "Endothelial cell": 3,
}
MARKERS = [
    "EPCAM",
    "KRT8",
    "KRT18",
    "KRT19",
    "KRT7",
    "MUC1",
    "COL1A1",
    "COL1A2",
    "DCN",
    "LUM",
    "COL3A1",
    "PDGFRA",
    "PTPRC",
    "CD3D",
    "CD3E",
    "CD79A",
    "MS4A1",
    "LST1",
    "LYZ",
    "PECAM1",
    "VWF",
    "KDR",
    "RGS5",
    "CSPG4",
    "ACTA2",
    "PRSS1",
    "PRSS2",
    "AMY2A",
    "CPA1",
    "INS",
    "GCG",
]


def decode(a):
    return [v.decode() if isinstance(v, bytes) else str(v) for v in a]


def read_10x(paths):
    """Read one original 10x library as sparse cells x genes; never dense atlas."""
    paths = [Path(p) for p in paths]
    if len(paths) == 1 and paths[0].suffix == ".h5":
        import h5py

        with h5py.File(paths[0]) as f:
            m = f["matrix"]
            shape = tuple(m["shape"][:])
            counts = sparse.csc_matrix(
                (m["data"][:], m["indices"][:], m["indptr"][:]), shape=shape
            ).T.tocsr()
            genes = decode(m["features/name"][:])
            barcodes = decode(m["barcodes"][:])
    else:
        with gzip.open(next(p for p in paths if "matrix.mtx" in p.name), "rb") as f:
            counts = io.mmread(f).T.tocsr()
        with gzip.open(
            next(p for p in paths if "genes.tsv" in p.name or "features.tsv" in p.name),
            "rt",
        ) as f:
            genes = [l.rstrip().split("\t")[1] for l in f]
        with gzip.open(next(p for p in paths if "barcodes.tsv" in p.name), "rt") as f:
            barcodes = [l.strip() for l in f]
    if (
        counts.shape != (len(barcodes), len(genes))
        or np.any(counts.data < 0)
        or np.any(counts.data != np.floor(counts.data))
    ):
        raise ValueError("Original integer count shape/units invalid")
    return counts, genes, barcodes


def align(counts, genes, panel):
    lookup = {g: i for i, g in enumerate(panel)}
    entries = [(i, lookup[g]) for i, g in enumerate(genes) if g in lookup]
    projection = sparse.coo_matrix(
        (np.ones(len(entries), dtype=np.int64), tuple(zip(*entries))),
        shape=(len(genes), len(panel)),
    ).tocsr()
    result = (counts @ projection).tocsr()
    result.sum_duplicates()
    result.sort_indices()
    return result


def save_pack(path, counts, genes, cells, manifest):
    counts = counts.tocsr()
    counts.sort_indices()
    if len(cells) != counts.shape[0] or len(genes) != counts.shape[1]:
        raise ValueError("Pack shape mismatch")
    with Path(path).open("wb") as f:
        np.savez_compressed(
            f,
            data=counts.data.astype(np.int64),
            indices=counts.indices.astype(np.int64),
            indptr=counts.indptr.astype(np.int64),
            genes=np.asarray(genes),
            cells=json.dumps(cells),
            manifest=json.dumps(manifest, sort_keys=True),
        )


def panel_from_metadata(root):
    root = Path(root)
    expanded = root / "expansion"
    partition = json.loads((expanded / "audit/partition.json").read_text())
    # Existing training-only selected genes, restricted by external feature names
    # only; no external numerical expression participates in feature selection.
    candidate = set(MARKERS)
    for comp in ("malignant", "fibroblast"):
        candidate.update(
            json.loads(
                (root / "prepared" / f"{comp}-state-reference.json").read_text()
            )["genes"]
        )
    allowed = None
    for s in partition["samples"]:
        paths = [
            expanded / "raw" / s["study"] / u.rsplit("/", 1)[1] for u in s["files"]
        ]
        if paths[0].suffix == ".h5":
            import h5py

            with h5py.File(paths[0]) as f:
                measured = set(decode(f["matrix/features/name"][:]))
        else:
            feature = next(
                p for p in paths if "features.tsv" in p.name or "genes.tsv" in p.name
            )
            with gzip.open(feature, "rt") as f:
                measured = {l.rstrip().split("\t")[1] for l in f}
        allowed = measured if allowed is None else allowed & measured
    # Lin is kept as an external study; all of its original feature metadata
    # constrains availability too, never its outcomes.
    for p in (root / "raw/lin").glob("*.tsv.gz"):
        if "barcodes" in p.name:
            continue
        with gzip.open(p, "rt") as f:
            allowed &= {l.rstrip().split("\t")[1] for l in f}
    panel = sorted(candidate & allowed)
    if len(panel) < 1000:
        raise ValueError("Insufficient common measured panel")
    (expanded / "audit/panel.json").write_text(
        json.dumps(
            dict(
                genes=panel,
                selection="union of Peng-training panels plus predefined markers, intersected using feature metadata",
            ),
            indent=2,
        )
        + "\n"
    )
    return panel


def prepare_peng(root, panel):
    root = Path(root)
    expanded = root / "expansion"
    p = root / "raw/peng-count-matrix.txt"
    with p.open() as f:
        ids = [s.strip('"') for s in f.readline().split()]
    labels = {
        l.split("\t")[0]: l.rstrip().split("\t")[1]
        for l in (root / "source-audit/peng-celltypes.txt").read_text().splitlines()[1:]
    }
    selected = np.array([i for i, c in enumerate(ids) if c.startswith("T")])
    lookup = {g: i for i, g in enumerate(panel)}
    totals = np.zeros(len(ids), dtype=np.int64)
    rows = []
    cols = []
    values = []
    for gene, count in count_rows(p):
        totals += count
        if gene in lookup:
            v = count[selected]
            nz = np.flatnonzero(v)
            rows.append(nz)
            cols.append(np.full(len(nz), lookup[gene]))
            values.append(v[nz])
    counts = sparse.coo_matrix(
        (np.concatenate(values), (np.concatenate(rows), np.concatenate(cols))),
        shape=(len(selected), len(panel)),
    ).tocsr()
    cells = []
    for i in selected:
        donor = ids[i].split("_")[0]
        n = int(donor[1:])
        cells.append(
            dict(
                cell_id=ids[i],
                donor="CRA001160:" + donor,
                study="CRA001160",
                label=PENG_LABELS.get(labels[ids[i]], 4),
                label_source="original-published-Peng-compartment",
                library_size=int(totals[i]),
                role="train" if n <= 16 else "validation",
            )
        )
    dest = expanded / "prepared/peng.npz"
    save_pack(
        dest,
        counts,
        panel,
        cells,
        dict(
            schema="ecosystem-expanded-v1",
            source_sha256=sha256(p),
            note="Exposed development only, epithelial includes type1/type2 and is not a CNA call",
        ),
    )
    return dict(
        study="CRA001160",
        cells=len(cells),
        donors=24,
        path=str(dest),
        sha256=sha256(dest),
    )


def prepare_external(root, panel):
    import pandas as pd

    root = Path(root)
    expanded = root / "expansion"
    plan = json.loads((expanded / "audit/partition.json").read_text())
    steele = pd.read_csv(expanded / "audit/metadata.txt", sep=r"\s+", index_col=0)
    annotation = {}
    for sample, g in steele.groupby("sample_name"):
        annotation[str(sample)] = {
            idx.split("_", 1)[1]: (
                str(r.patient_id),
                str(r.cell_types),
                int(r.nCount_RNA),
            )
            for idx, r in g.iterrows()
        }
    known = {
        "Epithelial": 0,
        "Fibroblast": 1,
        "Endothelial": 3,
        "Acinar": 4,
        "Pericytes": 4,
        "Endocrine": 4,
        "Neural": 4,
        "Cycling": 4,
    }
    packed = {}
    identities = set()
    audit = []
    for s in plan["samples"]:
        paths = [
            expanded / "raw" / s["study"] / u.rsplit("/", 1)[1] for u in s["files"]
        ]
        counts, genes, barcodes = read_10x(paths)
        totals = np.asarray(counts.sum(1)).ravel()
        donor = s["donor"]
        mapping = None
        if s["study"] == "GSE229413":
            matches = []
            for sample, meta in annotation.items():
                same = sum(
                    b in meta and meta[b][2] == int(t) for b, t in zip(barcodes, totals)
                )
                matches.append((same, sample))
            matches.sort(reverse=True)
            if matches[0][0] < 20 or matches[0][0] <= matches[1][0] * 2:
                # Two deposited reprocessed libraries do not match the older
                # annotation barcodes. Keep their explicitly named original
                # patient identity, but do not force incompatible cell labels.
                fallback = {"GSM7277540": "1306", "GSM7277541": "1307"}
                if s["sample"] not in fallback:
                    raise ValueError("Unresolved original Steele library identity")
                donor = "GSE155698:" + fallback[s["sample"]]
                audit.append(
                    dict(
                        sample=s["sample"],
                        canonical_donor=donor,
                        annotation="unmatched; GPU lineage prediction required",
                        identity_source="explicit GEO tumor sample title",
                    )
                )
            else:
                mapping = annotation[matches[0][1]]
                donor = "GSE155698:" + next(iter(mapping.values()))[0]
                audit.append(
                    dict(
                        sample=s["sample"],
                        original_sample=matches[0][1],
                        canonical_donor=donor,
                        exact_barcode_library_matches=matches[0][0],
                    )
                )
        if donor in identities:
            raise ValueError("Repeated canonical donor")
        identities.add(donor)
        # Entire new Zhang cohort is external test. Original Steele donors use a
        # deterministic metadata-only holdout; Werba primary donors train.
        role = (
            "external-test"
            if s["study"] == "GSE212966"
            else (
                "validation"
                if s["study"] == "GSE229413"
                and int(hashlib.sha256(donor.encode()).hexdigest()[:8], 16) % 4 == 0
                else "train"
            )
        )
        metadata = []
        keep = []
        for i, (barcode, total) in enumerate(zip(barcodes, totals)):
            if total <= 0:
                continue
            label = -1
            if mapping is not None:
                if barcode not in mapping:
                    continue
                label = known.get(mapping[barcode][1], 2)
            keep.append(i)
            metadata.append(
                dict(
                    cell_id=s["sample"] + ":" + barcode,
                    donor=donor,
                    study=s["study"],
                    label=label,
                    label_source="original-study-metadata"
                    if mapping
                    else "unlabeled-predict-on-CUDA",
                    library_size=int(total),
                    role=role,
                )
            )
        packed.setdefault(s["study"], []).append(
            (align(counts[keep], genes, panel), metadata)
        )
        print(s["study"], s["sample"], len(keep), role, flush=True)
    # Add all original primary Lin cells, using the existing fixed metadata roles.
    lin = pd.read_csv(root / "source-audit/lin-celltypes.tsv", sep="\t").set_index(
        "Cell"
    )
    for s in json.loads((root / "source-audit/lin-partition.json").read_text())[
        "samples"
    ]:
        paths = [root / "raw/lin" / u.strip().rsplit("/", 1)[1] for u in s["files"]]
        counts, genes, barcodes = read_10x(paths)
        totals = np.asarray(counts.sum(1)).ravel()
        metadata = []
        keep = []
        for i, b in enumerate(barcodes):
            key = s["sample"] + "@" + b
            if key not in lin.index or totals[i] <= 0:
                continue
            info = lin.loc[key]
            label = {
                "Malignant": 0,
                "Fibroblasts": 1,
                "Endothelial": 3,
                "Acinar": 4,
                "Ductal": 0,
            }.get(info["Celltype (major-lineage)"], 2)
            metadata.append(
                dict(
                    cell_id=key,
                    donor="GSE154778:" + str(info.Patient),
                    study="GSE154778",
                    label=label,
                    label_source="TISCH-development-lineage",
                    library_size=int(totals[i]),
                    role="external-test",
                )
            )
            keep.append(i)
        packed.setdefault("GSE154778", []).append(
            (align(counts[keep], genes, panel), metadata)
        )
    results = []
    for study, parts in packed.items():
        cells = [c for _, m in parts for c in m]
        counts = sparse.vstack([x for x, _ in parts], format="csr")
        dest = expanded / "prepared" / f"{study}.npz"
        save_pack(
            dest,
            counts,
            panel,
            cells,
            dict(
                schema="ecosystem-expanded-v1",
                study=study,
                classes=CLASS_NAMES,
                status="exposed-development",
                partition_sha256=sha256(expanded / "audit/partition.json"),
            ),
        )
        results.append(
            dict(
                study=study,
                cells=len(cells),
                donors=len({c["donor"] for c in cells}),
                path=str(dest),
                sha256=sha256(dest),
            )
        )
    (expanded / "audit/steele-crosswalk.json").write_text(
        json.dumps(audit, indent=2) + "\n"
    )
    return results


def prepare(root):
    root = Path(root)
    (root / "expansion/prepared").mkdir(exist_ok=True)
    panel = panel_from_metadata(root)
    print("Common genes", len(panel), flush=True)
    results = [prepare_peng(root, panel), *prepare_external(root, panel)]
    report = dict(
        schema="ecosystem-expansion-preparation-v1",
        sources=results,
        genes=len(panel),
        donors=sum(r["donors"] for r in results),
        cells=sum(r["cells"] for r in results),
        confirmation="unavailable",
    )
    (root / "expansion/audit/preparation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    return report


def acquire(root):
    """Reproduce public metadata/role freeze and original count downloads."""
    import requests, concurrent.futures, time

    root = Path(root) / "expansion"
    audit = root / "audit"
    audit.mkdir(parents=True, exist_ok=True)

    def download(url, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            partial = Path(str(path) + ".part")
            for attempt in range(6):
                try:
                    offset = partial.stat().st_size if partial.exists() else 0
                    with requests.get(
                        url,
                        stream=True,
                        headers={"Range": f"bytes={offset}-"} if offset else {},
                        timeout=(30, 60),
                    ) as response:
                        response.raise_for_status()
                        if offset and (
                            response.status_code != 206
                            or not response.headers.get("Content-Range", "").startswith(
                                f"bytes {offset}-"
                            )
                        ):
                            raise ValueError("Unsafe download resume")
                        with partial.open("ab" if offset else "wb") as f:
                            for data in response.iter_content(1024**2):
                                f.write(data)
                                if f.tell() > 4 * 1024**3:
                                    raise ValueError("Source size cap exceeded")
                    partial.replace(path)
                    break
                except requests.RequestException:
                    if attempt == 5:
                        raise
                    time.sleep(3)
        return dict(
            url=url,
            file=str(path.relative_to(root)),
            bytes=path.stat().st_size,
            sha256=sha256(path),
        )

    samples = []
    records = []
    for acc in ("GSE205013", "GSE212966", "GSE229413"):
        path = audit / f"{acc}-full.txt"
        records.append(
            download(
                f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={acc}&targ=all&form=text&view=full",
                path,
            )
        )
        for chunk in path.read_text().split("^SAMPLE = ")[1:]:
            gsm = chunk.splitlines()[0].strip()
            title = re.search(r"!Sample_title = (.*)", chunk).group(1).strip()
            source = (
                re.search(r"!Sample_source_name_ch1 = (.*)", chunk).group(1).strip()
            )
            use = (
                (acc == "GSE205013" and source == "Primary PDAC")
                or (acc == "GSE212966" and title.startswith("PDAC"))
                or (
                    acc == "GSE229413"
                    and source == "Pancreas Tumor"
                    and "Keller" not in title
                )
            )
            if not use:
                continue
            urls = [
                u.strip().replace("ftp://", "https://")
                for u in re.findall(r"!Sample_supplementary_file_\d+ = (.*)", chunk)
            ]
            if acc == "GSE229413":
                urls = [u for u in urls if "_filtered_" in u]
            if any(
                not u.startswith("https://ftp.ncbi.nlm.nih.gov/geo/samples/")
                for u in urls
            ):
                raise ValueError("Unexpected original count host")
            samples.append(
                dict(
                    study=acc,
                    sample=gsm,
                    donor=("GSE155698:" + title)
                    if acc == "GSE229413"
                    else acc + ":" + title.split(",")[0],
                    files=urls,
                    role="external-test"
                    if acc == "GSE212966"
                    else "development-expansion",
                    treatment=re.findall(
                        r"!Sample_characteristics_ch1 = treatment: (.*)", chunk
                    ),
                )
            )
    doc = dict(
        schema="ecosystem-expansion-partition-v1",
        samples=samples,
        excluded=[
            "Hwang reserved whole study",
            "GSE194247 pooled runs pending demultiplexed donor IDs",
            "GSE211644 T-cell-only",
            "GSE229413 Keller repeat and normals",
            "GSE205013 liver metastases",
        ],
        note="Expanded exposed development includes treatment mixtures; not narrow untreated confirmation. Reprocessed Steele counted once.",
        seed=2701,
    )
    partition = audit / "partition.json"
    if partition.exists() and json.loads(partition.read_text()) != doc:
        raise ValueError("Existing development partition differs")
    if not partition.exists():
        partition.write_text(json.dumps(doc, indent=2) + "\n")
    jobs = [
        (u, root / "raw" / s["study"] / u.rsplit("/", 1)[1])
        for s in samples
        for u in s["files"]
    ]
    with concurrent.futures.ThreadPoolExecutor(3) as pool:
        records.extend(pool.map(lambda args: download(*args), jobs))
    # Range-read only the published cell metadata from the 820 MB author archive.
    # Count matrices come from individual original 10x libraries above.
    import io as stdio, zipfile

    url = "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE229nnn/GSE229413/suppl/GSE229413_tumor_samples.zip"

    class RemoteZip(stdio.RawIOBase):
        def __init__(self):
            self.pos = 0
            self.size = 820087734

        def seekable(self):
            return True

        def tell(self):
            return self.pos

        def seek(self, offset, whence=0):
            self.pos = (
                offset
                if whence == 0
                else self.pos + offset
                if whence == 1
                else self.size + offset
            )
            return self.pos

        def read(self, n=-1):
            n = min(n if n >= 0 else self.size - self.pos, self.size - self.pos)
            if not n:
                return b""
            if n > 64 * 1024**2:
                raise ValueError("Metadata-only range cap")
            response = requests.get(
                url,
                headers={"Range": f"bytes={self.pos}-{self.pos + n - 1}"},
                timeout=40,
            )
            if response.status_code != 206:
                raise ValueError("Archive range response required")
            self.pos += len(response.content)
            return response.content

    metadata = audit / "metadata.txt"
    if not metadata.exists():
        with zipfile.ZipFile(RemoteZip()) as z:
            metadata.write_bytes(z.read("metadata.txt"))
    records.append(
        dict(
            url=url + "#metadata.txt",
            file=str(metadata.relative_to(root)),
            bytes=metadata.stat().st_size,
            sha256=sha256(metadata),
        )
    )
    (audit / "acquisition.json").write_text(json.dumps(records, indent=2) + "\n")
    return dict(
        sources=len(records),
        candidate_donors=len(samples),
        partition_sha256=sha256(partition),
    )
