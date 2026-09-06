"""Development comparisons of frozen protein views, at identical donor folds."""
from __future__ import annotations

import json
from pathlib import Path
import urllib.request
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, balanced_accuracy_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from .protein_data import read_matrix
from .protein_design import digest, donor_keys, load
from .protein_encoder import ProteinEncoder

MODULES = {"mitotic": ["NUAK1", "PPP1R12A", "PPP1CB", "GSK3B", "PLK4", "ATM", "ATR", "KIFC1"],
           "stress_redox": ["NFE2L2", "CPEB1", "NQO1", "HMOX1", "GPX4"],
           "integrin_fak": ["ITGB1", "ITGA5", "PTK2"]}


def panel_mapping(path):
    path = Path(path)
    if path.exists():
        return load(path)
    entries = {}
    for symbol in sum(MODULES.values(), []):
        url = f"https://rest.ensembl.org/lookup/symbol/homo_sapiens/{symbol}?content-type=application/json"
        with urllib.request.urlopen(url, timeout=30) as stream:
            value = json.load(stream)
        entries[symbol] = {"id": value["id"], "source": url, "response_sha256": digest(value)}
    result = {"version": "protein-mitotic-stress-integrin-v1", "modules": MODULES, "entries": entries}
    with path.open("x") as stream:
        json.dump(result, stream, indent=2)
    return result


def ranks(x, mask):
    out = np.zeros_like(x)
    for i in range(len(x)):
        observed = mask[i].astype(bool)
        out[i, observed] = rankdata(x[i, observed], method="average") / (observed.sum() + 1)
    return out


def evaluate(root, raw, panel):
    root, raw = Path(root), Path(raw)
    train, validation, dev = (load(root / f"{role}.json") for role in ("train", "validation", "dev"))
    models = {"pca": ProteinEncoder.load(root / "pca.npz"),
              "denoiser": ProteinEncoder.load(root / "denoiser-seed0.npz")}
    a, v, d = (models["pca"].inputs(c) for c in (train, validation, dev))
    p = a.shape[1] // 2
    rng = np.random.default_rng(20260906)
    held = (rng.random((len(v), p)) < .2) & v[:, p:].astype(bool)
    blinded = v.copy()
    blinded[:, :p][held] = 0
    blinded[:, p:][held] = 0
    reconstruction = {"training_mean": {"hidden_mse": float(np.mean(v[:, :p][held]**2))}}
    for name, model in models.items():
        prediction = model.reconstruct_inputs(blinded)
        reconstruction[name] = {"hidden_mse": float(np.mean((prediction[held]-v[:, :p][held])**2)),
                                "model_sha256": model.sha256}
    ranked_train = ranks(a[:, :p], a[:, p:])
    rank_model = PCA(n_components=32, svd_solver="randomized", random_state=0).fit(ranked_train)
    ranked_val = ranks(v[:, :p], v[:, p:])
    ranked_blind = ranks(blinded[:, :p], blinded[:, p:])
    rank_pred = rank_model.inverse_transform(rank_model.transform(ranked_blind))
    reconstruction["rank_pca"] = {"rank_hidden_mse": float(np.mean((rank_pred[held]-ranked_val[held])**2)),
        "rank_training_mean_hidden_mse": float(np.mean((np.broadcast_to(ranked_train.mean(0), ranked_val.shape)[held]-ranked_val[held])**2)),
        "note": "rank-scale loss is not comparable to standardized abundance loss"}
    raw_dev = read_matrix(raw / "PDAC_proteomics.txt").reindex([r["donor_id"] for r in dev["observations"]])
    raw_train = pd.concat([read_matrix(raw / f"{c}_proteomics.txt") for c in ("BRCA", "COAD")])
    module_values, coverage = [], {}
    for module, symbols in panel["modules"].items():
        cols = []
        coverage[module] = {}
        for symbol in symbols:
            base_id = panel["entries"][symbol]["id"]
            matches = [c for c in raw_train.columns if c.split(".")[0] == base_id]
            measured = len(matches) == 1 and matches[0] in raw_dev.columns
            coverage[module][symbol] = {"annotation_id": base_id, "resolved": len(matches) == 1,
                "measured_dev_donors": int(raw_dev[matches[0]].notna().sum()) if measured else 0}
            if not measured:
                continue
            feature = matches[0]
            center, scale = raw_train[feature].mean(), raw_train[feature].std(ddof=0)
            if not np.isfinite(center) or not np.isfinite(scale) or scale < 1e-8:
                continue
            cols.append(((raw_dev[feature]-center)/scale).to_numpy())
        values = np.array(cols).T if cols else np.empty((len(raw_dev), 0))
        counts = np.isfinite(values).sum(axis=1)
        module_values.append(np.divide(np.nansum(values, axis=1), counts, out=np.zeros(len(raw_dev)), where=counts>0))
    module_values = np.array(module_values).T
    views = {"fixed_modules": module_values, "missingness_only": d[:, p:],
             "linear_abundance": d[:, :p], "kernel_abundance": d[:, :p],
             "pca": models["pca"].transform(dev), "denoiser": models["denoiser"].transform(dev),
             "rank_pca": rank_model.transform(ranks(d[:, :p], d[:, p:]))}
    indices = np.array([i for i, r in enumerate(dev["observations"]) if r["grade"] in {"G1", "G2", "G3"}])
    y = np.array([int(dev["observations"][i]["grade"] == "G3") for i in indices])
    folds = list(StratifiedKFold(n_splits=5, shuffle=True, random_state=0).split(indices, y))
    prediction_metrics = {}
    for name, full in views.items():
        x = full[indices]
        pred = np.zeros(len(y))
        for tr, te in folds:
            classifier = SVC(C=1, kernel="rbf", gamma="scale", class_weight="balanced") if name == "kernel_abundance" else LogisticRegression(C=1, class_weight="balanced", max_iter=2000)
            model = make_pipeline(StandardScaler(), classifier)
            model.fit(x[tr], y[tr])
            pred[te] = model.decision_function(x[te])
        prediction_metrics[name] = {"out_of_fold_auroc": float(roc_auc_score(y, pred)),
            "balanced_accuracy": float(balanced_accuracy_score(y, pred>0)), "n_donors": len(y)}
    # Exploratory effect for a fixed module; no seed/panel chosen by this estimate.
    mitotic = module_values[indices, 0]
    delta = float(mitotic[y==1].mean() - mitotic[y==0].mean())
    pooled = float(np.sqrt((mitotic[y==1].var(ddof=1)+mitotic[y==0].var(ddof=1))/2))
    effect = delta/pooled if pooled else 0
    retrieval = {}
    perturb = d.copy()
    lost = (rng.random((len(d), p)) < .05) & d[:, p:].astype(bool)
    perturb[:, :p][lost] = 0; perturb[:, p:][lost] = 0
    for name, model in models.items():
        original = views[name]
        if name == "pca":
            disturbed = (perturb-model.arrays["input_center"]) @ model.arrays["components"].T
        else:
            hidden = np.maximum(0, perturb@model.arrays["w1"].T+model.arrays["b1"])
            disturbed = hidden@model.arrays["w2"].T+model.arrays["b2"]
        def nearest(x):
            distances = ((x[:, None]-x[None, :])**2).sum(2)
            np.fill_diagonal(distances, np.inf)
            return np.argsort(distances, axis=1, kind="stable")[:, :5]
        n1, n2 = nearest(original), nearest(disturbed)
        retrieval[name] = float(np.mean([len(set(a)&set(b))/5 for a,b in zip(n1,n2)]))
    keys = donor_keys(dev)
    return {"schema": "ProteinDevelopmentComparison-v1", "status": "exploratory",
            "cohort_hashes": {k: digest(c) for k,c in zip(("train","validation","dev"),(train,validation,dev))},
            "panel_sha256": digest(panel), "reconstruction": reconstruction,
            "grade_prediction": prediction_metrics, "retrieval_top5_overlap_after_5pct_mask_loss": retrieval,
            "module_coverage": coverage, "mitotic_grade_standardized_difference": effect,
            "folds": [{"train": [keys[indices[i]] for i in tr], "test": [keys[indices[i]] for i in te]} for tr,te in folds],
            "limitations": ["Out-of-fold development prediction, not native confirmation", "treatment status unresolved",
                            "26 grade pairs before exclusions; 48 required", "processed reference assay may carry cohort/batch effects"]}
