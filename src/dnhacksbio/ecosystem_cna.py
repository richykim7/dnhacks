"""Public CUIMC development-source audit and bounded original-file acquisition.

This recurrence-selected cohort is not an untreated confirmation population.
Only source metadata is used to freeze donor roles before numerical acquisition.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


GEO = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE253429&targ=all&form=text&view=full"
CLINICAL = "https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41588-025-02345-5/MediaObjects/41588_2025_2345_MOESM3_ESM.xlsx"
ARCHIVE = "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE253nnn/GSE253429/suppl/GSE253429_compartments.zip"
MEMBERS = (
    "compartments/cancer.RData",
    "compartments/CAF.RData",
    "compartments/exocrine.RData",
)


def digest(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def clinical_mapping(content):
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        strings = [
            "".join(e.itertext())
            for e in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns)
        ]
        rows = ET.fromstring(z.read("xl/worksheets/sheet1.xml")).findall(".//m:row", ns)
        result = {}
        header_checked = False
        for row in rows:
            values = {}
            for cell in row.findall("m:c", ns):
                v = cell.find("m:v", ns)
                if v is not None:
                    values[re.sub(r"\d+", "", cell.attrib["r"])] = (
                        strings[int(v.text)] if cell.attrib.get("t") == "s" else v.text
                    )
            if values.get("A") == "PN_ID":
                if values.get("M") != "neoadjuvant" or values.get("C") != "lpWGS":
                    raise ValueError("Clinical treatment/genomic header changed")
                header_checked = True
            donor = values.get("A", "")
            if not re.fullmatch(r"PN\d+", donor):
                continue
            if (
                donor in result
                or values.get("M") not in ("0", "1")
                or values.get("C") not in ("0", "1")
            ):
                raise ValueError(
                    "Duplicate donor or unresolved treatment/genomic validation"
                )
            result[donor] = dict(neoadjuvant=int(values["M"]), lpWGS=int(values["C"]))
    if not header_checked or len(result) != 21:
        raise ValueError("Expected original21-donor clinical inventory")
    return result


def partition(geo, clinical, clinical_sha256):
    samples = []
    for chunk in geo.split("^SAMPLE = ")[1:]:
        gsm = chunk.splitlines()[0].strip()
        title = re.search(r"!Sample_title = (.*)", chunk)
        match = re.search(r"\[(PN\d+)\]", title.group(1)) if title else None
        if not match or not re.fullmatch(r"GSM\d+", gsm):
            raise ValueError("Unexpected original sample identity")
        pn = match.group(1)
        urls = [
            u.replace("ftp://", "https://").strip()
            for u in re.findall(r"!Sample_supplementary_file_\d+ = (.*)", chunk)
        ]
        expected_name = f"{gsm}_{pn}_filtered_feature_bc_matrix.h5"
        if (
            len(urls) != 1
            or not urls[0].startswith("https://ftp.ncbi.nlm.nih.gov/geo/samples/")
            or urls[0].rsplit("/", 1)[-1] != expected_name
        ):
            raise ValueError("Original donor count file mismatch")
        samples.append(
            dict(sample=gsm, donor="GSE253429:" + pn, **clinical[pn], files=urls)
        )
    samples.sort(key=lambda s: s["sample"])
    if (
        len(samples) != 21
        or len({s["donor"] for s in samples}) != 21
        or len({s["sample"] for s in samples}) != 21
    ):
        raise ValueError("Repeated or missing original donor")
    for i, sample in enumerate(samples):
        sample["role"] = "train" if i % 2 == 0 else "development-validation"
    return dict(
        schema="ecosystem-cna-development-partition-v1",
        samples=samples,
        selection_rule="Ascending original GSM identifiers alternate TRAIN (even zero-based index) and development-validation; frozen before original counts/annotations",
        population="CUIMC primary PDAC selected by subsequent liver/lung recurrence; treatment is recorded, not pooled as untreated confirmation",
        private_confirmation=False,
        clinical_sha256=clinical_sha256,
    )


def freeze(root):
    import requests

    root = Path(root)
    audit = root / "audit"
    audit.mkdir(parents=True, exist_ok=True)
    for name, url in [("GSE253429-full.txt", GEO), ("clinical-source.xlsx", CLINICAL)]:
        path = audit / name
        if not path.exists():
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            path.write_bytes(r.content)
    clinical = audit / "clinical-source.xlsx"
    result = partition(
        (audit / "GSE253429-full.txt").read_text(),
        clinical_mapping(clinical.read_bytes()),
        digest(clinical),
    )
    path = audit / "partition.json"
    if path.exists() and json.loads(path.read_text()) != result:
        raise ValueError("Frozen development partition changed")
    if not path.exists():
        path.write_text(json.dumps(result, indent=2) + "\n")
    return result


class GeoRangeReader(io.RawIOBase):
    """Seek public GEO ZIPs without downloading unrelated multi-GB members."""

    def __init__(self, url):
        if url != ARCHIVE:
            raise ValueError("Only the audited public annotation archive is allowed")
        self.url, self.pos = url, 0
        self.size = None
        self._range(0, 1)

    def seekable(self):
        return True

    def seek(self, offset, whence=0):
        if whence not in (0, 1, 2):
            raise ValueError("Invalid seek origin")
        value = (
            offset
            if whence == 0
            else self.pos + offset
            if whence == 1
            else self.size + offset
        )
        if value < 0:
            raise ValueError("Negative seek")
        self.pos = value
        return self.pos

    def tell(self):
        return self.pos

    def _range(self, start, size):
        import requests

        with requests.get(
            self.url,
            headers={"Range": f"bytes={start}-{start + size - 1}"},
            stream=True,
            timeout=(30, 60),
        ) as r:
            r.raise_for_status()
            match = re.fullmatch(
                r"bytes (\d+)-(\d+)/(\d+)", r.headers.get("Content-Range", "")
            )
            if (
                r.status_code != 206
                or not match
                or tuple(map(int, match.groups()[:2])) != (start, start + size - 1)
            ):
                raise ValueError("Original ZIP server returned wrong byte range")
            total = int(match.group(3))
            if self.size is not None and self.size != total:
                raise ValueError("Original ZIP size changed")
            self.size = total
            data = bytearray()
            for block in r.iter_content(1024**2):
                data.extend(block)
                if len(data) > size:
                    raise ValueError("Original ZIP range exceeds declared length")
            if len(data) != size:
                raise ValueError("Truncated original ZIP range")
            return bytes(data)

    def read(self, size=-1):
        size = min(size if size >= 0 else self.size - self.pos, self.size - self.pos)
        if size <= 0:
            return b""
        if size > 32 * 1024**2:
            raise ValueError("Bounded reads required")
        data = self._range(self.pos, size)
        self.pos += size
        return data


def acquire(root):
    import requests

    root = Path(root)
    frozen = freeze(root)
    raw = root / "raw"
    raw.mkdir(exist_ok=True)
    records = []
    # Download all original count matrices; no outcome-based inclusion.
    for sample in frozen["samples"]:
        url = sample["files"][0]
        path = raw / url.rsplit("/", 1)[-1]
        if not path.exists():
            partial = path.with_suffix(path.suffix + ".part")
            with requests.get(url, stream=True, timeout=(30, 60)) as r:
                r.raise_for_status()
                with partial.open("wb") as f:
                    for block in r.iter_content(1024**2):
                        f.write(block)
                        if f.tell() > 256 * 1024**2:
                            raise ValueError("Original count file exceeds source cap")
            partial.replace(path)
        records.append(
            dict(
                url=url, file=path.name, bytes=path.stat().st_size, sha256=digest(path)
            )
        )
        print("verified count", sample["sample"], flush=True)
    with zipfile.ZipFile(GeoRangeReader(ARCHIVE)) as z:
        for name in MEMBERS:
            info = z.getinfo(name)
            path = raw / Path(name).name
            if info.file_size > 2 * 1024**3:
                raise ValueError("Annotation exceeds audited memory/disk cap")
            if not path.exists():
                partial = path.with_suffix(".RData.part")
                with z.open(info) as src, partial.open("wb") as dst:
                    while block := src.read(8 * 1024**2):
                        dst.write(block)
                partial.replace(path)  # ZipExtFile checks CRC before publication.
            records.append(
                dict(
                    url=ARCHIVE,
                    member=name,
                    file=path.name,
                    bytes=path.stat().st_size,
                    sha256=digest(path),
                    crc32=info.CRC,
                )
            )
            print("verified annotation", name, flush=True)
    path = root / "audit/acquisition.json"
    if path.exists() and json.loads(path.read_text()) != records:
        raise ValueError("Original acquired source bytes changed")
    path.write_text(json.dumps(records, indent=2) + "\n")
    return dict(
        donors=len(frozen["samples"]),
        files=len(records),
        bytes=sum(r["bytes"] for r in records),
    )


def extract_annotations(root):
    """Read author metadata as R data; never execute serialized code or fit on CPU."""
    import gc
    import rdata

    root = Path(root)
    expected = {
        r["file"]: r for r in json.loads((root / "audit/acquisition.json").read_text())
    }
    reports = []
    for member in MEMBERS:
        name = Path(member).name
        source = root / "raw" / name
        if digest(source) != expected[name]["sha256"]:
            raise ValueError("Author annotation source changed")
        parsed = rdata.parser.parse_file(source)
        obj = parsed.object.value[0]
        a = obj.attributes
        metadata = None
        while a is not None and a.value is not None:
            if rdata.conversion.convert(a.tag) == "meta.data":
                metadata = rdata.conversion.convert(a.value[0])
                break
            a = a.value[1]
        if metadata is None:
            raise ValueError("Author metadata slot missing")
        required = [
            "orig.ident",
            "cell_type",
            "histology",
            "subcompartment",
            "treatment",
        ]
        if not set(required).issubset(metadata.columns):
            raise ValueError("Author annotation contract changed")
        output = root / "audit" / f"{Path(member).stem}-labels.tsv"
        metadata[required].to_csv(output, sep="\t", index_label="author_cell_id")
        reports.append(
            dict(
                member=member,
                cells=len(metadata),
                cell_types=metadata["cell_type"].astype(str).value_counts().to_dict(),
                sha256=digest(output),
                source_sha256=digest(source),
            )
        )
        print("extracted annotations", member, len(metadata), flush=True)
        del parsed, obj, a, metadata
        gc.collect()
    (root / "audit/annotations.json").write_text(json.dumps(reports, indent=2) + "\n")
    return reports


def prepare(root, panel, *, allow_missing_author_cells=False):
    import csv
    import h5py
    import numpy as np
    from scipy import sparse
    from .ecosystem_expansion import align, save_pack

    root = Path(root)
    panel = Path(panel)
    genes = json.loads(panel.read_text())["genes"]
    frozen = freeze(root)
    donors = {s["donor"].split(":")[1]: s for s in frozen["samples"]}
    acquisition = {
        r["file"]: r for r in json.loads((root / "audit/acquisition.json").read_text())
    }
    annotations = json.loads((root / "audit/annotations.json").read_text())
    labels = {}
    for report in annotations:
        name = Path(report["member"]).stem
        path = root / "audit" / f"{name}-labels.tsv"
        if digest(path) != report["sha256"]:
            raise ValueError("Extracted author labels changed")
        with path.open() as f:
            for row in csv.DictReader(f, delimiter="\t"):
                donor = row["orig.ident"]
                barcode = row["author_cell_id"].split("_")[0]
                key = (donor, barcode)
                if donor not in donors or key in labels:
                    raise ValueError(
                        "Unknown donor or overlapping compartment annotation"
                    )
                if row["treatment"] != (
                    "treated" if donors[donor]["neoadjuvant"] else "untreated"
                ):
                    raise ValueError("Clinical/author treatment mismatch")
                labels[key] = dict(row, compartment=name)
    output = root / "prepared"
    output.mkdir(exist_ok=True)
    reports = []
    matched = set()
    for sample in frozen["samples"]:
        source = root / "raw" / Path(sample["files"][0]).name
        if digest(source) != acquisition[source.name]["sha256"]:
            raise ValueError("Original count source changed")
        with h5py.File(source) as f:
            m = f["matrix"]
            counts = sparse.csc_matrix(
                (m["data"][:], m["indices"][:], m["indptr"][:]),
                shape=tuple(m["shape"][:]),
            ).T.tocsr()
            measured = [v.decode() for v in m["features/name"][:]]
            barcodes = [v.decode() for v in m["barcodes"][:]]
        if set(genes) - set(measured):
            raise ValueError("Frozen genes unmeasured; no imputation permitted")
        totals = np.asarray(counts.sum(1)).ravel()
        pn = sample["donor"].split(":")[1]
        keep = []
        cells = []
        for i, barcode in enumerate(barcodes):
            key = (pn, barcode)
            if key not in labels:
                continue
            if key in matched or totals[i] <= 0:
                raise ValueError("Repeated/zero-count annotated cell")
            matched.add(key)
            label = labels[key]
            keep.append(i)
            compartment = label["compartment"]
            cells.append(
                dict(
                    cell_id=sample["sample"] + ":" + barcode,
                    donor=sample["donor"],
                    study="GSE253429",
                    role="train" if sample["role"] == "train" else "validation",
                    label={"cancer": 0, "CAF": 1, "exocrine": 4}[compartment],
                    label_source="author-CNV-supported-compartment",
                    author_cell_type=label["cell_type"],
                    author_histology=label["histology"],
                    neoadjuvant=sample["neoadjuvant"],
                    lpWGS=sample["lpWGS"],
                    library_size=int(totals[i]),
                )
            )
        path = output / (sample["sample"] + ".npz")
        save_pack(
            path,
            align(counts[keep], measured, genes),
            genes,
            cells,
            dict(
                schema="ecosystem-expanded-v1",
                assay="snRNA",
                status="exposed-development",
                partition_sha256=digest(root / "audit/partition.json"),
                original_sources=[digest(source)],
                author_annotations_sha256=digest(root / "audit/annotations.json"),
            ),
        )
        reports.append(
            dict(
                sample=sample["sample"],
                donor=sample["donor"],
                cells=len(cells),
                train=sample["role"] == "train",
                untreated=not bool(sample["neoadjuvant"]),
                sha256=digest(path),
            )
        )
        print("prepared", sample["sample"], len(cells), flush=True)
    if matched != set(labels) and not allow_missing_author_cells:
        raise ValueError(
            f"{len(set(labels) - matched)} author cells missing from original count matrices"
        )
    missing = {}
    for key in set(labels) - matched:
        group = key[0] + ":" + labels[key]["compartment"]
        missing[group] = missing.get(group, 0) + 1
    report = dict(
        missing_author_cells=dict(sorted(missing.items())),
        expected_author_cells=len(labels),
        allow_missing_author_cells=allow_missing_author_cells,
        schema="ecosystem-cna-preparation-v1",
        donors=len(reports),
        cells=len(matched),
        genes=len(genes),
        sources=reports,
        biological_gate_passed=False,
    )
    (root / "audit/preparation.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def train_malignancy(prepared, output, *, epochs=30):
    """CUDA diagnostic against author malignant versus normal ductal labels."""
    import fcntl
    import time
    import torch
    from .ecosystem_cuda import load_packs, require_cuda, save_weights

    require_cuda()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    protocol = dict(
        seed=9401,
        epochs=epochs,
        learning_rate=0.001,
        weight_decay=0.01,
        target="author-CNV-supported malignant versus author ductal/ductal-like",
        population="untreated CUIMC recurrence-selected development donors",
        selection="fixed final epoch; no validation-selected checkpoint",
        biological_gate_passed=False,
    )
    (output / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    with open("/tmp/dnhacks-gpu.lock", "a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        counts, totals, logged, roles, labels, metadata, genes, hashes = load_packs(
            prepared
        )
        del counts, totals
        torch.manual_seed(protocol["seed"])
        eligible = torch.tensor(
            [
                not c["neoadjuvant"]
                and (c["label"] == 0 or c["author_cell_type"] == "ductal/ductal-like")
                for c in metadata
            ],
            device="cuda",
        )
        target = (labels == 0).long()
        masks = {role: mask & eligible for role, mask in roles.items()}
        donor_roles = {}
        for cell in metadata:
            donor_roles.setdefault(cell["donor"], set()).add(cell["role"])
        if any(len(r) != 1 for r in donor_roles.values()):
            raise ValueError("Donor crosses training and validation roles")
        train = torch.where(masks["train"])[0]
        validation = torch.where(masks["validation"])[0]
        if len(train) == 0 or len(validation) == 0:
            raise ValueError(
                "Independent untreated training and validation donors required"
            )
        groups = {}
        for i in train.cpu().tolist():
            key = (metadata[i]["donor"], metadata[i]["label"] == 0)
            groups.setdefault(key, []).append(i)
        weights = torch.zeros(len(metadata), device="cuda")
        for rows in groups.values():
            weights[torch.tensor(rows, device="cuda")] = 1 / len(rows)
        model = torch.nn.Sequential(
            torch.nn.Linear(len(genes), 128),
            torch.nn.LayerNorm(128),
            torch.nn.SiLU(),
            torch.nn.Dropout(0.2),
            torch.nn.Linear(128, 2),
        ).cuda()
        optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.01)
        curves = []
        started = time.monotonic()
        for epoch in range(epochs):
            model.train()
            total_loss = 0.0
            order = torch.multinomial(weights, len(train), replacement=True)
            for batch in order.split(512):
                loss = torch.nn.functional.cross_entropy(
                    model(logged[batch]), target[batch]
                )
                if not torch.isfinite(loss):
                    raise ValueError("Nonfinite malignancy loss")
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total_loss += float(loss.detach()) * len(batch)
            model.eval()
            with torch.no_grad():
                pred = model(logged[validation])
                loss = float(
                    torch.nn.functional.cross_entropy(pred, target[validation])
                )
            curves.append(
                dict(
                    epoch=epoch + 1,
                    training_loss=total_loss / len(train),
                    validation_loss=loss,
                    seconds=time.monotonic() - started,
                )
            )
            if epoch % 5 == 0 or epoch == epochs - 1:
                print("malignancy", curves[-1], flush=True)
        with torch.no_grad():
            scores = torch.cat([model(x).softmax(1)[:, 1] for x in logged.split(1024)])
        donor_reports = []
        for donor in sorted({c["donor"] for c in metadata}):
            ix = torch.tensor(
                [
                    i
                    for i, c in enumerate(metadata)
                    if c["donor"] == donor
                    and not c["neoadjuvant"]
                    and (
                        c["label"] == 0 or c["author_cell_type"] == "ductal/ductal-like"
                    )
                ],
                device="cuda",
                dtype=torch.long,
            )
            if len(ix) == 0:
                continue
            positive = target[ix] == 1
            negative = ~positive
            donor_reports.append(
                dict(
                    donor=donor,
                    role=metadata[int(ix[0])]["role"],
                    malignant_cells=int(positive.sum()),
                    normal_ductal_cells=int(negative.sum()),
                    sensitivity_at_08=float(
                        (scores[ix][positive] >= 0.8).float().mean()
                    )
                    if positive.any()
                    else None,
                    false_positive_rate_at_08=float(
                        (scores[ix][negative] >= 0.8).float().mean()
                    )
                    if negative.any()
                    else None,
                    accuracy_at_05=float(
                        ((scores[ix] >= 0.5) == positive).float().mean()
                    ),
                )
            )
        report = dict(
            protocol=protocol,
            curves=curves,
            donors=donor_reports,
            source_packs=hashes,
            genes=len(genes),
            device=torch.cuda.get_device_name(),
            peak_vram_bytes=torch.cuda.max_memory_allocated(),
            biological_gate_passed=False,
        )
        save_weights(output / "malignancy.npz", {"classifier": model}, report)
        (output / "report.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n"
        )
        return report


def evaluate_existing_critic(training_views, new_views, weights, output):
    """Score new author-defined compartments without refitting any critic state.

    Existing growth weights were fit after load_views' TRAIN normalization and a
    second fitter normalization. Reproduce both using original TRAIN views only.
    """
    import fcntl
    import numpy as np
    import torch
    from .ecosystem_cuda import require_cuda
    from .ecosystem_power import projection
    from .ecosystem_power_training import growth, study_pairs

    require_cuda()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)

    def read(root):
        packs = []
        for name in ("epithelial-enriched", "fibroblast"):
            path = Path(root) / (name + "-donor-summaries.npz")
            with np.load(path, allow_pickle=False) as z:
                packs.append({k: z[k].copy() for k in z.files})
        shared = sorted(set(packs[0]["donors"]) & set(packs[1]["donors"]))
        values = []
        roles = None
        studies = None
        for p in packs:
            if len(set(p["donors"])) != len(p["donors"]):
                raise ValueError("Repeated donor summary")
            ix = [p["donors"].tolist().index(d) for d in shared]
            r = p["roles"][ix].tolist()
            s = p["studies"][ix].tolist()
            if roles is not None and (roles != r or studies != s):
                raise ValueError("Compartment role mismatch")
            roles, studies = r, s
            values.append(torch.as_tensor(p["values"][ix], device="cuda"))
        return values, roles, studies, shared

    with open("/tmp/dnhacks-gpu.lock", "a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        train_values, train_roles, _, train_donors = read(training_views)
        values, roles, studies, donors = read(new_views)
        if set(train_donors) & set(donors):
            raise ValueError("New evaluation donor overlaps original source")
        train = torch.tensor(
            [i for i, r in enumerate(train_roles) if r == "train"], device="cuda"
        )
        if len(train) < 2:
            raise ValueError("Original TRAIN normalization requires donors")
        with np.load(weights, allow_pickle=False) as z:
            state = {
                k: torch.as_tensor(z[k], device="cuda")
                for k in z.files
                if k != "manifest"
            }
        critic = frozen_critic_scores(train_values, train, values, state)
        results = {}
        for study in sorted(set(studies)):
            ix = [
                i for i, r in enumerate(roles) if r != "train" and studies[i] == study
            ]
            if len(ix) < 3:
                continue
            matrix = critic[
                torch.tensor(ix, device="cuda")[:, None],
                torch.tensor(ix, device="cuda")[None, :],
            ]
            report = dict(
                observed_donors=len(ix),
                distinct_pair_log_growth=float(
                    growth(critic, study_pairs(ix, studies))
                ),
                projections=[],
            )
            for n in (18, 24, 40, 60, 100):
                for null in (False, True):
                    report["projections"].append(
                        dict(
                            simulated_donors=n,
                            scenario="product-null" if null else "empirical-joint",
                            **projection(
                                matrix, n, streams=10000, seed=9403, null=null
                            ),
                        )
                    )
            results[study] = report
        report = dict(
            schema="ecosystem-cna-frozen-critic-v1",
            status="development-only",
            biological_gate_passed=False,
            original_weight_sha256=digest(weights),
            normalization="original TRAIN load_views normalization followed by frozen fitter normalization; no new-data fitting",
            original_training_views=[
                dict(file=name, sha256=digest(Path(training_views) / name))
                for name in (
                    "epithelial-enriched-donor-summaries.npz",
                    "fibroblast-donor-summaries.npz",
                )
            ],
            results=results,
        )
        (output / "report.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n"
        )
        return report


def frozen_critic_scores(training_values, train, values, state):
    """Apply both recorded training normalizations without fitting on new views."""
    import torch

    normalized = []
    for prefix, old, new in zip(("x", "y"), training_values, values):
        if old.shape[1] != new.shape[1]:
            raise ValueError("Frozen feature dimension mismatch")
        base = (new - old[train].mean(0)) / old[train].std(0).clamp_min(0.1)
        normalized.append((base - state[prefix + "_mean"]) / state[prefix + "_scale"])
    left = torch.nn.functional.linear(
        normalized[0], state["left.0.weight"], state["left.0.bias"]
    ).tanh()
    right = torch.nn.functional.linear(
        normalized[1], state["right.0.weight"], state["right.0.bias"]
    ).tanh()
    return torch.tanh((left * state["weight"]) @ right.T + state["offset"])
