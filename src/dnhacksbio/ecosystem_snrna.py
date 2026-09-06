"""Original snRNA preparation and CUDA-only frozen transfer diagnostics."""

from __future__ import annotations

import fcntl
import hashlib
import json
from pathlib import Path

import numpy as np

# Same predefined programs as the original ecosystem_data.PROGRAMS, represented
# by their individual measured genes rather than a tuned weighted pathway score.
PROGRAM_GENES = {
    "epithelial-enriched": [
        "DDIT3",
        "HSPA5",
        "ATF4",
        "XBP1",
        "SLC1A5",
        "SLC38A2",
        "SLC7A5",
        "SLC16A1",
        "B2M",
        "HLA-A",
        "HLA-B",
        "HLA-C",
        "TAP1",
    ],
    "fibroblast": [
        "ACTA2",
        "TAGLN",
        "MYL9",
        "COL1A1",
        "COL1A2",
        "CXCL12",
        "IL6",
        "CXCL14",
        "CFD",
        "DPT",
        "CD74",
        "HLA-DRA",
        "HLA-DPA1",
        "HLA-DPB1",
        "SLC16A1",
        "LDHA",
        "SLC38A2",
        "GOT1",
        "PSAT1",
    ],
}


def partition_from_geo(text):
    import re

    samples = []
    for chunk in text.split("^SAMPLE = ")[1:]:
        sample = chunk.splitlines()[0].strip()
        title_match = re.search(r"!Sample_title = (.*)", chunk)
        if title_match is None:
            raise ValueError("Missing original snRNA population title")
        title = title_match.group(1).strip()
        match = re.fullmatch(r"PDAC Tumor Sample PDAC(\d+)", title)
        characteristics = [
            v.strip() for v in re.findall(r"!Sample_characteristics_ch1 = (.*)", chunk)
        ]
        if (
            not match
            or "treatment: treatment-naive" not in characteristics
            or "tissue: Pancreas (tumor)" not in characteristics
        ):
            raise ValueError("Unexpected original snRNA population metadata")
        number = int(match.group(1))
        files = [
            u.strip().replace("ftp://", "https://")
            for u in re.findall(r"!Sample_supplementary_file_\d+ = (.*)", chunk)
        ]
        if len(files) != 3 or any(
            not u.startswith("https://ftp.ncbi.nlm.nih.gov/geo/samples/") for u in files
        ):
            raise ValueError("Three original GEO count files required")
        samples.append(
            dict(
                sample=sample,
                donor=f"GSE291124:PDAC{number}",
                role="train" if number <= 9 else "development-validation",
                files=files,
            )
        )
    if (
        len(samples) != 17
        or {s["donor"] for s in samples} != {f"GSE291124:PDAC{i}" for i in range(1, 18)}
        or len({s["sample"] for s in samples}) != 17
    ):
        raise ValueError("Original17-donor source identity inventory changed")
    return dict(
        schema="ecosystem-snRNA-development-partition-v1",
        purpose="untreated primary-PDAC assay-transfer development; not private confirmation",
        samples=samples,
        selection_rule="Original donor numbers1-9 training,10-17 development-validation; frozen before counts",
        reserved_Hwang_opened=False,
    )


def acquire(root):
    """Acquire only this public source after freezing its donor roles."""
    import concurrent.futures
    import time
    import requests
    from .ecosystem_data import sha256

    root = Path(root) / "power"
    audit = root / "audit"
    audit.mkdir(parents=True, exist_ok=True)
    source = audit / "GSE291124-full.txt"
    if not source.exists():
        r = requests.get(
            "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE291124&targ=all&form=text&view=full",
            timeout=60,
        )
        r.raise_for_status()
        source.write_text(r.text)
    partition = partition_from_geo(source.read_text())
    path = audit / "snRNA-partition.json"
    if path.exists() and json.loads(path.read_text()) != partition:
        raise ValueError("Frozen source partition differs")
    if not path.exists():
        path.write_text(json.dumps(partition, indent=2) + "\n")
    record_path = audit / "snRNA-acquisition.json"
    expected = (
        {r["file"]: r for r in json.loads(record_path.read_text())}
        if record_path.exists()
        else {}
    )

    def download(url):
        path = root / "raw/GSE291124" / url.rsplit("/", 1)[1]
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            partial = Path(str(path) + ".part")
            for attempt in range(6):
                try:
                    offset = partial.stat().st_size if partial.exists() else 0
                    with requests.get(
                        url,
                        headers={"Range": f"bytes={offset}-"} if offset else {},
                        stream=True,
                        timeout=(30, 60),
                    ) as response:
                        response.raise_for_status()
                        if offset and (
                            response.status_code != 206
                            or not response.headers.get("Content-Range", "").startswith(
                                f"bytes {offset}-"
                            )
                        ):
                            raise ValueError("Invalid original count resume response")
                        with partial.open("ab" if offset else "wb") as f:
                            for chunk in response.iter_content(1024**2):
                                f.write(chunk)
                                if f.tell() > 2 * 1024**3:
                                    raise ValueError("Original source exceeds2GiB cap")
                    partial.replace(path)
                    break
                except requests.RequestException:
                    if attempt == 5:
                        raise
                    time.sleep(3)
        name = str(path.relative_to(root))
        result = dict(
            url=url, file=name, bytes=path.stat().st_size, sha256=sha256(path)
        )
        if name in expected and result != expected[name]:
            raise ValueError("Acquired source differs from recorded bytes")
        return result

    urls = [u for s in partition["samples"] for u in s["files"]]
    with concurrent.futures.ThreadPoolExecutor(3) as pool:
        records = list(pool.map(download, urls))
    record_path.write_text(json.dumps(records, indent=2) + "\n")
    return dict(
        donors=17,
        files=len(records),
        bytes=sum(r["bytes"] for r in records),
        metadata_sha256=sha256(source),
    )


def prepare(root):
    from .ecosystem_data import sha256
    from .ecosystem_expansion import align, read_10x, save_pack

    root = Path(root)
    power = root / "power"
    partition = json.loads((power / "audit/snRNA-partition.json").read_text())
    acquisition = {
        r["file"]: r
        for r in json.loads((power / "audit/snRNA-acquisition.json").read_text())
    }
    genes = json.loads((root / "expansion/audit/panel.json").read_text())["genes"]
    output = power / "prepared-snrna"
    output.mkdir(parents=True, exist_ok=True)
    seen, sources = set(), []
    for sample in partition["samples"]:
        donor = sample["donor"]
        if donor in seen:
            raise ValueError("Duplicate canonical snRNA donor")
        seen.add(donor)
        paths = [
            power / "raw/GSE291124" / url.rsplit("/", 1)[1] for url in sample["files"]
        ]
        for path in paths:
            expected = acquisition[str(path.relative_to(power))]
            if (
                path.stat().st_size != expected["bytes"]
                or sha256(path) != expected["sha256"]
            ):
                raise ValueError("Original snRNA source changed")
        counts, measured, barcodes = read_10x(paths)
        if set(genes) - set(measured):
            raise ValueError(
                "Frozen panel has unmeasured snRNA genes; do not zero-impute"
            )
        totals = np.asarray(counts.sum(1)).ravel()
        keep = np.flatnonzero(totals > 0)
        if sample["role"] not in ("train", "development-validation"):
            raise ValueError("Unexpected frozen snRNA role")
        role = "train" if sample["role"] == "train" else "validation"
        cells = [
            dict(
                cell_id=sample["sample"] + ":" + barcodes[i],
                donor=donor,
                study="GSE291124",
                role=role,
                label=-1,
                label_source="unlabeled-snRNA-frozen-transfer",
                library_size=int(totals[i]),
            )
            for i in keep
        ]
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
                partition_sha256=sha256(power / "audit/snRNA-partition.json"),
                original_sources=[
                    acquisition[str(p.relative_to(power))]["sha256"] for p in paths
                ],
            ),
        )
        sources.append(
            dict(file=path.name, role=role, cells=len(cells), sha256=sha256(path))
        )
        print(sample["sample"], role, len(cells), flush=True)
    report = dict(
        schema="ecosystem-snrna-preparation-v1",
        donors=len(seen),
        cells=sum(s["cells"] for s in sources),
        genes=len(genes),
        sources=sources,
        biological_gate_passed=False,
    )
    (power / "audit/snRNA-preparation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    return report


def fixed_bag_summary(z, assigned, metadata, compartment, cells_per_compartment=32):
    """One deterministic fixed-size bag per donor; cells never become donors."""
    import torch

    groups = {}
    if len(metadata) != len(z) or len(assigned) != len(z):
        raise ValueError("Embedding metadata shape mismatch")
    for i, label in enumerate(assigned.detach().cpu().tolist()):
        if label == compartment:
            groups.setdefault(metadata[i]["donor"], []).append(i)
    rows, donors, roles, studies = [], [], [], []
    for donor, indices in sorted(groups.items()):
        indices = sorted(indices, key=lambda i: metadata[i]["cell_id"])
        if len({metadata[i]["cell_id"] for i in indices}) != len(indices):
            raise ValueError("Repeated cells within a donor")
        if len({(metadata[i]["role"], metadata[i]["study"]) for i in indices}) != 1:
            raise ValueError("Donor crosses roles or source studies")
        if len(indices) < cells_per_compartment:
            continue
        seed = int(
            hashlib.sha256(f"fixed32-v1:{compartment}:{donor}".encode()).hexdigest()[
                :16
            ],
            16,
        )
        # CPU chooses indices only; embeddings and summary calculations stay CUDA.
        chosen = np.random.default_rng(seed).choice(
            indices, cells_per_compartment, replace=False
        )
        v = z[torch.as_tensor(chosen, device=z.device)]
        rows.append(torch.cat([v.mean(0), v.var(0, unbiased=False)]))
        donors.append(donor)
        roles.append(metadata[indices[0]]["role"])
        studies.append(metadata[indices[0]]["study"])
    values = (
        torch.stack(rows) if rows else torch.empty((0, z.shape[1] * 2), device=z.device)
    )
    return values, donors, roles, studies


def combine_summaries(left, right, output):
    """Join original disjoint donor records, without fitting or adding replicas."""
    output = Path(output)
    prepared = {}
    for name in ("epithelial-enriched", "fibroblast"):
        parts = []
        for root in (left, right):
            with np.load(
                Path(root) / f"{name}-donor-summaries.npz", allow_pickle=False
            ) as z:
                parts.append({k: z[k].copy() for k in z.files})
        if set(parts[0]["donors"]) & set(parts[1]["donors"]):
            raise ValueError("Repeated canonical donor between cohorts")
        if parts[0]["values"].shape[1] != parts[1]["values"].shape[1]:
            raise ValueError("Compartment summary dimensions differ")
        if "genes" in parts[0] or "genes" in parts[1]:
            if not np.array_equal(parts[0].get("genes"), parts[1].get("genes")):
                raise ValueError("Compartment feature order differs")
        prepared[name] = {
            k: np.concatenate([p[k] for p in parts])
            for k in ("values", "donors", "roles", "studies")
        }
    output.mkdir(parents=True, exist_ok=True)
    for name, arrays in prepared.items():
        np.savez_compressed(output / f"{name}-donor-summaries.npz", **arrays)
    return len(
        set(prepared["epithelial-enriched"]["donors"])
        & set(prepared["fibroblast"]["donors"])
    )


def evaluate(prepared, models, output):
    import torch
    from .ecosystem_cuda import (
        require_cuda,
        load_packs,
        build_autoencoder,
    )

    require_cuda()
    output, models = Path(output), Path(models)
    output.mkdir(parents=True, exist_ok=True)
    with Path("/tmp/dnhacks-gpu.lock").open("a+") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        torch.set_num_threads(2)
        counts, totals, logged, roles, labels, metadata, genes, hashes = load_packs(
            prepared
        )
        classifier = torch.nn.Sequential(
            torch.nn.Linear(len(genes), 128),
            torch.nn.LayerNorm(128),
            torch.nn.SiLU(),
            torch.nn.Dropout(0.2),
            torch.nn.Linear(128, 5),
        ).cuda()
        with np.load(models / "lineage.npz", allow_pickle=False) as z:
            classifier.load_state_dict(
                {
                    k: torch.from_numpy(z["classifier." + k]).cuda()
                    for k in classifier.state_dict()
                }
            )
        classifier.eval()
        with torch.no_grad():
            confidence, predicted = torch.cat(
                [classifier(x).softmax(1) for x in logged.split(512)]
            ).max(1)
        assigned = torch.where(
            labels >= 0,
            labels,
            torch.where(confidence >= 0.8, predicted, torch.full_like(predicted, -1)),
        )
        # Predefined marker checks are diagnostics, never relabeling to improve
        # a held-out association. Neither expression outcomes nor model scores
        # determine the already frozen donor partition.
        panels = dict(
            epithelial=["EPCAM", "KRT8", "KRT18", "KRT19"],
            fibroblast=["COL1A1", "COL1A2", "DCN", "LUM"],
            immune=["PTPRC", "CD3D", "LYZ"],
            endothelial=["PECAM1", "VWF", "KDR"],
        )
        marker = {
            k: logged[:, [genes.index(g) for g in gs if g in genes]].mean(1)
            for k, gs in panels.items()
        }
        marker_class = torch.stack(list(marker.values()), 1).argmax(1)
        report = dict(
            schema="ecosystem-snrna-transfer-v1",
            status="frozen-exposed-development",
            biological_gate_passed=False,
            device=torch.cuda.get_device_name(),
            input_hashes=hashes,
            donors=len({c["donor"] for c in metadata}),
            cells=len(metadata),
            unassigned_cells=int((assigned < 0).sum()),
            compartments={},
            marker_diagnostic={},
            marker_panel={k: [g for g in gs if g in genes] for k, gs in panels.items()},
            measurement="one deterministic32-cell bag per compartment; seed derived from donor and compartment",
        )
        for label, name in enumerate(panels):
            mask = assigned == label
            report["marker_diagnostic"][name] = dict(
                assigned_cells=int(mask.sum()),
                top_marker_agreement=float((marker_class[mask] == label).float().mean())
                if mask.any()
                else None,
            )
        coverage = {}
        program_output = output / "programs"
        program_output.mkdir(exist_ok=True)
        report["program_genes"] = PROGRAM_GENES
        for comp, name in [(0, "epithelial-enriched"), (1, "fibroblast")]:
            if set(PROGRAM_GENES[name]) - set(genes):
                raise ValueError("Predefined program has unmeasured genes")
            program_values, pd, pr, ps = fixed_bag_summary(
                logged[:, [genes.index(g) for g in PROGRAM_GENES[name]]],
                assigned,
                metadata,
                comp,
            )
            np.savez_compressed(
                program_output / f"{name}-donor-summaries.npz",
                values=program_values.cpu().numpy(),
                donors=np.asarray(pd),
                roles=np.asarray(pr),
                studies=np.asarray(ps),
                genes=np.asarray(PROGRAM_GENES[name]),
            )
            encoder, decoder = build_autoencoder(len(genes))
            with np.load(models / name / "dae-2701.npz", allow_pickle=False) as z:
                encoder.load_state_dict(
                    {
                        k: torch.from_numpy(z["encoder." + k]).cuda()
                        for k in encoder.state_dict()
                    }
                )
                decoder.load_state_dict(
                    {
                        k: torch.from_numpy(z["decoder." + k]).cuda()
                        for k in decoder.state_dict()
                    }
                )
            encoder.eval()
            decoder.eval()
            with torch.no_grad():
                z = torch.cat([encoder(x) for x in logged.split(512)])
                metrics = {}
                for role, role_mask in roles.items():
                    ix = torch.where(role_mask & (assigned == comp))[0]
                    error = sum(
                        float((decoder(z[b]) - logged[b]).square().sum())
                        for b in ix.split(512)
                    )
                    metrics[role] = dict(
                        cells=len(ix),
                        log_library_mse=error / (len(ix) * len(genes))
                        if len(ix)
                        else None,
                    )
            values, donors, donor_roles, studies = fixed_bag_summary(
                z, assigned, metadata, comp
            )
            np.savez_compressed(
                output / f"{name}-donor-summaries.npz",
                values=values.cpu().numpy(),
                donors=np.asarray(donors),
                roles=np.asarray(donor_roles),
                studies=np.asarray(studies),
            )
            coverage[name] = set(donors)
            report["compartments"][name] = dict(
                metrics=metrics, complete_donors=len(donors)
            )
        report["complete_paired_donors"] = len(set.intersection(*coverage.values()))
        report["peak_allocated_bytes"] = torch.cuda.max_memory_allocated()
        (output / "report.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n"
        )
        print(json.dumps(report, indent=2), flush=True)
        return report
