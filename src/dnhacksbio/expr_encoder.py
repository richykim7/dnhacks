"""Frozen, non-pickle expression encoders with training provenance.

Fit on a separate cohort only. Raw input is nonnegative TPM; log1p, means,
scales and projection are fixed at training time. Missing genes are imputed
at the stored log-expression mean. Nonfinite measured entries are rejected.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def identifiers(values) -> list[str]:
    """Reject missing identifiers rather than turning None/NaN into donor names."""
    values = list(values)
    if any(isinstance(v, (bool, np.bool_)) or not isinstance(v, (str, int, np.integer))
           or not str(v).strip() for v in values):
        raise ValueError("identifiers must be nonempty strings or integers, without missing values")
    return [str(v) for v in values]


def gene_names(genes) -> tuple[str, ...]:
    names = tuple(identifiers(genes))
    if not names or any(not g.strip() for g in names) or len(set(names)) != len(names):
        raise ValueError("gene identifiers must be nonempty and unique")
    return names


def unit_keys(units, namespace: str) -> list[str]:
    return [hashlib.sha256(json.dumps([namespace, str(u)]).encode()).hexdigest() for u in units]


@dataclass(frozen=True)
class FrozenEncoder:
    genes: tuple[str, ...]
    mean: np.ndarray
    scale: np.ndarray
    weights: tuple[np.ndarray, ...]
    manifest: dict
    identity: str = "in-memory"

    def validate(self) -> None:
        gene_names(self.genes)
        d = len(self.genes)
        if self.mean.shape != (d,) or self.scale.shape != (d,) or np.any(self.scale <= 0):
            raise ValueError("invalid preprocessing dimensions or scales")
        if not all(np.isfinite(a).all() for a in (self.mean, self.scale, *self.weights)):
            raise ValueError("nonfinite encoder parameters")
        kind = self.manifest.get("kind")
        if kind == "pca":
            if len(self.weights) != 1 or self.weights[0].ndim != 2 or self.weights[0].shape[0] != d:
                raise ValueError("invalid PCA dimensions")
        elif kind == "autoencoder":
            if len(self.weights) != 4:
                raise ValueError("autoencoder needs two weights and two biases")
            w1, b1, w2, b2 = self.weights
            if w1.ndim != 2 or w2.ndim != 2 or w1.shape[0] != d or b1.shape != (w1.shape[1],) or w2.shape[0] != w1.shape[1] or b2.shape != (w2.shape[1],):
                raise ValueError("invalid autoencoder dimensions")
        else:
            raise ValueError("unsupported encoder kind")
        if self.manifest.get("schema") != 1 or self.manifest.get("input_scale") != "TPM":
            raise ValueError("unsupported artifact schema or expression units")
        for field in ("source", "sampling", "unit_namespace", "training_unit_keys"):
            if not self.manifest.get(field):
                raise ValueError(f"artifact missing {field}")

    def transform(self, X, *, genes, max_missing_fraction: float = 0.2) -> np.ndarray:
        self.validate()
        names = gene_names(genes)
        X = np.asarray(X, dtype=np.float64)
        if X.ndim != 2 or X.shape[1] != len(names) or not np.isfinite(X).all() or np.any(X < 0):
            raise ValueError("expression matrix must be finite nonnegative TPM with matching genes")
        if not 0 <= max_missing_fraction <= 1:
            raise ValueError("max_missing_fraction must be in [0, 1]")
        index = {g: i for i, g in enumerate(names)}
        missing = sum(g not in index for g in self.genes)
        if missing / len(self.genes) > max_missing_fraction:
            raise ValueError("too many missing encoder genes")
        aligned = np.broadcast_to(self.mean, (len(X), len(self.genes))).copy()
        for j, g in enumerate(self.genes):
            if g in index:
                aligned[:, j] = np.log1p(X[:, index[g]])
        z = (aligned - self.mean) / self.scale
        if self.manifest["kind"] == "pca":
            out = z @ self.weights[0]
        else:
            w1, b1, w2, b2 = self.weights
            out = np.maximum(0, z @ w1 + b1) @ w2 + b2
        if not np.isfinite(out).all():
            raise ValueError("encoder output is nonfinite")
        return out

    def save(self, path: str | Path) -> None:
        self.validate()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            np.savez_compressed(f, genes=np.asarray(self.genes), mean=self.mean, scale=self.scale,
                                manifest=json.dumps(self.manifest, sort_keys=True),
                                **{f"weight_{i}": w for i, w in enumerate(self.weights)})

    @classmethod
    def load(cls, path: str | Path) -> FrozenEncoder:
        path = Path(path)
        with np.load(path, allow_pickle=False) as data:
            manifest = json.loads(str(data["manifest"]))
            n = 1 if manifest.get("kind") == "pca" else 4
            result = cls(tuple(data["genes"].tolist()), data["mean"].copy(), data["scale"].copy(),
                         tuple(data[f"weight_{i}"].copy() for i in range(n)), manifest,
                         hashlib.sha256(path.read_bytes()).hexdigest())
        result.validate()
        for a in (result.mean, result.scale, *result.weights):
            a.flags.writeable = False
        return result


def training_data(X, *, genes, units, source: str, sampling: str, unit_namespace: str):
    names = gene_names(genes)
    X = np.asarray(X, dtype=np.float64)
    units = identifiers(units)
    if X.ndim != 2 or X.shape[1] != len(names) or len(X) < 2 or len(units) != len(X):
        raise ValueError("training matrix, genes, and units must match; need at least two units")
    if len(set(units)) != len(units) or any(not u.strip() for u in units):
        raise ValueError("training inputs must already be one row per identified independent unit")
    if not all(s.strip() for s in (source, sampling, unit_namespace)):
        raise ValueError("source, sampling assumptions, and unit namespace are required")
    if not np.isfinite(X).all() or np.any(X < 0):
        raise ValueError("training input must be finite nonnegative TPM")
    log_x = np.log1p(X)
    mean, scale = log_x.mean(axis=0), log_x.std(axis=0)
    scale[scale == 0] = 1
    manifest = dict(schema=1, input_scale="TPM", source=source, sampling=sampling,
                    unit_namespace=unit_namespace, training_unit_keys=unit_keys(units, unit_namespace),
                    n_units=len(X), numpy_version=np.__version__)
    return names, (log_x - mean) / scale, mean, scale, manifest


def fit_pca(X, *, genes, units, source: str, sampling: str, unit_namespace: str,
            components: int = 64) -> FrozenEncoder:
    names, z, mean, scale, manifest = training_data(
        X, genes=genes, units=units, source=source, sampling=sampling, unit_namespace=unit_namespace)
    if not isinstance(components, int) or not 1 <= components <= min(z.shape[0] - 1, z.shape[1]):
        raise ValueError("PCA components must fit the training matrix rank bound")
    _, _, vh = np.linalg.svd(z, full_matrices=False)
    manifest.update(kind="pca", components=components)
    return FrozenEncoder(names, mean, scale, (vh[:components].T.copy(),), manifest)


def fit_autoencoder(X, *, genes, units, source: str, sampling: str, unit_namespace: str,
                    hidden: int = 512, components: int = 128, mask_fraction: float = 0.15,
                    epochs: int = 100, batch_size: int = 64, lr: float = 1e-3,
                    seed: int = 0, device: str = "cpu", dtype: str = "float64") -> FrozenEncoder:
    """Train a masked-gene autoencoder on the declared external cohort only.

    Fixed epochs; tune settings using separate development data. The saved
    artifact contains the frozen encoder only, not executable pickle content.
    """
    import torch
    from torch import nn
    from dnhacksbio.evalue_device import execution

    device, precision, execution_metadata = execution(device, dtype)

    names, z, mean, scale, manifest = training_data(
        X, genes=genes, units=units, source=source, sampling=sampling, unit_namespace=unit_namespace)
    if any(type(v) is not int or v < 1 for v in (hidden, components, epochs, batch_size)):
        raise ValueError("network widths, epochs, and batch_size must be positive integers")
    if not 0 < mask_fraction < 1 or not np.isfinite(lr) or lr <= 0:
        raise ValueError("invalid masking or learning rate")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("invalid seed")
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(seed)
        encoder = nn.Sequential(nn.Linear(z.shape[1], hidden), nn.ReLU(), nn.Linear(hidden, components)).to(device=device, dtype=precision)
        decoder = nn.Sequential(nn.Linear(components, hidden), nn.ReLU(), nn.Linear(hidden, z.shape[1])).to(device=device, dtype=precision)
        optimizer = torch.optim.Adam([*encoder.parameters(), *decoder.parameters()], lr=lr)
        x = torch.tensor(z, dtype=precision, device=device)
        losses = []
        for _ in range(epochs):
            order = torch.randperm(len(x)).to(device)
            total, count = 0.0, 0
            for start in range(0, len(x), batch_size):
                target = x[order[start:start + batch_size]]
                mask = (torch.rand(target.shape) < mask_fraction).to(device)
                if not mask.any():
                    continue
                damaged = target.masked_fill(mask, 0.0)
                optimizer.zero_grad()
                loss = (decoder(encoder(damaged)) - target)[mask].square().mean()
                if not torch.isfinite(loss):
                    raise ValueError("nonfinite autoencoder loss")
                loss.backward()
                optimizer.step()
                total += float(loss.detach()) * int(mask.sum())
                count += int(mask.sum())
            losses.append(total / count if count else 0.0)
        weights = (encoder[0].weight.detach().cpu().numpy().T.copy(), encoder[0].bias.detach().cpu().numpy().copy(),
                   encoder[2].weight.detach().cpu().numpy().T.copy(), encoder[2].bias.detach().cpu().numpy().copy())
    manifest.update(kind="autoencoder", hidden=hidden, components=components, mask_fraction=mask_fraction,
                    epochs=epochs, batch_size=batch_size, lr=lr, seed=seed, training_loss=losses,
                    torch_version=torch.__version__, execution=execution_metadata)
    result = FrozenEncoder(names, mean, scale, weights, manifest)
    result.validate()
    return result
