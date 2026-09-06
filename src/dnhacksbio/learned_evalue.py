"""Standalone two-sample DAVT diagnostics; never a biological verification verdict.

Null: equal distributions of independent, identically distributed units in
independent groups. A deterministic frozen representation and a predictable
antisymmetric payoff give conditionally fair scores. Unique IDs alone do not
establish independence. See plans/PLAN-learned-evalue.md and research/.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import math
import platform

import numpy as np
import torch
from torch import nn

from dnhacksbio.evalues import from_log
from dnhacksbio.evalue_device import execution
from dnhacksbio.expr_encoder import FrozenEncoder, gene_names, identifiers, unit_keys


@dataclass(frozen=True)
class LearnedEConfig:
    batch_pairs: int = 8
    burn_in: int = 2
    hidden: tuple[int, ...] = (64, 64)
    lr: float = 5e-4
    patience: int = 10
    max_epochs: int = 500
    weight_decay: float = 1e-2
    tanh_clip: float = 4.0
    seed: int = 0
    encoder: str | None = None
    max_missing_fraction: float = 0.2
    device: str = "cpu"
    dtype: str = "float64"
    pairing: str = "shuffle"  # in_order supports predeclared fixed unordered-pair audits

    def validate(self):
        if self.pairing not in {"shuffle", "in_order"}:
            raise ValueError("pairing must be shuffle or in_order")
        for name in ("batch_pairs", "patience", "max_epochs"):
            v = getattr(self, name)
            if type(v) is not int or v < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.burn_in != 2:
            raise ValueError("initial implementation requires exactly two burn-in batches")
        if type(self.seed) is not int or not 0 <= self.seed < 2**32:
            raise ValueError("seed must be an integer in [0, 2**32)")
        if any(type(h) is not int or h < 1 for h in self.hidden):
            raise ValueError("hidden widths must be positive integers")
        if not math.isfinite(self.lr) or self.lr <= 0 or not math.isfinite(self.weight_decay) or self.weight_decay < 0:
            raise ValueError("invalid optimizer settings")
        if not math.isfinite(self.tanh_clip) or not 0 < self.tanh_clip <= 4:
            raise ValueError("tanh_clip must be in (0, 4] to keep every score strictly positive")
        if not math.isfinite(self.max_missing_fraction) or not 0 <= self.max_missing_fraction < 1:
            raise ValueError("max_missing_fraction must be in [0, 1)")


@dataclass(frozen=True)
class SamplingContract:
    mode: str  # expression, aggregated, or synthetic
    source: str
    assumptions: str
    unit_namespace: str = ""
    input_scale: str = "features"
    aggregation: str = "reject"  # or predeclared mean_tpm for technical replicates

    def validate(self):
        if self.mode not in {"expression", "aggregated", "synthetic"}:
            raise ValueError("declare expression, aggregated, or synthetic independent-unit mode")
        if not self.source.strip() or not self.assumptions.strip():
            raise ValueError("document data source and independent-unit sampling assumptions")
        if self.input_scale not in {"features", "TPM"}:
            raise ValueError("input scale must be features or TPM")
        if self.mode != "synthetic" and not self.unit_namespace.strip():
            raise ValueError("real inputs need a documented unit namespace")
        if self.mode == "expression" and self.input_scale != "TPM":
            raise ValueError("initial expression support requires TPM")
        if self.aggregation not in {"reject", "mean_tpm"}:
            raise ValueError("unsupported aggregation")
        if self.aggregation == "mean_tpm" and self.input_scale != "TPM":
            raise ValueError("mean_tpm aggregation requires TPM inputs")


@dataclass
class LearnedE:
    e_value: float | None
    status: str
    reason: str
    per_batch: list[float]
    log_wealth_path: list[float]
    n_pairs: int
    n_batches: int
    n_scored: int  # scored batches, not donors or pairs
    config: LearnedEConfig
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _units(X, ids, *, group: str, contract: SamplingContract):
    if ids is None:
        if contract.mode != "synthetic":
            raise ValueError("real inputs require unit IDs, including already aggregated inputs")
        ids = [f"synthetic-{group}-{i}" for i in range(len(X))]
    ids = identifiers(ids)
    if len(ids) != len(X) or any(not i.strip() for i in ids):
        raise ValueError("unit IDs must be nonempty and match input rows")
    unique = list(dict.fromkeys(ids))
    if len(unique) != len(ids):
        if contract.aggregation != "mean_tpm":
            raise ValueError("repeated units require an explicit compatible aggregation protocol")
        lookup = {u: j for j, u in enumerate(unique)}
        total = np.zeros((len(unique), X.shape[1]), dtype=np.float64)
        counts = np.zeros(len(unique), dtype=np.int64)
        for row, u in zip(X, ids):
            total[lookup[u]] += row
            counts[lookup[u]] += 1
        X = total / counts[:, None]
    return X, unique


def _network(dim: int, hidden: tuple[int, ...]) -> nn.Module:
    layers = []
    for width in hidden:
        layers.extend((nn.Linear(dim, width), nn.ReLU()))
        dim = width
    layers.append(nn.Linear(dim, 1))
    return nn.Sequential(*layers).double()


def _log_payoffs(model, a, b, clip):
    d = torch.clamp(model(a).flatten() - model(b).flatten(), -clip, clip)
    # log(1+tanh(d)) = log(2) - softplus(-2*d), avoiding cancellation.
    return math.log(2) - torch.nn.functional.softplus(-2 * d)


def _fit(model, train_a, train_b, val_a, val_b, config):
    optimizer = torch.optim.Adam(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    model.eval()
    with torch.no_grad():
        best = float(-_log_payoffs(model, val_a, val_b, config.tanh_clip).mean())
    saved = {k: v.detach().clone() for k, v in model.state_dict().items()}
    stale = 0
    for epoch in range(config.max_epochs):
        model.train()
        optimizer.zero_grad()
        loss = -_log_payoffs(model, train_a, train_b, config.tanh_clip).mean()
        if not torch.isfinite(loss):
            raise ValueError("nonfinite training loss")
        loss.backward()
        optimizer.step()
        model.eval()
        with torch.no_grad():
            score = float(-_log_payoffs(model, val_a, val_b, config.tanh_clip).mean())
        if not math.isfinite(score):
            raise ValueError("nonfinite validation loss")
        if score < best:
            best = score
            saved = {k: v.detach().clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
        if stale >= config.patience:
            break
    model.load_state_dict(saved)
    model.eval()
    return epoch + 1


def learned_two_sample_e(Xa, Xb, *, genes, sampling: SamplingContract,
                         unit_a=None, unit_b=None, config=LearnedEConfig()) -> LearnedE:
    """Return final wealth and its path, or unavailable for insufficient units.

    Invalid contracts/data raise ValueError. No data-dependent retries, seed
    selection, feature selection, or evidence-source selection are performed.
    Device and precision are explicit (CPU/float64 by default). Model initialization
    uses the CPU RNG in an isolated scope; CUDA RNG state is never consumed.
    """
    config.validate()
    device, dtype, execution_metadata = execution(config.device, config.dtype)
    sampling.validate()
    genes = gene_names(genes)
    a, b = np.asarray(Xa, dtype=np.float64), np.asarray(Xb, dtype=np.float64)
    for x in (a, b):
        if x.ndim != 2 or x.shape[1] != len(genes) or not np.isfinite(x).all():
            raise ValueError("matrices must be finite, two-dimensional, and match gene identifiers")
        if sampling.input_scale == "TPM" and np.any(x < 0):
            raise ValueError("TPM must be nonnegative")
    n_rows = [len(a), len(b)]
    input_hashes = [hashlib.sha256(np.ascontiguousarray(x, dtype="<f8").tobytes()).hexdigest() for x in (a, b)]
    a, ids_a = _units(a, unit_a, group="a", contract=sampling)
    b, ids_b = _units(b, unit_b, group="b", contract=sampling)
    if set(ids_a) & set(ids_b):
        raise ValueError("a unit occurs in both groups; independent-group construction is unsupported")
    if sampling.input_scale == "TPM" and config.encoder is None:
        raise ValueError("TPM inputs require a frozen external encoder artifact")
    artifact = "identity:predeclared-features"
    missing_genes = []
    if config.encoder is not None:
        if sampling.input_scale != "TPM":
            raise ValueError("expression encoder expects TPM, not precomputed features")
        encoder = FrozenEncoder.load(config.encoder)
        training_keys = set(encoder.manifest["training_unit_keys"])
        if training_keys.intersection(unit_keys(ids_a + ids_b, sampling.unit_namespace)):
            raise ValueError("evaluation units overlap encoder training units")
        a = encoder.transform(a, genes=genes, max_missing_fraction=config.max_missing_fraction)
        b = encoder.transform(b, genes=genes, max_missing_fraction=config.max_missing_fraction)
        artifact = encoder.identity
        missing_genes = [g for g in encoder.genes if g not in genes]
    rng = np.random.default_rng(config.seed)
    if config.pairing == "shuffle":
        order_a, order_b = rng.permutation(len(a)), rng.permutation(len(b))
    else:
        order_a, order_b = np.arange(len(a)), np.arange(len(b))
    n = min(len(a), len(b))
    metadata = dict(null="equal distributions of independent units in independent groups",
                    diagnostic_only=True, sampling=asdict(sampling), artifact=artifact,
                    missing_genes=missing_genes, input_rows=n_rows, independent_units=[len(a), len(b)],
                    input_sha256=input_hashes, genes=list(genes),
                    dropped_units=[], unused_a=[ids_a[i] for i in order_a[n:]],
                    unused_b=[ids_b[i] for i in order_b[n:]],
                    pair_order=[[ids_a[i], ids_b[j]] for i, j in zip(order_a[:n], order_b[:n])],
                    software=dict(python=platform.python_version(), numpy=np.__version__, torch=torch.__version__),
                    execution=execution_metadata, training_updates=[], scored_pairs=0)
    nb = math.ceil(n / config.batch_pairs)
    if n < (config.burn_in + 4) * config.batch_pairs:
        return LearnedE(None, "unavailable", "need two burn-in and four full scoring batches",
                        [], [0.0], n, nb, 0, config, metadata)
    a = torch.tensor(a[order_a[:n]], dtype=dtype, device=device)
    b = torch.tensor(b[order_b[:n]], dtype=dtype, device=device)
    batch_size = config.batch_pairs
    logs, factors = [0.0], []
    # Only CPU RNG is used. No global NumPy seed or thread-count changes.
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(config.seed)
        model = _network(a.shape[1], config.hidden).to(device=device, dtype=dtype)
        for batch in range(2, nb):
            train_end = (batch - 1) * batch_size
            val_end = batch * batch_size
            epochs = _fit(model, a[:train_end], b[:train_end], a[train_end:val_end], b[train_end:val_end], config)
            metadata["training_updates"].append(dict(
                before_scoring_batch=batch + 1, training_batches=list(range(1, batch)),
                validation_batch=batch, epochs=epochs))
            end = min(n, val_end + batch_size)
            with torch.no_grad():
                log_s = float(_log_payoffs(model, a[val_end:end], b[val_end:end], config.tanh_clip).sum())
            if not math.isfinite(log_s):
                raise ValueError("nonfinite scoring payoff")
            factors.append(from_log(log_s))
            logs.append(logs[-1] + log_s)
            metadata["scored_pairs"] += end - val_end
    metadata["log_final_wealth"] = logs[-1]
    metadata["scored_batch_numbers"] = list(range(3, nb + 1))
    return LearnedE(from_log(logs[-1]), "ok", "standalone diagnostic; final wealth",
                    factors, logs, n, nb, len(factors), config, metadata)
