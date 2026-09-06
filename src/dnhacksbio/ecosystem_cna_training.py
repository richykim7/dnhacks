"""Direct malignant/CAF CUDA training with fixed donor splits and measurements."""

from __future__ import annotations

import fcntl
import json
from pathlib import Path
import numpy as np


def donor_groups(metadata, indices):
    groups = {}
    roles = {}
    for c in metadata:
        roles.setdefault(c["donor"], set()).add(c["role"])
    if any(len(r) != 1 for r in roles.values()):
        raise ValueError("Donor crosses training and validation roles")
    for i in indices:
        groups.setdefault(metadata[i]["donor"], []).append(i)
    return groups


def nb_loss(counts, logits, totals, dispersion):
    import torch

    mu = (logits.softmax(1)[:, : counts.shape[1]] * totals[:, None]).clamp_min(1e-8)
    theta = torch.nn.functional.softplus(dispersion) + 1e-4
    return -(
        torch.lgamma(counts + theta)
        - torch.lgamma(theta)
        - torch.lgamma(counts + 1)
        + theta * (theta.log() - (theta + mu).log())
        + counts * (mu.log() - (theta + mu).log())
    )


def train_encoder(logged, counts, totals, groups, output, *, method, epochs, seed):
    import torch
    from .ecosystem_cuda import build_autoencoder, save_weights

    torch.manual_seed(seed)
    d = logged.shape[1]
    is_nb = method == "nb"
    encoder, decoder = build_autoencoder(d, 64, is_nb)
    dispersion = torch.nn.Parameter(torch.zeros(d, device="cuda")) if is_nb else None
    if is_nb:
        with torch.no_grad():
            fractions = torch.stack(
                [
                    (counts[ix] / totals[ix, None]).mean(0)
                    for ix in groups["train"].values()
                ]
            ).mean(0)
            residual = (1 - fractions.sum()).clamp_min(1e-5)
            decoder[-1].bias.copy_(
                torch.cat([fractions, residual[None]]).clamp_min(1e-7).log()
            )
    parameters = [*encoder.parameters(), *decoder.parameters()] + (
        [dispersion] if is_nb else []
    )
    optimizer = torch.optim.AdamW(parameters, lr=0.001, weight_decay=0.0001)
    weights = torch.zeros(len(logged), device="cuda")
    for ix in groups["train"].values():
        weights[ix] = 1 / len(ix)
    steps = sum(len(ix) for ix in groups["train"].values())

    def evaluate():
        encoder.eval()
        decoder.eval()
        metrics = {}
        for role, by_donor in groups.items():
            donor_metrics = []
            generator = torch.Generator(device="cuda").manual_seed(seed + 1)
            for donor, indices in by_donor.items():
                total = 0.0
                mse = 0.0
                for ix in indices.split(512):
                    x = logged[ix]
                    mask = (
                        torch.rand(x.shape, device="cuda", generator=generator) < 0.15
                    )
                    prediction = decoder(encoder(x.masked_fill(mask, 0)))
                    loss = (
                        nb_loss(counts[ix], prediction, totals[ix], dispersion)
                        if is_nb
                        else (prediction - x).square()
                    )
                    per_cell = (loss * mask).sum(1) / mask.sum(1).clamp_min(1)
                    recon = (
                        torch.log1p(10000 * prediction.softmax(1)[:, :d])
                        if is_nb
                        else prediction
                    )
                    total += float(per_cell.sum())
                    mse += float((recon - x).square().mean(1).sum())
                donor_metrics.append(
                    dict(
                        donor=donor,
                        masked_loss=total / len(indices),
                        masked_input_log_mse=mse / len(indices),
                    )
                )
            metrics[role] = dict(
                donors=donor_metrics,
                masked_loss=sum(v["masked_loss"] for v in donor_metrics)
                / len(donor_metrics),
                masked_input_log_mse=sum(
                    v["masked_input_log_mse"] for v in donor_metrics
                )
                / len(donor_metrics),
            )
        return metrics

    curves = []
    for epoch in range(epochs):
        encoder.train()
        decoder.train()
        total = 0.0
        order = torch.multinomial(weights, steps, replacement=True)
        for ix in order.split(512):
            x = logged[ix]
            mask = torch.rand(x.shape, device="cuda") < 0.15
            prediction = decoder(encoder(x.masked_fill(mask, 0)))
            loss = (
                nb_loss(counts[ix], prediction, totals[ix], dispersion)
                if is_nb
                else (prediction - x).square()
            )
            objective = ((loss * mask).sum(1) / mask.sum(1).clamp_min(1)).mean()
            if not torch.isfinite(objective):
                raise ValueError("Nonfinite count objective")
            optimizer.zero_grad()
            objective.backward()
            torch.nn.utils.clip_grad_norm_(parameters, 5)
            optimizer.step()
            total += float(objective.detach()) * len(ix)
        if epoch == 0 or (epoch + 1) % 5 == 0:
            with torch.no_grad():
                metrics = evaluate()
            curves.append(
                dict(
                    epoch=epoch + 1,
                    training_loss=total / steps,
                    validation_loss=metrics["validation"]["masked_loss"],
                    validation_mse=metrics["validation"]["masked_input_log_mse"],
                )
            )
            print(method, output.name, curves[-1], flush=True)
    encoder.eval()
    decoder.eval()
    with torch.no_grad():
        z = torch.cat([encoder(x) for x in logged.split(1024)])
        metrics = evaluate()
    report = dict(
        method=method,
        seed=seed,
        epochs=epochs,
        selection="fixed final checkpoint; no validation-selected epoch",
        curves=curves,
        metrics=metrics,
        latent=64,
        device="cuda",
    )
    save_weights(
        output / f"{method}.npz", {"encoder": encoder, "decoder": decoder}, report
    )
    if is_nb:
        np.savez_compressed(
            output / "nb-dispersion.npz",
            dispersion=(torch.nn.functional.softplus(dispersion) + 1e-4)
            .detach()
            .cpu()
            .numpy(),
        )
    return z, report


def run(prepared, output, *, epochs=100):
    import torch
    from .ecosystem_cuda import load_packs, require_cuda
    from .ecosystem_snrna import fixed_bag_summary

    if type(epochs) is not int or not 1 <= epochs <= 200:
        raise ValueError("Use1-200 fixed epochs")
    require_cuda()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    protocol = dict(
        schema="ecosystem-cna-model-training-v1",
        epochs=epochs,
        seed=9407,
        latent=64,
        donor_balanced=True,
        cells_per_bag=32,
        methods=["pca", "dae", "nb"],
        selection="Fixed encoder specifications before fitting;8 development donors never select checkpoints",
        biological_gate_passed=False,
    )
    (output / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    with open("/tmp/dnhacks-gpu.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        torch.set_num_threads(2)
        torch.cuda.reset_peak_memory_stats()
        counts, totals, logged, roles, labels, metadata, genes, hashes = load_packs(
            prepared
        )
        if any(c["neoadjuvant"] for c in metadata):
            raise ValueError("Untreated source packs required")
        # Freeze removal of the50 author-CAF adipocyte labels before training.
        adipocyte = torch.tensor(
            [c["author_cell_type"] == "adipocyte" for c in metadata], device="cuda"
        )
        assigned = labels.clone()
        assigned[adipocyte] = 4
        report = dict(
            protocol=protocol,
            inputs=hashes,
            models={},
            coverage={},
            device=torch.cuda.get_device_name(),
            excluded_adipocyte_cells=int(adipocyte.sum()),
        )
        for comp, name in [(0, "epithelial-enriched"), (1, "fibroblast")]:
            out = output / name
            out.mkdir(exist_ok=True)
            groups = {}
            for role in ("train", "validation"):
                ix = torch.where(roles[role] & (assigned == comp))[0].cpu().tolist()
                groups[role] = {
                    donor: torch.tensor(rows, device="cuda")
                    for donor, rows in donor_groups(metadata, ix).items()
                }
                if len(groups[role]) < 3:
                    raise ValueError("Independent donor coverage insufficient")
            report["coverage"][name] = {
                role: {d: len(ix) for d, ix in group.items()}
                for role, group in groups.items()
            }
            mean = torch.stack(
                [logged[ix].mean(0) for ix in groups["train"].values()]
            ).mean(0)
            covariance = torch.zeros((len(genes), len(genes)), device="cuda")
            for ix in groups["train"].values():
                x = logged[ix] - mean
                covariance.add_(x.T @ x / len(ix) / len(groups["train"]))
            _, v = torch.linalg.eigh(covariance)
            basis = v[:, -64:].flip(1)
            z = (logged - mean) @ basis
            metrics = {
                role: sum(
                    float(((z[ix] @ basis.T + mean) - logged[ix]).square().mean())
                    for ix in group.values()
                )
                / len(group)
                for role, group in groups.items()
            }
            np.savez_compressed(
                out / "pca.npz", mean=mean.cpu().numpy(), projection=basis.cpu().numpy()
            )
            pca_report = dict(
                method="pca",
                metrics=metrics,
                measurement="unmasked reconstruction; not directly comparable to masked-input neural validation",
                latent=64,
                device="cuda",
            )
            for method in ("pca", "dae", "nb"):
                if method == "pca":
                    measured = pca_report
                else:
                    z, measured = train_encoder(
                        logged,
                        counts,
                        totals,
                        groups,
                        out,
                        method=method,
                        epochs=epochs,
                        seed=9407,
                    )
                values, donors, donor_roles, studies = fixed_bag_summary(
                    z, assigned, metadata, comp
                )
                view = output / method
                view.mkdir(exist_ok=True)
                np.savez_compressed(
                    view / (name + "-donor-summaries.npz"),
                    values=values.cpu().numpy(),
                    donors=np.asarray(donors),
                    roles=np.asarray(donor_roles),
                    studies=np.asarray(studies),
                )
                report["models"][name + "-" + method] = measured
                (output / "report.json").write_text(
                    json.dumps(report, indent=2, allow_nan=False) + "\n"
                )
        report["peak_vram_bytes"] = torch.cuda.max_memory_allocated()
        (output / "report.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n"
        )
        return report


def critic_folds(train):
    """Three deterministic donor folds; never split a donor's cells."""
    if len(train) < 6 or len(set(train)) != len(train):
        raise ValueError("At least6 unique training donors required")
    return [([i for i in train if i not in train[k::3]], train[k::3]) for k in range(3)]


def train_critics(views, output):
    import torch
    from .ecosystem_cuda import require_cuda
    from .ecosystem_power import projection
    from .ecosystem_power_training import cca_rbf, growth_network, growth, study_pairs

    require_cuda()
    views = Path(views)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with open("/tmp/dnhacks-gpu.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        torch.set_num_threads(2)
        packs = []
        for name in ("epithelial-enriched", "fibroblast"):
            with np.load(
                views / (name + "-donor-summaries.npz"), allow_pickle=False
            ) as z:
                packs.append({k: z[k].copy() for k in z.files})
        shared = sorted(set(packs[0]["donors"]) & set(packs[1]["donors"]))
        values = []
        roles = None
        studies = None
        for p in packs:
            if len(p["donors"]) != len(set(p["donors"])):
                raise ValueError("Repeated donor")
            ix = [p["donors"].tolist().index(d) for d in shared]
            r = p["roles"][ix].tolist()
            s = p["studies"][ix].tolist()
            if roles is not None and (r != roles or s != studies):
                raise ValueError("Compartment role/study mismatch")
            roles, studies = r, s
            values.append(torch.as_tensor(p["values"][ix], device="cuda"))
        x, y = values
        train = [i for i, r in enumerate(roles) if r == "train"]
        held = [i for i, r in enumerate(roles) if r == "validation"]
        if len(held) < 3:
            raise ValueError("Held-out donor coverage insufficient")
        folds = critic_folds(train)
        configs = [
            dict(method="cca-rbf", rank=k, ridge=r, bandwidth=b)
            for k in (1, 2, 4, 8)
            for r in (0.1, 1.0, 10.0)
            for b in (0.5, 1.0, 2.0)
        ]
        configs += [
            dict(method="native-growth", rank=k, decay=d, seed=9201)
            for k in (2, 8)
            for d in (0.1, 1.0)
        ]
        candidates = []
        for config in configs:
            fitter = cca_rbf if config["method"] == "cca-rbf" else growth_network
            scores = []
            for fit, validation in folds:
                c, _, _ = fitter(x, y, fit, studies, config)
                scores.append(float(growth(c, study_pairs(validation, studies))))
            candidates.append(
                dict(
                    config=config,
                    fold_growth=scores,
                    mean_growth=sum(scores) / len(scores),
                )
            )
        selected = {
            method: max(
                [r for r in candidates if r["config"]["method"] == method],
                key=lambda r: r["mean_growth"],
            )
            for method in ("cca-rbf", "native-growth")
        }
        selection = dict(
            schema="ecosystem-cna-critic-selection-v1",
            candidate_scope="critic-only3fold TRAIN donor evaluation; encoders trained on all9TRAIN donors",
            donors=shared,
            training_donors=[shared[i] for i in train],
            development_donors=[shared[i] for i in held],
            candidates=candidates,
            selected=selected,
        )
        (output / "selection.json").write_text(json.dumps(selection, indent=2) + "\n")
        results = {}
        for method, chosen in selected.items():
            fitter = cca_rbf if method == "cca-rbf" else growth_network
            c, state, curves = fitter(x, y, train, studies, chosen["config"])
            np.savez_compressed(
                output / (method + ".npz"),
                manifest=json.dumps(
                    dict(
                        schema="ecosystem-cna-direct-critic-v1",
                        normalization="fitter-only",
                        **chosen,
                    )
                ),
                **{k: v.detach().cpu().numpy() for k, v in state.items()},
            )
            replay = direct_critic_scores(x, y, state, chosen["config"])
            replay_error = float((replay - c).abs().max())
            if replay_error > 1e-5:
                raise ValueError("Frozen critic replay differs from fitted scores")
            ix = torch.tensor(held, device="cuda")
            matrix = c[ix[:, None], ix[None, :]].detach()
            result = dict(
                selection=chosen,
                frozen_replay_max_error=replay_error,
                curves=curves,
                observed_donors=len(held),
                distinct_pair_log_growth=float(growth(c, study_pairs(held, studies))),
                projections=[],
            )
            for n in (18, 24, 40, 60, 100):
                for null in (False, True):
                    result["projections"].append(
                        dict(
                            simulated_donors=n,
                            scenario="product-null" if null else "empirical-joint",
                            **projection(
                                matrix, n, streams=10000, seed=9411, null=null
                            ),
                        )
                    )
            results[method] = result
            print(
                views.name,
                method,
                "TRAIN-CV",
                chosen["mean_growth"],
                "HELD",
                result["distinct_pair_log_growth"],
                flush=True,
            )
        report = dict(
            schema="ecosystem-cna-direct-power-v1",
            representation=views.name,
            training_donors=len(train),
            development_donors=len(held),
            results=results,
            biological_gate_passed=False,
            normalization="Each fitter uses only its TRAIN donors; no extra load_views normalization",
        )
        (output / "report.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n"
        )
        return report


def direct_critic_scores(x, y, state, config):
    """Apply a single fitter normalization stored by this direct-training schema."""
    import torch

    x = (x - state["x_mean"]) / state["x_scale"]
    y = (y - state["y_mean"]) / state["y_scale"]
    if config["method"] == "cca-rbf":
        a = x @ state["x_projection"]
        b = y @ state["y_projection"]
        distance = (a[:, None] - b[None, :]).square().sum(-1) / config["rank"]
        return 2 * torch.exp(-distance / (2 * config["bandwidth"] ** 2)) - 1
    if config["method"] != "native-growth":
        raise ValueError("Unknown frozen critic")
    a = torch.nn.functional.linear(
        x, state["left.0.weight"], state["left.0.bias"]
    ).tanh()
    b = torch.nn.functional.linear(
        y, state["right.0.weight"], state["right.0.bias"]
    ).tanh()
    return torch.tanh((a * state["weight"]) @ b.T + state["offset"])
