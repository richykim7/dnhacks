#!/usr/bin/env python3
"""Export measured CUDA training curves and held-out comparisons as PNG/PDF."""

import argparse, json
from pathlib import Path
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--report", required=True)
p.add_argument("--output", required=True)
a = p.parse_args()
r = json.loads(Path(a.report).read_text())
out = Path(a.output)
out.mkdir(parents=True, exist_ok=True)
plt.rcParams.update(
    {
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 150,
    }
)
colors = {"epithelial-enriched": "#147D92", "fibroblast": "#B16B32"}


def export(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(out / f"{name}.{ext}", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)


fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
for row, (comp, color) in enumerate(colors.items()):
    for col, method in enumerate(("dae", "nb")):
        ax = axes[row, col]
        models = [
            m for k, m in r["models"].items() if k.startswith(comp + "-" + method + "-")
        ]
        for i, m in enumerate(models):
            curves = m["curves"]
            x = [c["epoch"] for c in curves]
            ax.plot(
                x,
                [c["train_loss"] for c in curves],
                color=color,
                alpha=0.3,
                linewidth=1,
                label="Training (masked inputs)" if i == 0 else None,
            )
            ax.plot(
                x,
                [c["validation_loss"] for c in curves],
                color=color,
                linewidth=1.5,
                linestyle=("--", ":", "-")[i % 3],
                label=f"Validation · seed {m['seed']}",
            )
            best = next(c for c in curves if c["epoch"] == m["best_epoch"])
            ax.scatter(
                [best["epoch"]], [best["validation_loss"]], color=color, s=25, zorder=5
            )
        ax.set(
            title=f"{comp.capitalize()} · {'denoising autoencoder' if method == 'dae' else 'negative-binomial encoder'}",
            xlabel="Epoch",
            ylabel="Log-library MSE" if method == "dae" else "Negative log likelihood",
        )
        ax.legend(frameon=False, fontsize=8)
fig.suptitle(
    f"{r['donors']}-donor cellular development — actual CUDA training curves",
    fontweight="bold",
)
export(fig, "training-curves")
fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), layout="constrained")
for ax, (comp, color) in zip(axes, colors.items()):
    for offset, split, alpha in [
        (-0.18, "validation", 1),
        (0.18, "external-test", 0.45),
    ]:
        means = []
        spreads = []
        for method in ("pca", "dae", "nb"):
            models = [
                m
                for k, m in r["models"].items()
                if k == comp + "-" + method or k.startswith(comp + "-" + method + "-")
            ]
            values = [m["metrics"][split]["log_library_mse"] for m in models]
            means.append(np.mean(values))
            spreads.append(np.std(values))
        ax.bar(
            np.arange(3) + offset,
            means,
            width=0.34,
            color=color,
            alpha=alpha,
            label="Donor validation" if split == "validation" else "External studies",
            yerr=spreads,
            capsize=3,
        )
    ax.set(
        xticks=np.arange(3),
        xticklabels=["GPU PCA", "Denoising AE", "Masked NB"],
        ylabel="Held-out log-library MSE",
        title=comp.capitalize(),
    )
    ax.legend(frameon=False)
fig.suptitle("Same expanded data and 64-dimensional representations", fontweight="bold")
fig.supxlabel(
    "Bars: mean across recorded seeds; error bars: seed standard deviation (not donor uncertainty)",
    fontsize=9,
)
export(fig, "held-out-comparison")
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
c = r["lineage"]["curves"]
axes[0].plot(
    [v["epoch"] for v in c],
    [v["train_loss"] for v in c],
    label="Training (class weighted)",
    color="#147D92",
)
axes[0].plot(
    [v["epoch"] for v in c],
    [v["validation_loss"] for v in c],
    label="Validation",
    color="#B16B32",
)
axes[0].axvline(
    r["lineage"]["best_epoch"], ls=":", color="#555", label="Saved checkpoint"
)
axes[0].set(
    xlabel="Epoch", ylabel="Cross entropy", title="Coarse lineage classification"
)
axes[0].legend(frameon=False, fontsize=8)
axes[1].plot(
    [v["epoch"] for v in c],
    [v["validation_accuracy"] * 100 for v in c],
    color="#147D92",
)
axes[1].set(
    xlabel="Epoch",
    ylabel="Validation accuracy (%)",
    title="Published compartment labels",
)
fig.suptitle(
    "Actual classifier diagnostics — rising validation loss is retained",
    fontweight="bold",
)
export(fig, "lineage-curves")
fig, ax = plt.subplots(figsize=(10, 5), layout="constrained")
associations = list(r["association"].values())
studies = sorted(set(s for a in associations for s in a["within_study_holdouts"]))
labels = ["Pooled holdout"] + studies
learned = []
baseline = []
spread = []
for study in [None] + studies:
    values = [
        a["held_out"]["auroc"]
        if study is None
        else a["within_study_holdouts"][study]["learned"]["auroc"]
        for a in associations
    ]
    controls = [
        a["held_out_bilinear"]["auroc"]
        if study is None
        else a["within_study_holdouts"][study]["bilinear"]["auroc"]
        for a in associations
    ]
    learned.append(np.mean(values))
    spread.append(np.std(values))
    baseline.append(np.mean(controls))
x = np.arange(len(labels))
ax.bar(
    x - 0.18,
    learned,
    width=0.34,
    yerr=spread,
    capsize=3,
    color="#147D92",
    label="Neural scorer (three seeds)",
)
ax.bar(
    x + 0.18,
    baseline,
    width=0.34,
    color="#B16B32",
    label="Training-only bilinear baseline",
)
ax.axhline(0.5, color="#777", ls="--", label="Chance")
ax.set(
    xticks=x,
    xticklabels=labels,
    ylim=(0, 1),
    ylabel="Donor matching AUROC",
    title="Held-out associations — pooled and within-study controls",
)
ax.legend(frameon=False, fontsize=8)
fig.supxlabel(
    "Exposed development discrimination; not confirmation, causality or a power certificate",
    fontsize=9,
)
export(fig, "association-controls")
