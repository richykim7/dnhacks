"""CUDA diagnostics of the actual bounded donor kernel on frozen development views.

Empirical resampling is a conditional power projection, not new biological donors
or a private confirmation certificate. Model selection uses training donors only.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
from pathlib import Path

import numpy as np

from .ecosystem_cuda import require_cuda
from .ecosystem_simulations import summarize


def load_views(root):
    import torch

    root = Path(root)
    packs = []
    for name in ("epithelial-enriched", "fibroblast"):
        with np.load(root / f"{name}-donor-summaries.npz", allow_pickle=False) as z:
            packs.append({k: z[k].copy() for k in z.files})
    shared = sorted(set(packs[0]["donors"]) & set(packs[1]["donors"]))
    views = []
    for pack in packs:
        ix = [pack["donors"].tolist().index(d) for d in shared]
        views.append(torch.as_tensor(pack["values"][ix], device="cuda"))
    positions = [packs[0]["donors"].tolist().index(d) for d in shared]
    roles = packs[0]["roles"][positions].tolist()
    studies = packs[0]["studies"][positions].tolist()
    for pack in packs[1:]:
        ix = [pack["donors"].tolist().index(d) for d in shared]
        if (
            pack["roles"][ix].tolist() != roles
            or pack["studies"][ix].tolist() != studies
        ):
            raise ValueError("Compartment donor roles or study identities disagree")
    train = torch.tensor(
        [i for i, role in enumerate(roles) if role == "train"], device="cuda"
    )
    normalized = [
        (v - v[train].mean(0)) / v[train].std(0).clamp_min(0.1) for v in views
    ]
    return *normalized, train, roles, studies


def bounded_kernel(c, x1, y1, x2, y2):
    return (c[x1, y1] + c[x2, y2] - c[x1, y2] - c[x2, y1]) / 4


def projection(c, donors, *, streams, seed, null=False):
    """Independent draws from a fixed empirical joint/product distribution."""
    import torch

    if streams < 10000 or donors < 2:
        raise ValueError("At least 10000 streams and two donors required")
    if c.ndim != 2 or c.shape[0] != c.shape[1] or len(c) < 2:
        raise ValueError("Square frozen donor score matrix required")
    if not torch.isfinite(c).all() or c.abs().max() > 1:
        raise ValueError("Frozen critic must be finite and bounded by one")
    generator = torch.Generator(device=c.device).manual_seed(seed)
    shape = (streams, donors // 2, 2)
    x = torch.randint(len(c), shape, device=c.device, generator=generator)
    y = (
        torch.randint(len(c), shape, device=c.device, generator=generator)
        if null
        else x
    )
    h = bounded_kernel(c, x[:, :, 0], y[:, :, 0], x[:, :, 1], y[:, :, 1])
    logw = torch.log1p(0.9 * h).cumsum(1)
    result = summarize(logw.cpu().numpy())
    result["mean_block_h"] = float(h.mean())
    result["mean_block_log_growth"] = float(torch.log1p(0.9 * h).mean())
    return result


def diagnose(
    root,
    output,
    *,
    streams=10000,
    budgets=(18, 24, 40, 60, 100, 200, 400, 800),
    seed=9101,
):
    import torch

    require_cuda()
    root, output = Path(root), Path(output)
    with Path("/tmp/dnhacks-gpu.lock").open("a+") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        torch.set_num_threads(2)
        x, y, train, roles, studies = load_views(root)
        pairs = torch.cartesian_prod(
            torch.arange(len(x), device="cuda"), torch.arange(len(x), device="cuda")
        )
        raw = {}
        for s in (2701, 2702, 2703):
            model = torch.nn.Sequential(
                torch.nn.Linear(x.shape[1] + y.shape[1], 64),
                torch.nn.SiLU(),
                torch.nn.Dropout(0.3),
                torch.nn.Linear(64, 1),
            ).cuda()
            with np.load(root / f"association-{s}.npz", allow_pickle=False) as z:
                model.load_state_dict(
                    {
                        k: torch.from_numpy(z["critic." + k]).cuda()
                        for k in model.state_dict()
                    }
                )
            model.eval()
            with torch.no_grad():
                raw[f"neural-{s}"] = model(
                    torch.cat([x[pairs[:, 0]], y[pairs[:, 1]]], 1)
                ).reshape(len(x), len(x))
        raw["bilinear"] = x @ (x[train].T @ y[train] / len(train)) @ y.T
        # Scale selection uses only same-study training donor pairs. No held-out
        # power result participates in critic/temperature selection.
        training_pairs = [
            (i, j)
            for i in train.tolist()
            for j in train.tolist()
            if i != j and studies[i] == studies[j]
        ]
        i, j = (torch.tensor(v, device="cuda") for v in zip(*training_pairs))
        groups = {
            s: [
                i
                for i, (r, st) in enumerate(zip(roles, studies))
                if r != "train" and st == s
            ]
            for s in sorted(set(studies))
        }
        groups = {s: ix for s, ix in groups.items() if len(ix) >= 3}
        records, scales = [], {}
        for name, matrix in raw.items():
            magnitude = matrix[train[:, None], train[None, :]].std().clamp_min(1e-6)
            choices = []
            for scale in (0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0):
                c = torch.tanh(matrix / magnitude * scale)
                growth = float(torch.log1p(0.9 * bounded_kernel(c, i, i, j, j)).mean())
                choices.append((growth, scale))
            _, scale = max(choices)
            c = torch.tanh(matrix / magnitude * scale)
            scales[name] = dict(
                scale=scale,
                training_score_std=float(magnitude),
                training_log_growth=max(choices)[0],
            )
            for study, ix in groups.items():
                ix = torch.tensor(ix, device="cuda")
                frozen = c[ix[:, None], ix[None, :]]
                for n in budgets:
                    for null in (False, True):
                        measured = projection(
                            frozen, n, streams=streams, seed=seed, null=null
                        )
                        record = dict(
                            critic=name,
                            study=study,
                            observed_donors=len(ix),
                            simulated_donors=n,
                            scenario="product-null" if null else "empirical-joint",
                            **measured,
                        )
                        records.append(record)
                        if n in (18, 100, 800) and not null:
                            print(
                                name,
                                study,
                                n,
                                measured["anytime_rejection"],
                                measured["mean_block_log_growth"],
                                flush=True,
                            )
        result = dict(
            schema="ecosystem-frozen-critic-power-v1",
            status="conditional-development-projection",
            biological_gate_passed=False,
            alpha=0.05,
            streams=streams,
            seed=seed,
            device=torch.cuda.get_device_name(),
            scales=scales,
            records=records,
            inputs={
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(root.glob("*.npz"))
            },
            limitations=[
                "Empirical resampling does not create independent biological donors.",
                "Small observed study samples make biological power uncertain.",
                "Training fits and critic scale selection exclude the held-out projection cohorts.",
                "The native two-donor /4 kernel and stake .9 are unchanged.",
            ],
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
        return result
