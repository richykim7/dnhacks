#!/usr/bin/env python3
"""Reproducible GSE212041 day-zero training and standalone DAVT evaluation.

Raw data and donor-level replay stay in ignored data/processed. Public summaries
contain aggregate diagnostics only. No classifier or biological verdict is made.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import gzip
import hashlib
import json
import math
from pathlib import Path
import time
from urllib.request import urlretrieve

import numpy as np
import pandas as pd
import torch

from dnhacksbio.expr_encoder import FrozenEncoder, fit_autoencoder, fit_pca, unit_keys
from dnhacksbio.learned_evalue import (
    LearnedEConfig,
    SamplingContract,
    learned_two_sample_e,
)
from dnhacksbio.evalues import p_to_e
from evalue_harness import interval

SOURCE = "GSE212041; GEO processed TPM; GRCh38/GENCODE v35; RSEM 1.3.0"
NAMESPACE = "GSE212041:patient"
ASSUMPTIONS = (
    "One D0 sample per donor; distinct donors treated as independent within groups. "
    "Observational recruitment, cell composition and clinical confounding remain; "
    "this tests distribution equality, not a causal effect."
)
URLS = {
    "tpm.txt.gz": "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE212nnn/GSE212041/suppl/GSE212041_Neutrophil_RNAseq_TPM_Matrix.txt.gz",
    "metadata.soft.gz": "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE212nnn/GSE212041/soft/GSE212041_family.soft.gz",
}
SOURCE_SHA256 = {
    "tpm.txt.gz": "2fde22f76fc415a8466272138784773dda29b102b44b29e6a44497f730eec847",
    "metadata.soft.gz": "f023cb02534c15d471807d0c33a926df15fb8284f2fd130edff4fcc749403df1",
}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metadata(path):
    records, row = [], None
    with gzip.open(path, "rt") as f:
        for line in f:
            if line.startswith("^SAMPLE = "):
                row = {}
                records.append(row)
            elif row is not None and line.startswith("!Sample_title = "):
                row["title"] = line.strip().split(" = ", 1)[1]
            elif row is not None and line.startswith("!Sample_characteristics_ch1 = "):
                key, value = line.strip().split(" = ", 1)[1].split(": ", 1)
                row[key] = value
    return records


def split_records(records, seed):
    eligible = [
        r
        for r in records
        if r.get("time point") == "D0"
        and r.get("patient category") in {"COVID+", "COVID- symptomatic"}
    ]
    for r in eligible:
        donor, separator, point = r["title"].partition("_")
        if not separator or point != "D0" or not donor:
            raise ValueError("unexpected day-zero donor title")
    ids = [r["title"].split("_")[0] for r in eligible]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate D0 donors: resolve provenance before proceeding")
    rng = np.random.default_rng(seed)
    splits = dict(train=[], development=[], evaluation=[])
    for label in ("COVID+", "COVID- symptomatic"):
        group = sorted(
            [r for r in eligible if r["patient category"] == label],
            key=lambda r: r["title"],
        )
        order = rng.permutation(len(group))
        n_train, n_dev = int(0.4 * len(group)), int(0.2 * len(group))
        for name, indices in zip(
            splits,
            (
                order[:n_train],
                order[n_train : n_train + n_dev],
                order[n_train + n_dev :],
            ),
        ):
            splits[name].extend(group[i] for i in indices)
    return splits


def prepare(root):
    raw = root / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for name, url in URLS.items():
        if not (raw / name).exists():
            temporary = raw / (name + ".part")
            urlretrieve(url, temporary)
            temporary.replace(raw / name)
        if sha(raw / name) != SOURCE_SHA256[name]:
            raise ValueError(f"{name} differs from the audited source release")
    records = metadata(raw / "metadata.soft.gz")
    splits = split_records(records, 20260905)
    frame = pd.read_csv(
        raw / "tpm.txt.gz", sep="\t", dtype={"Gene.ID": str, "Symbol": str}
    )
    frame = frame.loc[frame["Gene.ID"].str.startswith("ENSG")].copy()
    if frame["Gene.ID"].duplicated().any():
        raise ValueError("duplicate gene identifiers")
    training = frame[[r["title"] for r in splits["train"]]].to_numpy(dtype=float).T
    if not np.isfinite(training).all() or (training < 0).any():
        raise ValueError("invalid source TPM")
    # Predeclared feature budget; ranking uses encoder-training donors only.
    variance = np.log1p(training).var(axis=0)
    selected = np.argsort(-variance, kind="stable")[:19000]
    selected = np.sort(selected)
    frame = frame.iloc[selected]
    manifest = dict(
        schema=1,
        source=SOURCE,
        urls=URLS,
        raw_sha256={n: sha(raw / n) for n in URLS},
        sampling=ASSUMPTIONS,
        unit_namespace=NAMESPACE,
        split_seed=20260905,
        split_rule="stratified 40% train, 20% development, remainder evaluation; floor counts",
        exclusions="all non-D0 draws, all healthy controls, non-human gene IDs",
        features="top 19000 training-only log1p(TPM) variances, stable source-order tie breaking",
        n_genes=len(frame),
        source_samples=len(records),
        splits={},
    )
    for name, rows in splits.items():
        x = frame[[r["title"] for r in rows]].to_numpy(dtype=float).T
        if not np.isfinite(x).all() or (x < 0).any():
            raise ValueError("invalid source TPM")
        target = root / f"{name}.npz"
        np.savez_compressed(
            target,
            X=x,
            genes=frame["Gene.ID"].to_numpy(dtype=str),
            symbols=frame["Symbol"].fillna("").to_numpy(dtype=str),
            units=np.array([r["title"].split("_")[0] for r in rows]),
            labels=np.array([r["patient category"] for r in rows]),
        )
        manifest["splits"][name] = dict(
            n=len(rows),
            groups=dict(Counter(r["patient category"] for r in rows)),
            sha256=sha(target),
        )
    # Frozen before training or inspecting final evaluation outcomes.
    manifest["protocol"] = dict(
        autoencoder=dict(
            hidden=512,
            components=128,
            epochs=100,
            mask_fraction=0.15,
            seed=20260905,
            device="cuda",
            dtype="float32",
        ),
        pca_components=64,
        bettor=dict(
            batch_pairs=4,
            hidden=[64, 64],
            max_epochs=100,
            patience=10,
            lr=0.0005,
            weight_decay=0.01,
        ),
        primary_seed=20260906,
        alpha=0.05,
        scalar="IFIT3",
        permutation_draws=9999,
        null_repetitions=200,
        sensitivity_seeds=list(range(20261000, 20261010)),
    )
    write(root / "manifest.json", manifest)
    print(json.dumps(manifest["splits"]), flush=True)


def load(root, name):
    with np.load(root / f"{name}.npz", allow_pickle=False) as f:
        return {k: f[k].copy() for k in f.files}


def train(root):
    manifest = json.loads((root / "manifest.json").read_text())
    if sha(root / "train.npz") != manifest["splits"]["train"]["sha256"]:
        raise ValueError("training cohort differs from frozen manifest")
    d = load(root, "train")
    torch.set_num_threads(4)
    kw = dict(
        genes=d["genes"],
        units=d["units"],
        source=SOURCE,
        sampling=ASSUMPTIONS,
        unit_namespace=NAMESPACE,
    )
    timing = {}
    for kind in ("pca", "autoencoder"):
        tick = time.perf_counter()
        if kind == "pca":
            encoder = fit_pca(
                d["X"], **kw, components=manifest["protocol"]["pca_components"]
            )
        else:
            encoder = fit_autoencoder(
                d["X"], **kw, **manifest["protocol"]["autoencoder"]
            )
            torch.cuda.synchronize()
        timing[kind] = time.perf_counter() - tick
        encoder.manifest.update(
            input_sha256=sha(root / "train.npz"),
            protocol_sha256=sha(root / "manifest.json"),
        )
        encoder.save(root / f"{kind}.npz")
        print(f"{kind}: {timing[kind]:.2f}s", flush=True)
    write(
        root / "training.json",
        dict(
            seconds=timing,
            artifacts={k: sha(root / f"{k}.npz") for k in timing},
            autoencoder=FrozenEncoder.load(root / "autoencoder.npz").manifest,
        ),
    )


def permutation(a, b, rng, draws):
    """Plus-one pooled-label randomization of squared distance between means.

    Gram-matrix calculation avoids repeated passes through the 19000 genes.
    """
    n, m = len(a), len(b)
    pooled = np.concatenate((a, b))
    pooled = pooled - pooled.mean(0)
    gram = pooled @ pooled.T
    contrast = np.r_[np.full(n, 1 / n), np.full(m, -1 / m)]
    observed = float(contrast @ gram @ contrast)
    count = 0
    for _ in range(draws):
        c = contrast[rng.permutation(n + m)]
        count += float(c @ gram @ c) >= observed - 1e-12 * max(1, abs(observed))
    return (count + 1) / (draws + 1)


def benchmark(root):
    """One warm-up and one timed development comparison per device; no tuning."""
    torch.set_num_threads(1)
    d = load(root, "development")
    x = FrozenEncoder.load(root / "autoencoder.npz").transform(d["X"], genes=d["genes"])
    ia = np.flatnonzero(d["labels"] == "COVID+")[:15]
    ib = np.flatnonzero(d["labels"] == "COVID- symptomatic")
    results = {}
    for device in ("cpu", "cuda", "cpu", "cuda"):
        tick = time.perf_counter()
        r = learned_two_sample_e(
            x[ia],
            x[ib],
            genes=[f"f{i}" for i in range(x.shape[1])],
            unit_a=d["units"][ia],
            unit_b=d["units"][ib],
            sampling=SamplingContract(
                "aggregated",
                "GSE212041 development split",
                "independent D0 donors; timing only",
                NAMESPACE,
            ),
            config=LearnedEConfig(
                batch_pairs=2, max_epochs=100, device=device, seed=20265000
            ),
        )
        if device == "cuda":
            torch.cuda.synchronize()
        results[device] = dict(
            seconds=time.perf_counter() - tick,
            execution=r.metadata["execution"],
            path=r.log_wealth_path,
        )
    results["max_path_difference"] = max(
        abs(a - b) for a, b in zip(results["cpu"]["path"], results["cuda"]["path"])
    )
    write(root / "device-benchmark.json", results)
    print(json.dumps(results), flush=True)


def evaluate(root, device):
    tick = time.perf_counter()
    torch.set_num_threads(1)
    manifest = json.loads((root / "manifest.json").read_text())
    protocol = manifest["protocol"]
    d = load(root, "evaluation")
    train_data = load(root, "train")
    for name in ("train", "development", "evaluation"):
        if sha(root / f"{name}.npz") != manifest["splits"][name]["sha256"]:
            raise ValueError("cohort differs from frozen manifest")
    partitions = [
        set(load(root, name)["units"])
        for name in ("train", "development", "evaluation")
    ]
    if any(a & b for i, a in enumerate(partitions) for b in partitions[i + 1 :]):
        raise ValueError("training/development/evaluation overlap")
    encoders = {
        k: FrozenEncoder.load(root / f"{k}.npz") for k in ("pca", "autoencoder")
    }
    for encoder in encoders.values():
        if encoder.manifest.get("protocol_sha256") != sha(root / "manifest.json"):
            raise ValueError("encoder and frozen protocol differ")
        if encoder.manifest.get("input_sha256") != sha(root / "train.npz"):
            raise ValueError("encoder and training cohort differ")
        if set(encoder.manifest["training_unit_keys"]) != set(
            unit_keys(train_data["units"], NAMESPACE)
        ):
            raise ValueError("encoder training donor manifest differs")
    base = encoders["pca"]
    z = (np.log1p(d["X"]) - base.mean) / base.scale
    scalar = np.flatnonzero(d["symbols"] == protocol["scalar"])
    if len(scalar) != 1:
        raise ValueError("predeclared scalar gene missing or ambiguous")
    features = {k: e.transform(d["X"], genes=d["genes"]) for k, e in encoders.items()}
    features["scalar"] = z[:, scalar]
    contract = SamplingContract("aggregated", SOURCE, ASSUMPTIONS, NAMESPACE)
    cfg = LearnedEConfig(
        **{**protocol["bettor"], "hidden": tuple(protocol["bettor"]["hidden"])},
        device=device,
        pairing="in_order",
    )
    results = dict(
        schema=1,
        diagnostic_only=True,
        source=SOURCE,
        protocol_sha256=sha(root / "manifest.json"),
        protocol=protocol,
        splits=manifest["splits"],
        artifacts={k: e.identity for k, e in encoders.items()},
        primary={},
        sensitivity=[],
        orientation_null={},
        device=device,
    )
    a_idx = np.flatnonzero(d["labels"] == "COVID+")
    b_idx = np.flatnonzero(d["labels"] == "COVID- symptomatic")
    seeds = [protocol["primary_seed"], *protocol["sensitivity_seeds"]]
    replay = []
    for i, seed in enumerate(seeds):
        rng = np.random.default_rng(seed)
        n = min(len(a_idx), len(b_idx))
        ia = rng.permutation(a_idx)[:n]
        ib = rng.permutation(b_idx)[:n]
        record = dict(seed=seed, pairs=n, methods={})
        for name, x in features.items():
            if name in encoders:
                # Exercise the public TPM/artifact API and its overlap guard end to end.
                result = learned_two_sample_e(
                    d["X"][ia],
                    d["X"][ib],
                    genes=d["genes"],
                    unit_a=d["units"][ia],
                    unit_b=d["units"][ib],
                    sampling=SamplingContract(
                        "expression", SOURCE, ASSUMPTIONS, NAMESPACE, "TPM"
                    ),
                    config=replace(cfg, seed=seed, encoder=str(root / f"{name}.npz")),
                )
            else:
                result = learned_two_sample_e(
                    x[ia],
                    x[ib],
                    genes=[f"{name}:{j}" for j in range(x.shape[1])],
                    unit_a=d["units"][ia],
                    unit_b=d["units"][ib],
                    sampling=contract,
                    config=replace(cfg, seed=seed),
                )
            results["software"] = result.metadata["software"]
            results["execution"] = result.metadata["execution"]
            replay.append(dict(run=i, method=name, result=result.to_dict()))
            record["methods"][name] = dict(
                e_value=result.e_value,
                log_wealth_path=result.log_wealth_path,
                final_reject=result.e_value >= 1 / protocol["alpha"],
                ever_crossed=max(result.log_wealth_path)
                >= math.log(1 / protocol["alpha"]),
            )
        if i == 0:
            p = permutation(z[ia], z[ib], rng, protocol["permutation_draws"])
            record["permutation"] = dict(
                p_value=p,
                calibrated_e=p_to_e(p),
                statistic="squared mean distance in frozen standardized genes",
            )
            results["primary"] = record
        else:
            results["sensitivity"].append(record)
        print(f"evaluation order {i + 1}/{len(seeds)}", flush=True)
    # Artificial null: fix disjoint unordered pairs from held-out donors, then
    # draw independent fair orientations. in_order prevents re-pairing which
    # would break this conditional null. Clinical labels play no role here.
    rng = np.random.default_rng(20262000)
    order = rng.permutation(len(d["X"]))
    n = len(order) // 2
    left = order[: 2 * n : 2]
    right = order[1 : 2 * n : 2]
    null = {k: [] for k in features}
    null_contract = SamplingContract(
        "aggregated",
        SOURCE + "; artificial fair-orientation audit",
        "Fixed disjoint unordered donor pairs with independent fair signs; preserve pair order. "
        "Conditional centering audit, not an assertion of iid clinical observations.",
        NAMESPACE,
    )
    for rep in range(protocol["null_repetitions"]):
        flip = np.random.default_rng(20263000 + rep).integers(0, 2, size=n).astype(bool)
        ia = np.where(flip, right, left)
        ib = np.where(flip, left, right)
        for name, x in features.items():
            r = learned_two_sample_e(
                x[ia],
                x[ib],
                genes=[f"{name}:{j}" for j in range(x.shape[1])],
                unit_a=d["units"][ia],
                unit_b=d["units"][ib],
                sampling=null_contract,
                config=replace(cfg, seed=20264000 + rep),
            )
            null[name].append(
                (r.e_value, max(r.log_wealth_path) >= math.log(1 / protocol["alpha"]))
            )
        if (rep + 1) % 25 == 0:
            print(
                f"orientation null {rep + 1}/{protocol['null_repetitions']}", flush=True
            )
    for name, values in null.items():
        final = sum(v >= 1 / protocol["alpha"] for v, _ in values)
        crossing = sum(c for _, c in values)
        count = len(values)
        results["orientation_null"][name] = dict(
            repetitions=count,
            final_rejections=final,
            crossing_rejections=crossing,
            final_ci95=interval(final, count),
            crossing_ci95=interval(crossing, count),
            quantiles=np.quantile(
                [v for v, _ in values], [0, 0.5, 0.9, 0.99, 1]
            ).tolist(),
        )
    results["seconds"] = time.perf_counter() - tick
    results["limitations"] = [
        "One observational cohort and a small negative group; no causal or clinical prediction claim.",
        "Primary seed and settings frozen before evaluation; other orders are sensitivity analyses, not independent power trials.",
        "Orientation null tests fair artificial signs conditional on fixed pairs; it does not assert COVID labels are randomized.",
        "No evidence selection or merger across methods/orders; final wealth is distinct from maximum wealth.",
        "Evaluation units excluded from gene selection, scaling and representation training; development split used only for device timing.",
        "Different latent widths: PCA64 and AE128; this comparison cannot isolate architecture alone.",
    ]
    write(root / "evaluation-replay.json", replay)
    write(root / "evaluation.json", results)
    print(json.dumps(results["primary"]), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["prepare", "train", "benchmark", "evaluate"])
    p.add_argument("--root", type=Path, default=Path("data/processed/evalue-real"))
    p.add_argument(
        "--device",
        default="cpu",
        help="bettor evaluation device; encoder training uses frozen CUDA protocol",
    )
    args = p.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    if args.action == "prepare":
        prepare(args.root)
    elif args.action == "train":
        train(args.root)
    elif args.action == "benchmark":
        benchmark(args.root)
    else:
        evaluate(args.root, args.device)


if __name__ == "__main__":
    main()
