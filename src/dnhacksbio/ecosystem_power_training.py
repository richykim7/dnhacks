"""Train transferable bounded critics for native-kernel growth, on CUDA only."""

from __future__ import annotations

import fcntl
import json
from pathlib import Path

import numpy as np

from .ecosystem_cuda import require_cuda
from .ecosystem_power import bounded_kernel, load_views, projection


def study_pairs(indices, studies):
    import torch

    pairs = [
        (i, j) for i in indices for j in indices if i < j and studies[i] == studies[j]
    ]
    if not pairs:
        raise ValueError("At least one same-study donor pair required")
    return torch.tensor(pairs, device="cuda").T


def growth(c, pairs):
    import torch

    i, j = pairs
    return torch.log1p(0.9 * bounded_kernel(c, i, i, j, j)).mean()


def normalize(x, y, indices):
    import torch

    ix = torch.tensor(indices, device="cuda")
    mx, my = x[ix].mean(0), y[ix].mean(0)
    sx, sy = x[ix].std(0).clamp_min(0.1), y[ix].std(0).clamp_min(0.1)
    return (
        (x - mx) / sx,
        (y - my) / sy,
        dict(x_mean=mx, y_mean=my, x_scale=sx, y_scale=sy),
    )


def cca_rbf(x, y, indices, studies, config):
    import torch

    # Remove study means only in training covariance estimation, never by fitting
    # an external-study normalization reference during scoring.
    x, y, state = normalize(x, y, indices)
    xx, yy = [], []
    for study in sorted({studies[i] for i in indices}):
        ix = torch.tensor([i for i in indices if studies[i] == study], device="cuda")
        xx.append(x[ix] - x[ix].mean(0))
        yy.append(y[ix] - y[ix].mean(0))
    xx, yy = torch.cat(xx), torch.cat(yy)
    ridge = config["ridge"]

    def whitening(v):
        cov = v.T @ v / len(v)
        eig, vectors = torch.linalg.eigh(
            cov + ridge * torch.eye(v.shape[1], device="cuda")
        )
        return (vectors * eig.clamp_min(1e-6).rsqrt()) @ vectors.T

    wx, wy = whitening(xx), whitening(yy)
    u, singular, vh = torch.linalg.svd(
        wx @ (xx.T @ yy / len(xx)) @ wy, full_matrices=False
    )
    rank = config["rank"]
    px, py = wx @ u[:, :rank], wy @ vh[:rank].T
    a, b = x @ px, y @ py
    distance = (a[:, None] - b[None, :]).square().sum(-1) / rank
    c = 2 * torch.exp(-distance / (2 * config["bandwidth"] ** 2)) - 1
    state.update(x_projection=px, y_projection=py, correlations=singular[:rank])
    return c, state, []


def growth_network(x, y, indices, studies, config):
    import torch

    torch.manual_seed(config["seed"])
    x, y, state = normalize(x, y, indices)
    rank = config["rank"]
    left = torch.nn.Sequential(
        torch.nn.Linear(x.shape[1], rank), torch.nn.Tanh()
    ).cuda()
    right = torch.nn.Sequential(
        torch.nn.Linear(y.shape[1], rank), torch.nn.Tanh()
    ).cuda()
    # A critic may learn both views; the input compartment encoders remain
    # separate and frozen. No held-out donor enters any optimizer update.
    weight = torch.nn.Parameter(torch.ones(rank, device="cuda"))
    offset = torch.nn.Parameter(torch.zeros((), device="cuda"))
    parameters = [*left.parameters(), *right.parameters(), weight, offset]
    optimizer = torch.optim.AdamW(parameters, lr=0.003, weight_decay=config["decay"])
    pairs = study_pairs(indices, studies)
    history = []
    for epoch in range(300):
        a, b = left(x), right(y)
        c = torch.tanh((a * weight) @ b.T + offset)
        loss = -growth(c, pairs)
        if not torch.isfinite(loss):
            raise ValueError("Nonfinite native-growth objective")
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(parameters, 2)
        optimizer.step()
        if epoch % 10 == 0 or epoch == 299:
            history.append(
                dict(epoch=epoch + 1, training_negative_log_growth=float(loss.detach()))
            )
    with torch.no_grad():
        c = torch.tanh((left(x) * weight) @ right(y).T + offset)
    state.update({"left." + k: v.detach() for k, v in left.state_dict().items()})
    state.update({"right." + k: v.detach() for k, v in right.state_dict().items()})
    state.update(weight=weight.detach(), offset=offset.detach())
    return c, state, history


def run(root, output):
    import torch

    require_cuda()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with Path("/tmp/dnhacks-gpu.lock").open("a+") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        torch.set_num_threads(2)
        x, y, train_tensor, roles, studies = load_views(root)
        # The source arrays were standardized by the prior frozen training
        # transform; every fold additionally fits its own normalization above.
        train = train_tensor.tolist()
        training_studies = sorted({studies[i] for i in train})
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
            folds = []
            for study in training_studies:
                fit = [i for i in train if studies[i] != study]
                held = [i for i in train if studies[i] == study]
                c, _, _ = fitter(x, y, fit, studies, config)
                folds.append(
                    dict(
                        study=study,
                        donors=len(held),
                        log_growth=float(growth(c, study_pairs(held, studies))),
                    )
                )
            score = sum(f["log_growth"] for f in folds) / len(folds)
            candidates.append(
                dict(config=config, folds=folds, mean_study_log_growth=score)
            )
            print(config, score, flush=True)
        # Freeze exactly one selection per family before scoring the development
        # holdouts. Report all candidates and both families, not a posthoc winner.
        selected = {
            method: max(
                [r for r in candidates if r["config"]["method"] == method],
                key=lambda r: r["mean_study_log_growth"],
            )
            for method in ("cca-rbf", "native-growth")
        }
        (output / "selection.json").write_text(
            json.dumps(
                dict(
                    training_studies=training_studies,
                    candidates=candidates,
                    selected=selected,
                ),
                indent=2,
            )
            + "\n"
        )
        results = {}
        for method, chosen in selected.items():
            fitter = cca_rbf if method == "cca-rbf" else growth_network
            c, state, curves = fitter(x, y, train, studies, chosen["config"])
            with (output / f"{method}.npz").open("wb") as f:
                np.savez_compressed(
                    f,
                    manifest=json.dumps(chosen),
                    **{k: v.detach().cpu().numpy() for k, v in state.items()},
                )
            results[method] = dict(selection=chosen, curves=curves, studies={})
            for study in sorted(set(studies)):
                held = [
                    i
                    for i, r in enumerate(roles)
                    if r != "train" and studies[i] == study
                ]
                if len(held) < 3:
                    continue
                ix = torch.tensor(held, device="cuda")
                matrix = c[ix[:, None], ix[None, :]].detach()
                measured = dict(
                    observed_donors=len(held),
                    distinct_pair_log_growth=float(
                        growth(c, study_pairs(held, studies))
                    ),
                    projections=[],
                )
                for n in (18, 24, 40, 60, 100, 200, 400):
                    for null in (False, True):
                        measured["projections"].append(
                            dict(
                                simulated_donors=n,
                                scenario="product-null" if null else "empirical-joint",
                                **projection(
                                    matrix, n, streams=10000, seed=9203, null=null
                                ),
                            )
                        )
                results[method]["studies"][study] = measured
                print(
                    "HELD",
                    method,
                    study,
                    measured["distinct_pair_log_growth"],
                    flush=True,
                )
        report = dict(
            schema="ecosystem-growth-training-v1",
            status="development-only",
            biological_gate_passed=False,
            selection="mean leave-one-training-study-out native log growth",
            results=results,
            device=torch.cuda.get_device_name(),
            independent_training_donors=len(train),
            independent_development_donors=sum(r != "train" for r in roles),
        )
        (output / "report.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n"
        )
        return report
