"""Frozen mask-aware protein PCA/denoising encoders. NPZ arrays, never pickle or TPM."""
from __future__ import annotations

from dataclasses import dataclass
import json
import platform
import resource
import time
import fcntl
import numpy as np

from .protein_design import digest, donor_keys, validate


def matrix(cohort, features):
    positions = {f: i for i, f in enumerate(cohort["feature_ids"])}
    x = np.zeros((len(cohort["observations"]), len(features)))
    mask = np.zeros_like(x, dtype=bool)
    for j, f in enumerate(features):
        if f in positions:
            k = positions[f]
            for i, row in enumerate(cohort["observations"]):
                mask[i, j] = row["mask"][k]
                x[i, j] = row["values"][k] if mask[i, j] else 0
    if cohort["scale"] == "linear_abundance":
        x = np.log2(1 + x)
    return x, mask


@dataclass
class ProteinEncoder:
    metadata: dict
    arrays: dict

    @property
    def sha256(self):
        return digest({"metadata": self.metadata, "arrays": {k: v.tolist() for k, v in self.arrays.items()}})

    def inputs(self, cohort):
        validate(cohort, discovery=True)
        if cohort["assay"] != self.metadata["assay"] or cohort["scale"] != self.metadata["scale"]:
            raise ValueError("Assay transfer requires a separately frozen and validated transform")
        x, mask = matrix(cohort, self.metadata["feature_ids"])
        if np.any(mask.mean(axis=1) < self.metadata["min_coverage"]):
            raise ValueError("Insufficient measured encoder coverage")
        z = np.where(mask, (x - self.arrays["center"]) / self.arrays["scale"], 0)
        return np.concatenate((z, mask.astype(float)), axis=1)

    def transform(self, cohort):
        x = self.inputs(cohort)
        if self.metadata["kind"] == "pca":
            return (x - self.arrays["input_center"]) @ self.arrays["components"].T
        hidden = np.maximum(0, x @ self.arrays["w1"].T + self.arrays["b1"])
        return hidden @ self.arrays["w2"].T + self.arrays["b2"]

    def reconstruct_inputs(self, inputs):
        """Reconstruct standardized abundance from value+mask inputs, including hidden-entry tests."""
        p = len(self.metadata["feature_ids"])
        x = np.asarray(inputs)
        if x.ndim != 2 or x.shape[1] != 2*p or not np.isfinite(x).all():
            raise ValueError("Invalid masked reconstruction inputs")
        if self.metadata["kind"] == "pca":
            z = (x - self.arrays["input_center"]) @ self.arrays["components"].T
            return (z @ self.arrays["components"] + self.arrays["input_center"])[:, :p]
        z = np.maximum(0, x @ self.arrays["w1"].T + self.arrays["b1"])
        z = z @ self.arrays["w2"].T + self.arrays["b2"]
        return z @ self.arrays["wd"].T + self.arrays["bd"]

    def save(self, path):
        with open(path, "xb") as stream:
            np.savez_compressed(stream, metadata=np.array(json.dumps(self.metadata, sort_keys=True)),
                                artifact_sha256=np.array(self.sha256), **self.arrays)

    @classmethod
    def load(cls, path):
        with np.load(path, allow_pickle=False) as data:
            metadata = json.loads(str(data["metadata"]))
            arrays = {k: data[k].copy() for k in data.files if k not in {"metadata", "artifact_sha256"}}
            obj = cls(metadata, arrays)
            if metadata.get("schema") != "ProteinEncoder-v1" or str(data["artifact_sha256"]) != obj.sha256:
                raise ValueError("Encoder integrity failure")
        p = len(metadata["feature_ids"])
        if metadata["kind"] not in {"pca", "denoising"} or any(not np.isfinite(a).all() for a in arrays.values()):
            raise ValueError("Invalid encoder arrays")
        if arrays["center"].shape != (p,) or arrays["scale"].shape != (p,) or np.any(arrays["scale"] <= 0):
            raise ValueError("Invalid transform")
        if metadata["kind"] == "pca":
            valid = arrays["input_center"].shape == (2*p,) and arrays["components"].shape == (metadata["latent"], 2*p)
        else:
            valid = all(arrays[k].shape == s for k, s in {
                "w1": (256, 2*p), "b1": (256,), "w2": (metadata["latent"], 256),
                "b2": (metadata["latent"],), "wd": (p, metadata["latent"]), "bd": (p,)}.items())
        if not valid:
            raise ValueError("Encoder shape mismatch")
        return obj


def fit(train, validation, **kwargs):
    """GPU work holds the agreed host lease for the complete training call."""
    device = kwargs.get("device", "cpu")
    if device not in {"cpu", "cuda"}:
        raise ValueError("Use cpu or cuda")
    if device == "cpu":
        return _fit(train, validation, **kwargs)
    with open("/tmp/dnhacks-gpu.lock", "a") as lease:
        # Blocking acquisition is deliberate: no heartbeat can expire a live worker.
        fcntl.flock(lease, fcntl.LOCK_EX)
        return _fit(train, validation, **kwargs)


def _fit(train, validation, *, kind="pca", latent=32, min_coverage=0.8, feature_coverage=0.8,
         max_features=8000, seed=0, epochs=50, corruption=0.2, device="cpu"):
    """Development training; feature selection/normalization use TRAIN only."""
    started = time.monotonic()
    validate(train, discovery=True)
    validate(validation, discovery=True)
    if train["role"] != "TRAIN" or validation["role"] != "VALIDATION":
        raise ValueError("Explicit TRAIN and VALIDATION required")
    if train["donor_namespace"] != validation["donor_namespace"]:
        raise ValueError("Harmonize donor namespace before checking train/validation overlap")
    if set(donor_keys(train)) & set(donor_keys(validation)):
        raise ValueError("Training/validation donor overlap")
    if train["cohort_id"] == validation["cohort_id"]:
        raise ValueError("Reserve an entire cohort for validation")
    if any(r["histology"] == "PDAC" for c in (train, validation) for r in c["observations"]):
        raise ValueError("First encoder requires non-PDAC training/validation")
    if any(not r["qc"]["pass"] for c in (train, validation) for r in c["observations"]):
        raise ValueError("Exclude failed assay QC before training")
    if kind not in {"pca", "denoising"} or type(latent) is not int or latent < 1:
        raise ValueError("Invalid architecture")
    if not 0 < min_coverage <= 1 or not 0 < feature_coverage <= 1 or not 0 < corruption < 1:
        raise ValueError("Invalid coverage/corruption")
    if type(max_features) is not int or not 1 <= max_features <= 8000 or type(epochs) is not int or not 1 <= epochs <= 1000:
        raise ValueError("Invalid training budget")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("Invalid seed")
    x, mask = matrix(train, train["feature_ids"])
    indices = np.flatnonzero(mask.mean(axis=0) >= feature_coverage)[:max_features]
    if not len(indices):
        raise ValueError("No measured training features")
    features = [train["feature_ids"][i] for i in indices]
    x, mask = x[:, indices], mask[:, indices]
    center = np.sum(x * mask, axis=0) / mask.sum(axis=0)
    scale = np.sqrt(np.sum(np.where(mask, (x-center)**2, 0), axis=0) / mask.sum(axis=0))
    scale[scale < 1e-8] = 1
    meta = {"schema": "ProteinEncoder-v1", "kind": kind, "feature_ids": features,
            "feature_sha256": digest(features), "assay": train["assay"], "scale": train["scale"],
            "transform": "log2(1+x) for linear abundance; training center/scale; zero impute; mask channel",
            "training_donor_keys": donor_keys(train), "validation_donor_keys": donor_keys(validation),
            "training_sha256": digest(train), "validation_sha256": digest(validation),
            "min_coverage": min_coverage, "feature_coverage": feature_coverage, "latent": latent,
            "seed": seed, "software": {"python": platform.python_version(), "numpy": np.__version__},
            "status": "exploratory", "objective": "observed-entry reconstruction"}
    encoder = ProteinEncoder(meta, {"center": center, "scale": scale})
    a, b = encoder.inputs(train), encoder.inputs(validation)
    if kind == "pca":
        mean = a.mean(axis=0)
        _, _, vt = np.linalg.svd(a-mean, full_matrices=False)
        if latent > len(vt):
            raise ValueError("PCA latent exceeds available training rank")
        encoder.arrays.update(input_center=mean, components=vt[:latent])
        predicted = ((b-mean) @ vt[:latent].T) @ vt[:latent] + mean
    else:
        if not 2000 <= len(features) <= 8000 or latent not in {32, 64}:
            raise ValueError("Denoising requires 2000–8000 features and latent 32 or 64")
        import torch
        from torch import nn
        if device == "cuda":
            if not torch.cuda.is_available():
                raise ValueError("CUDA unavailable")
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.set_per_process_memory_fraction(16 * 1024**3 / torch.cuda.get_device_properties(0).total_memory)
        meta["software"]["torch"] = torch.__version__
        meta["training_dtype"] = "float32"
        with torch.random.fork_rng(devices=[]):
            torch.random.default_generator.manual_seed(seed)
            network = nn.Sequential(nn.Linear(2*len(features), 256), nn.ReLU(),
                                    nn.Linear(256, latent), nn.Linear(latent, len(features))).to(device)
            optimizer = torch.optim.AdamW(network.parameters(), lr=0.001)
            at = torch.tensor(a, dtype=torch.float32, device=device)
            bt = torch.tensor(b, dtype=torch.float32, device=device)
            # Fixed blinded observed entries for checkpoint selection. No PDAC/model-choice feedback.
            validation_rng = np.random.default_rng(seed + 1)
            held = (validation_rng.random(b[:, len(features):].shape) < corruption) & b[:, len(features):].astype(bool)
            if not held.any():
                raise ValueError("No validation entries to hold out")
            held_t = torch.tensor(held, device=device)
            validation_input = bt.clone()
            validation_input[:, :len(features)][held_t] = 0
            validation_input[:, len(features):][held_t] = 0
            epoch_times = []
            best, selected = float("inf"), None
            for epoch in range(epochs):
                if time.monotonic() - started > 1800:
                    raise ValueError("Pilot exceeded 30-minute cap")
                epoch_start = time.monotonic()
                network.train()
                for batch in torch.randperm(len(at)).split(32):
                    original = at[batch.to(device)]
                    observed = original[:, len(features):].bool()
                    keep = observed & (torch.rand(observed.shape).to(device) >= corruption)
                    corrupted = torch.cat((original[:, :len(features)] * keep, keep.float()), dim=1)
                    error = network(corrupted) - original[:, :len(features)]
                    loss = error[observed].square().mean()
                    if not torch.isfinite(loss):
                        raise ValueError("Nonfinite reconstruction")
                    optimizer.zero_grad(); loss.backward(); optimizer.step()
                network.eval()
                with torch.no_grad():
                    error = network(validation_input) - bt[:, :len(features)]
                    score = float(error[held_t].square().mean())
                if score < best:
                    best, selected = score, {k: v.detach().clone() for k, v in network.state_dict().items()}
                    meta["selected_epoch"] = epoch + 1
                epoch_times.append(time.monotonic() - epoch_start)
            if selected is None:
                raise ValueError("No finite validation checkpoint")
            network.load_state_dict(selected)
            with torch.no_grad():
                predicted = network(bt).cpu().numpy()
            for prefix, layer in (("1", network[0]), ("2", network[2]), ("d", network[3])):
                encoder.arrays["w"+prefix] = layer.weight.detach().cpu().numpy().copy()
                encoder.arrays["b"+prefix] = layer.bias.detach().cpu().numpy().copy()
        meta.update(corruption=corruption, max_epochs=epochs, validation_hidden_mse=best,
                    validation_hidden_entries=int(held.sum()), epoch_seconds=epoch_times,
                    peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated() if device == "cuda" else 0,
                    peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved() if device == "cuda" else 0)
    observed = b[:, len(features):].astype(bool)
    meta["validation_masked_mse"] = float(np.mean((predicted[:, :len(features)] - b[:, :len(features)])[observed]**2))
    meta["elapsed_seconds"] = time.monotonic() - started
    meta["process_peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    meta["weights_bytes"] = sum(a.nbytes for a in encoder.arrays.values())
    meta["device"] = device
    meta["training_donors_per_second"] = len(a) / meta["elapsed_seconds"]
    meta["preprocessing_sha256"] = digest({"transform": meta["transform"], "features": features,
                                             "center": center.tolist(), "scale": scale.tolist()})
    return encoder
