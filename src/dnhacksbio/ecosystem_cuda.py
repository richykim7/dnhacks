"""CUDA-only exploratory cellular training with donor/study holdouts.

CPU work is limited to sparse input loading and bounded transfer batches. No
training fallback exists. This is not a private evidence/confirmation worker.
"""

from __future__ import annotations
import json, time, hashlib, fcntl
from pathlib import Path
import numpy as np


def require_cuda():
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required; CPU training fallback is prohibited")
    return torch.device("cuda")


def load_packs(directory, *, cells_per_donor=16384, seed=2701):
    from scipy import sparse
    import torch

    device = require_cuda()
    parts = []
    metadata = []
    genes = None
    rng = np.random.default_rng(seed)
    hashes = []
    for path in sorted(Path(directory).glob("*.npz")):
        with np.load(path, allow_pickle=False) as z:
            panel = z["genes"].tolist()
            if genes is not None and panel != genes:
                raise ValueError("Frozen common feature order required")
            genes = panel
            cells = json.loads(str(z["cells"]))
            manifest = json.loads(str(z["manifest"]))
            if manifest["schema"] != "ecosystem-expanded-v1":
                raise ValueError("Expanded development pack required")
            matrix = sparse.csr_matrix(
                (z["data"], z["indices"], z["indptr"]), shape=(len(cells), len(genes))
            )
        groups = {}
        for i, c in enumerate(cells):
            groups.setdefault(c["donor"], []).append(i)
        chosen = []
        for donor, rows in sorted(groups.items()):
            chosen.extend(
                sorted(rng.choice(rows, min(cells_per_donor, len(rows)), replace=False))
            )
        parts.append(matrix[chosen])
        metadata.extend(cells[i] for i in chosen)
        h = hashlib.sha256()
        with path.open("rb") as f:
            for b in iter(lambda: f.read(1024**2), b""):
                h.update(b)
        hashes.append(dict(file=path.name, sha256=h.hexdigest()))
    if not metadata or len(metadata) * len(genes) > 1_000_000_000:
        raise ValueError("Missing inputs or GPU data budget exceeded")
    # Allocate the complete dense training data only on CUDA, never on host.
    counts = torch.empty(
        (len(metadata), len(genes)), device=device, dtype=torch.float32
    )
    offset = 0
    for matrix in parts:
        for start in range(0, matrix.shape[0], 512):
            chunk = matrix[start : start + 512].toarray().astype(np.float32)
            counts[offset + start : offset + start + len(chunk)].copy_(
                torch.from_numpy(chunk).to(device)
            )
        offset += matrix.shape[0]
    totals = torch.tensor(
        [c["library_size"] for c in metadata], device=device, dtype=torch.float32
    )
    if (
        not torch.isfinite(counts).all()
        or (counts < 0).any()
        or (totals < counts.sum(1)).any()
    ):
        raise ValueError("Invalid library counts")
    logged = torch.log1p(counts / totals[:, None] * 10000)
    roles = {
        role: torch.tensor([c["role"] == role for c in metadata], device=device)
        for role in ("train", "validation", "external-test")
    }
    labels = torch.tensor(
        [c["label"] for c in metadata], device=device, dtype=torch.long
    )
    return counts, totals, logged, roles, labels, metadata, genes, hashes


def build_autoencoder(d, latent=64, nb=False):
    import torch

    encoder = torch.nn.Sequential(
        torch.nn.Linear(d, 256),
        torch.nn.LayerNorm(256),
        torch.nn.SiLU(),
        torch.nn.Linear(256, latent),
    )
    decoder = torch.nn.Sequential(
        torch.nn.Linear(latent, 256), torch.nn.SiLU(), torch.nn.Linear(256, d + int(nb))
    )
    return encoder.cuda(), decoder.cuda()


def cpu_state(module):
    return {k: v.detach().cpu().numpy() for k, v in module.state_dict().items()}


def save_weights(path, modules, manifest):
    arrays = {
        f"{name}.{k}": v
        for name, module in modules.items()
        for k, v in cpu_state(module).items()
    }
    with Path(path).open("wb") as f:
        np.savez_compressed(f, manifest=json.dumps(manifest, sort_keys=True), **arrays)


def classification(logged, roles, labels, output, *, epochs=100, seed=2701):
    import torch

    torch.manual_seed(seed)
    train = torch.where(roles["train"] & (labels >= 0))[0]
    val = torch.where(roles["validation"] & (labels >= 0))[0]
    model = torch.nn.Sequential(
        torch.nn.Linear(logged.shape[1], 128),
        torch.nn.LayerNorm(128),
        torch.nn.SiLU(),
        torch.nn.Dropout(0.2),
        torch.nn.Linear(128, 5),
    ).cuda()
    weights = torch.bincount(labels[train], minlength=5).float().clamp_min(1).rsqrt()
    weights /= weights.mean()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.01)
    curves = []
    started = time.monotonic()
    best = float("inf")
    best_state = None
    for epoch in range(epochs):
        model.train()
        order = train[torch.randperm(len(train), device="cuda")]
        loss_sum = 0.0
        for batch in order.split(512):
            loss = torch.nn.functional.cross_entropy(
                model(logged[batch]), labels[batch], weight=weights
            )
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            loss_sum += float(loss.detach()) * len(batch)
        model.eval()
        with torch.no_grad():
            pred = model(logged[val])
            loss = float(torch.nn.functional.cross_entropy(pred, labels[val]))
            accuracy = float((pred.argmax(1) == labels[val]).float().mean())
        curves.append(
            dict(
                epoch=epoch + 1,
                train_loss=loss_sum / len(train),
                validation_loss=loss,
                validation_accuracy=accuracy,
                seconds=time.monotonic() - started,
            )
        )
        if loss < best:
            best = loss
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        if (epoch + 1) % 10 == 0:
            print("lineage", curves[-1], flush=True)
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        prob = torch.cat([model(x).softmax(1) for x in logged.split(1024)])
    confidence, pred = prob.max(1)
    assigned = torch.where(
        labels >= 0,
        labels,
        torch.where(confidence >= 0.8, pred, torch.full_like(pred, -1)),
    )
    metrics = {}
    best_epoch = min(curves, key=lambda c: c["validation_loss"])["epoch"]
    for role, mask in roles.items():
        known = mask & (labels >= 0)
        metrics[role] = dict(
            labeled_cells=int(known.sum()),
            accuracy=float((pred[known] == labels[known]).float().mean())
            if known.any()
            else None,
        )
    report = dict(
        curves=curves,
        metrics=metrics,
        best_epoch=best_epoch,
        confidence_threshold=0.8,
        interpretation="Published coarse-label prediction, not CNA/malignancy validation",
        seed=seed,
    )
    save_weights(output / "lineage.npz", {"classifier": model}, report)
    return assigned, report


def reconstruction(
    logged,
    counts,
    totals,
    train,
    val,
    test,
    output,
    *,
    method="dae",
    epochs=200,
    seed=2701,
    latent=64,
):
    import torch

    torch.manual_seed(seed)
    d = logged.shape[1]
    nb = method == "nb"
    enc, dec = build_autoencoder(d, latent, nb)
    if nb:
        theta_raw = torch.nn.Parameter(torch.zeros(d, device="cuda"))
        with torch.no_grad():
            fractions = (counts[train] / totals[train, None]).mean(0)
            residual = (1 - fractions.sum()).clamp_min(1e-5)
            dec[-1].bias.copy_(
                torch.cat([fractions, residual[None]]).clamp_min(1e-7).log()
            )
    optimizer = torch.optim.AdamW(
        [*enc.parameters(), *dec.parameters(), *([theta_raw] if nb else [])],
        lr=0.001,
        weight_decay=0.0001,
    )

    def evaluate(indices):
        enc.eval()
        dec.eval()
        total_loss = 0.0
        mse = 0.0
        with torch.no_grad():
            for ix in indices.split(512):
                logits = dec(enc(logged[ix]))
                prediction = (
                    torch.log1p(10000 * logits.softmax(1)[:, :d]) if nb else logits
                )
                err = (prediction - logged[ix]).square().mean(1)
                mse += float(err.sum())
                if nb:
                    mu = (logits.softmax(1)[:, :d] * totals[ix, None]).clamp_min(1e-8)
                    theta = torch.nn.functional.softplus(theta_raw) + 1e-4
                    x = counts[ix]
                    loss = -(
                        torch.lgamma(x + theta)
                        - torch.lgamma(theta)
                        - torch.lgamma(x + 1)
                        + theta * (theta.log() - (theta + mu).log())
                        + x * (mu.log() - (theta + mu).log())
                    ).mean(1)
                    total_loss += float(loss.sum())
                else:
                    total_loss += float(err.sum())
        return dict(
            loss=total_loss / max(1, len(indices)),
            log_library_mse=mse / max(1, len(indices)),
        )

    history = []
    best = float("inf")
    best_epoch = 0
    best_state = None
    start = time.monotonic()
    for epoch in range(epochs):
        enc.train()
        dec.train()
        order = train[torch.randperm(len(train), device="cuda")]
        total = 0.0
        for ix in order.split(512):
            x = logged[ix]
            mask = torch.rand(x.shape, device="cuda") < 0.15
            logits = dec(enc(x.masked_fill(mask, 0)))
            if nb:
                mu = (logits.softmax(1)[:, :d] * totals[ix, None]).clamp_min(1e-8)
                theta = torch.nn.functional.softplus(theta_raw) + 1e-4
                y = counts[ix]
                logp = (
                    torch.lgamma(y + theta)
                    - torch.lgamma(theta)
                    - torch.lgamma(y + 1)
                    + theta * (theta.log() - (theta + mu).log())
                    + y * (mu.log() - (theta + mu).log())
                )
                loss = -logp[mask].mean()
            else:
                loss = (logits - x).square().mean()
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite training loss")
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_([*enc.parameters(), *dec.parameters()], 5)
            optimizer.step()
            total += float(loss.detach()) * len(ix)
        held = evaluate(val)
        history.append(
            dict(
                epoch=epoch + 1,
                train_loss=total / len(train),
                validation_loss=held["loss"],
                validation_mse=held["log_library_mse"],
                elapsed_seconds=time.monotonic() - start,
            )
        )
        if held["loss"] < best:
            best = held["loss"]
            best_epoch = epoch + 1
            best_state = (
                {k: v.detach().clone() for k, v in enc.state_dict().items()},
                {k: v.detach().clone() for k, v in dec.state_dict().items()},
                theta_raw.detach().clone() if nb else None,
            )
        if epoch == 0 or (epoch + 1) % 10 == 0:
            print(method, output.name, history[-1], flush=True)
        if epoch + 1 - best_epoch >= 35:
            break
    enc.load_state_dict(best_state[0])
    dec.load_state_dict(best_state[1])
    if nb:
        theta_raw.data.copy_(best_state[2])
    metrics = {
        "train": evaluate(train),
        "validation": evaluate(val),
        "external-test": evaluate(test),
    }
    enc.eval()
    with torch.no_grad():
        embeddings = torch.cat([enc(x) for x in logged.split(1024)])
    report = dict(
        method=method,
        seed=seed,
        latent=latent,
        best_epoch=best_epoch,
        curves=history,
        metrics=metrics,
        training_cells=len(train),
        validation_cells=len(val),
        external_cells=len(test),
        seconds=time.monotonic() - start,
        device="cuda",
        peak_allocated_bytes=torch.cuda.max_memory_allocated(),
    )
    save_weights(
        output / f"{method}-{seed}.npz", {"encoder": enc, "decoder": dec}, report
    )
    if nb:
        np.savez_compressed(
            output / f"{method}-{seed}-dispersion.npz",
            dispersion=(torch.nn.functional.softplus(theta_raw) + 1e-4)
            .detach()
            .cpu()
            .numpy(),
        )
    return embeddings, report


def pca(logged, train, val, test, output, latent=64):
    import torch

    mean = logged[train].mean(0)
    x = logged[train] - mean
    _, v = torch.linalg.eigh(x.T @ x / len(train))
    projection = v[:, -latent:].flip(1)
    z = (logged - mean) @ projection
    metrics = {}
    for name, ix in [("train", train), ("validation", val), ("external-test", test)]:
        metrics[name] = dict(
            log_library_mse=float(
                ((z[ix] @ projection.T + mean) - logged[ix]).square().mean()
            )
        )
    np.savez_compressed(
        output / "pca.npz",
        mean=mean.cpu().numpy(),
        projection=projection.cpu().numpy(),
        manifest=json.dumps(dict(device="cuda", method="pca", latent=latent)),
    )
    return z, dict(
        method="pca",
        solver="exact CUDA covariance eigendecomposition",
        device="cuda",
        metrics=metrics,
        latent=latent,
    )


def donor_summary(z, assigned, metadata, compartment, minimum=32):
    import torch

    groups = {}
    selected = assigned.detach().cpu().tolist()
    for i, c in enumerate(metadata):
        if selected[i] == compartment:
            groups.setdefault(c["donor"], []).append(i)
    rows = []
    donors = []
    roles = []
    studies = []
    for donor, indices in sorted(groups.items()):
        if len(indices) < minimum:
            continue
        ix = torch.tensor(indices, device="cuda")
        v = z[ix]
        rows.append(torch.cat([v.mean(0), v.var(0, unbiased=False)]))
        donors.append(donor)
        roles.append(metadata[indices[0]]["role"])
        studies.append(metadata[indices[0]]["study"])
    return torch.stack(rows), donors, roles, studies


def association(left, right, output, seed=2701):
    """GPU trained matched-vs-mismatched scorer; donor holdout, exploratory only."""
    import torch

    a, ad, ar, ast = left
    b, bd, br, bst = right
    shared = sorted(set(ad) & set(bd))
    ai = torch.tensor([ad.index(d) for d in shared], device="cuda")
    bi = torch.tensor([bd.index(d) for d in shared], device="cuda")
    x = a[ai]
    y = b[bi]
    roles = [ar[ad.index(d)] for d in shared]
    train = torch.tensor(
        [i for i, r in enumerate(roles) if r == "train"], device="cuda"
    )
    val = torch.tensor([i for i, r in enumerate(roles) if r != "train"], device="cuda")
    if len(train) < 5 or len(val) < 3:
        return dict(
            available=False,
            complete_donors=len(shared),
            reason="insufficient donor holdout",
        )
    mx = x[train].mean(0)
    sx = x[train].std(0).clamp_min(0.1)
    my = y[train].mean(0)
    sy = y[train].std(0).clamp_min(0.1)
    x = (x - mx) / sx
    y = (y - my) / sy
    torch.manual_seed(seed)
    model = torch.nn.Sequential(
        torch.nn.Linear(x.shape[1] + y.shape[1], 64),
        torch.nn.SiLU(),
        torch.nn.Dropout(0.3),
        torch.nn.Linear(64, 1),
    ).cuda()
    opt = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.05)
    studies = [ast[ad.index(d)] for d in shared]
    covariance = x[train].T @ y[train] / len(train)
    same_study = torch.tensor(
        [
            [studies[i] == studies[j] and i != j for j in train.tolist()]
            for i in train.tolist()
        ],
        device="cuda",
        dtype=torch.float32,
    )
    if (same_study.sum(1) == 0).any():
        raise ValueError(
            "Within-study negative training needs at least two donors per study"
        )

    def evaluate(ix, baseline=False):
        model.eval()
        with torch.no_grad():
            pairs = torch.cartesian_prod(ix, ix)
            scores = (
                ((x[pairs[:, 0]] @ covariance) * y[pairs[:, 1]]).sum(1)
                if baseline
                else model(torch.cat([x[pairs[:, 0]], y[pairs[:, 1]]], 1)).flatten()
            )
            truth = pairs[:, 0] == pairs[:, 1]
            positive = scores[truth]
            negative = scores[~truth]
            auc = float(
                (
                    (positive[:, None] > negative).float()
                    + 0.5 * (positive[:, None] == negative).float()
                ).mean()
            )
            loss = float(
                torch.nn.functional.binary_cross_entropy_with_logits(
                    scores, truth.float()
                )
            )
        return dict(
            auroc=auc,
            loss=loss,
            independent_donors=len(ix),
            matched_pairs=len(ix),
            mismatched_pairs=len(ix) * (len(ix) - 1),
        )

    history = []
    for epoch in range(300):
        model.train()
        other = train[torch.multinomial(same_study, 1).flatten()]
        inputs = torch.cat(
            [torch.cat([x[train], y[train]], 1), torch.cat([x[train], y[other]], 1)]
        )
        labels = torch.cat(
            [
                torch.ones(len(train), device="cuda"),
                torch.zeros(len(train), device="cuda"),
            ]
        )
        loss = torch.nn.functional.binary_cross_entropy_with_logits(
            model(inputs).flatten(), labels
        )
        opt.zero_grad()
        loss.backward()
        opt.step()
        if epoch % 10 == 0:
            history.append(
                dict(
                    epoch=epoch + 1,
                    train_loss=float(loss.detach()),
                    held_out_auroc=evaluate(val)["auroc"],
                )
            )
    study_metrics = {}
    for study in sorted(set(studies)):
        ix = torch.tensor(
            [i for i in val.tolist() if studies[i] == study], device="cuda"
        )
        if len(ix) >= 3:
            study_metrics[study] = dict(
                learned=evaluate(ix), bilinear=evaluate(ix, True)
            )
    report = dict(
        curves=history,
        seed=seed,
        negative_sampling="within-training-study only",
        train=evaluate(train),
        held_out=evaluate(val),
        held_out_bilinear=evaluate(val, True),
        within_study_holdouts=study_metrics,
        complete_donors=len(shared),
        interpretation="Exposed donor-matching discrimination; pooled study/treatment confounding possible; no p-value/e-value or power certificate",
    )
    save_weights(output / f"association-{seed}.npz", {"critic": model}, report)
    return report


def run(prepared, output, *, epochs=200, seeds=(2701,), lease="/tmp/dnhacks-gpu.lock"):
    import torch

    if type(epochs) is not int or not 1 <= epochs <= 500 or not seeds or len(seeds) > 3:
        raise ValueError("Use 1-500 epochs and 1-3 recorded seeds")
    if lease != "/tmp/dnhacks-gpu.lock":
        raise ValueError("Canonical shared GPU lease required")
    require_cuda()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with Path(lease).open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        torch.set_num_threads(2)
        torch.cuda.reset_peak_memory_stats()
        torch.manual_seed(seeds[0])
        started = time.monotonic()
        counts, totals, logged, roles, labels, metadata, genes, hashes = load_packs(
            prepared
        )
        assigned, lineage = classification(logged, roles, labels, output, seed=seeds[0])
        report = dict(
            schema="ecosystem-cuda-expansion-v1",
            status="exposed-development",
            confirmation="unavailable",
            device=torch.cuda.get_device_name(),
            torch_version=torch.__version__,
            inputs=hashes,
            genes=len(genes),
            cells=len(metadata),
            donors=len({c["donor"] for c in metadata}),
            lineage=lineage,
            models={},
            coverage={},
            association={},
        )
        summaries = {}
        donor_reports = {}
        for comp, name in [(0, "epithelial-enriched"), (1, "fibroblast")]:
            out = output / name
            out.mkdir(exist_ok=True)
            indices = {
                r: torch.where(mask & (assigned == comp))[0]
                for r, mask in roles.items()
            }
            if min(len(v) for v in indices.values()) < 64:
                raise ValueError("Insufficient compartment coverage")
            eligible = {
                r: len({metadata[i]["donor"] for i in ix.detach().cpu().tolist()})
                for r, ix in indices.items()
            }
            report["coverage"][name] = dict(
                cells={r: len(ix) for r, ix in indices.items()}, donors=eligible
            )
            z, measured = pca(logged, *indices.values(), out)
            report["models"][name + "-pca"] = measured
            for seed in seeds:
                for method in ("dae", "nb"):
                    z, measured = reconstruction(
                        logged,
                        counts,
                        totals,
                        *indices.values(),
                        out,
                        method=method,
                        epochs=epochs,
                        seed=seed,
                    )
                    report["models"][f"{name}-{method}-{seed}"] = measured
                    if method == "dae" and seed == seeds[0]:
                        summaries[name] = donor_summary(z, assigned, metadata, comp)
                    report["elapsed_seconds"] = time.monotonic() - started
                    (output / "report.json").write_text(
                        json.dumps(report, indent=2, allow_nan=False) + "\n"
                    )
            donor_reports[name] = [
                dict(donor=d, role=r, study=s)
                for d, r, s in zip(
                    summaries[name][1], summaries[name][2], summaries[name][3]
                )
            ]
        for name, (values, donors, donor_roles, studies) in summaries.items():
            np.savez_compressed(
                output / f"{name}-donor-summaries.npz",
                values=values.cpu().numpy(),
                donors=np.asarray(donors),
                roles=np.asarray(donor_roles),
                studies=np.asarray(studies),
            )
        report["association"] = {
            str(seed): association(
                summaries["epithelial-enriched"],
                summaries["fibroblast"],
                output,
                seed=seed,
            )
            for seed in seeds
        }
        report["elapsed_seconds"] = time.monotonic() - started
        report["peak_allocated_bytes"] = torch.cuda.max_memory_allocated()
        (output / "report.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n"
        )
        (output / "donor-coverage.json").write_text(
            json.dumps(donor_reports, indent=2) + "\n"
        )
        print(
            "Finished",
            report["elapsed_seconds"],
            report["coverage"],
            {s: r.get("held_out") for s, r in report["association"].items()},
            flush=True,
        )
    return report


def refresh_exact_pca(prepared, output, lease="/tmp/dnhacks-gpu.lock"):
    """Strengthen a completed comparison baseline without refitting neural models."""
    import torch

    if lease != "/tmp/dnhacks-gpu.lock":
        raise ValueError("Canonical shared GPU lease required")
    require_cuda()
    output = Path(output)
    with Path(lease).open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        torch.set_num_threads(2)
        counts, totals, logged, roles, labels, metadata, genes, hashes = load_packs(
            prepared
        )
        report = json.loads((output / "report.json").read_text())
        if hashes != report["inputs"]:
            raise ValueError("Frozen source packs changed")
        classifier = torch.nn.Sequential(
            torch.nn.Linear(len(genes), 128),
            torch.nn.LayerNorm(128),
            torch.nn.SiLU(),
            torch.nn.Dropout(0.2),
            torch.nn.Linear(128, 5),
        ).cuda()
        with np.load(output / "lineage.npz", allow_pickle=False) as z:
            classifier.load_state_dict(
                {
                    k: torch.from_numpy(z["classifier." + k]).cuda()
                    for k in classifier.state_dict()
                }
            )
        classifier.eval()
        with torch.no_grad():
            prob = torch.cat([classifier(x).softmax(1) for x in logged.split(1024)])
        confidence, pred = prob.max(1)
        assigned = torch.where(
            labels >= 0,
            labels,
            torch.where(confidence >= 0.8, pred, torch.full_like(pred, -1)),
        )
        report["randomized_pca_pilot"] = {}
        for comp, name in [(0, "epithelial-enriched"), (1, "fibroblast")]:
            indices = {
                r: torch.where(mask & (assigned == comp))[0]
                for r, mask in roles.items()
            }
            _, result = pca(logged, *indices.values(), output / name)
            report["randomized_pca_pilot"][name] = report["models"][name + "-pca"]
            report["models"][name + "-pca"] = result
        # Report coverage sensitivity separately; never silently change the
        # >=32-cell donor definition used for the association benchmark.
        by_donor = {}
        assigned_labels = assigned.detach().cpu().tolist()
        for i, c in enumerate(metadata):
            label = assigned_labels[i]
            if label in (0, 1):
                by_donor.setdefault(c["donor"], [0, 0])[label] += 1
        report["complete_donor_coverage"] = {
            str(n): sum(min(v) >= n for v in by_donor.values())
            for n in (16, 32, 64, 128)
        }
        (output / "report.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n"
        )
        print(
            "Exact GPU PCA",
            {
                k: v["metrics"]
                for k, v in report["models"].items()
                if k.endswith("-pca")
            },
            report["complete_donor_coverage"],
            flush=True,
        )
    return report
