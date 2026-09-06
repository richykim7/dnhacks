#!/usr/bin/env python3
"""Render measured presentation figures from committed aggregate JSON; no training."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess

import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager, pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "presentation/assets/v2/plots"
INK, GREEN, AMBER, IVORY = "#14201B", "#A6C9B8", "#DEB577", "#F1EFE7"
MUTED, GRID, BLUE, ROSE = "#A6B3A9", "#35473B", "#89AEBB", "#D99E99"
SOURCES, FIGURES = {}, []


def read(relative):
    path = REPO / relative
    raw = path.read_bytes()
    SOURCES[relative] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def style():
    # Matplotlib may have cached its fonts before the presentation fonts were installed.
    folder = Path.home() / ".local/share/fonts/dnhacks-presentation"
    for path in folder.glob("IBMPlexSans-*.ttf"):
        font_manager.fontManager.addfont(str(path))
    if not any(f.name == "IBM Plex Sans" for f in font_manager.fontManager.ttflist):
        raise RuntimeError("Install IBM Plex Sans before rendering the figures")
    plt.rcParams.update({
        "font.family": "IBM Plex Sans", "font.size": 20, "axes.titlesize": 25,
        "axes.labelsize": 21, "xtick.labelsize": 19, "ytick.labelsize": 20,
        "legend.fontsize": 18, "figure.facecolor": INK, "axes.facecolor": INK,
        "savefig.facecolor": INK, "text.color": IVORY, "axes.labelcolor": IVORY,
        "xtick.color": MUTED, "ytick.color": IVORY, "axes.edgecolor": GRID,
        "axes.spines.top": False, "axes.spines.right": False,
        "pdf.fonttype": 42, "ps.fonttype": 42,
    })


def figure(title, subtitle, panels=1):
    fig, axes = plt.subplots(1, panels, figsize=(16, 9), dpi=100, squeeze=False)
    fig.subplots_adjust(left=.16 if panels > 1 else .115, right=.95,
                        bottom=.285 if panels > 1 else .23,
                        top=.69 if panels > 1 else .755, wspace=.55)
    fig.text(.055, .938, title, size=32, weight="bold", va="top")
    fig.text(.055, .866, subtitle, size=20, color=GREEN, va="top")
    for ax in axes.flat:
        ax.set_axisbelow(True)
    return fig, axes[0]


def finish(fig, name, source, scope, data, note, aliases=()):
    fig.text(.055, .122, scope, size=18, color=IVORY, va="top")
    fig.text(.055, .063, source, size=14, color=MUTED, va="top")
    for basename in (name, *aliases):
        for ext in ("png", "pdf"):
            fig.savefig(OUT / f"{basename}.{ext}", dpi=100)
    plt.close(fig)
    FIGURES.append({"name": name, "png": f"{name}.png", "pdf": f"{name}.pdf",
                    "size_px": [1600, 900], "scope": scope, "source": source,
                    "data": data, "note": note, "aliases": list(aliases)})


def bars(ax, labels, values, colors, *, xmax=None, digits=3):
    pos = np.arange(len(labels))
    ax.barh(pos, values, height=.53, color=colors)
    ax.set_yticks(pos, labels)
    ax.invert_yaxis()
    limit = xmax or max(values) * 1.3
    ax.set_xlim(0, limit)
    ax.grid(axis="x", color=GRID, linewidth=.8)
    ax.tick_params(axis="y", length=0, pad=10)
    for y, value in zip(pos, values):
        ax.text(value + limit*.024, y, f"{value:.{digits}f}", va="center", size=20)


def expression():
    prefix = "research/learned-evalue-validation/real-expression/"
    training = read(prefix + "training.json")
    evaluation = read(prefix + "evaluation.json")
    losses = training["autoencoder"]["training_loss"]
    fig, (ax,) = figure("A learned expression representation", "Measured training · GSE212041 · 149 training donors")
    ax.plot(range(1, len(losses)+1), losses, color=GREEN, linewidth=4)
    ax.set(xlabel="Training epoch", ylabel="Masked reconstruction MSE", xlim=(1, 100), ylim=(0, 1.2))
    ax.grid(color=GRID, linewidth=.8)
    ax.text(.98, .89, "19,000 → 512 → 128\n15% masking · L40S", transform=ax.transAxes,
            ha="right", va="top", color=GREEN, size=23, linespacing=1.5)
    finish(fig, "expression_training", "Source: real-expression/training.json · autoencoder.training_loss",
           "Training loss only. A per-epoch held-out validation series was not recorded.",
           {"epochs": list(range(1, 101)), "training_loss": losses}, "No validation points invented; fixed 100-epoch run.")

    primary = evaluation["primary"]
    fig, (ax,) = figure("Evidence changes as fresh pairs arrive", "Measured diagnostic · COVID expression cohort · primary seed 20260906")
    plot_data = {}
    for key, label, color in (("autoencoder", "Learned encoder", GREEN),
                              ("pca", "PCA", BLUE), ("scalar", "IFIT3 single gene", AMBER)):
        row = primary["methods"][key]
        values = np.exp(row["log_wealth_path"])
        observed = [8, 12, 16, 20, 24, 28, 30]
        assert len(values) == len(observed)
        ax.plot(observed, values, "o-", color=color, linewidth=3,
                label=f"{label}  ({row['e_value']:,.1f})", markersize=7)
        plot_data[key] = {"pairs_observed": observed, "e_value": values.tolist()}
    ax.axhline(20, color=IVORY, linestyle=(0, (4, 4)), linewidth=1.5)
    ax.text(8.3, 25, "Evidence threshold: 20", size=18, color=IVORY)
    perm = primary["permutation"]["calibrated_e"]
    ax.scatter([30], [perm], color=ROSE, marker="D", s=70, zorder=5,
               label=f"Calibrated permutation, final only  ({perm:.1f})")
    ax.set(yscale="log", ylim=(.8, 20000), xlim=(7.6, 30.6),
           xlabel="Pairs observed (first 8 pairs are burn-in)", ylabel="Evidence value · logarithmic scale")
    ax.set_xticks([8, 12, 16, 20, 24, 28, 30])
    ax.set_yticks([1, 10, 100, 1000, 10000], ["1", "10", "100", "1,000", "10,000"])
    ax.grid(axis="y", which="major", color=GRID)
    ax.legend(loc="upper left", frameon=False, ncols=2, bbox_to_anchor=(0, 1.03),
              labelspacing=.45, columnspacing=1.2, handlelength=1.8)
    finish(fig, "expression_evidence", "Source: real-expression/evaluation.json · primary.methods.*.log_wealth_path",
           "Same 30 selected pairs. The single-gene baseline is strongest in this primary run.",
           {"series": plot_data, "calibrated_permutation_final": perm},
           "Standalone observational diagnostic, not PDAC, causal evidence or universal model superiority.")


def ecosystems():
    d = read("docs/ecosystem-training/metrics.json")
    fig, (ax,) = figure("Training improves; generalization must be measured", "Measured masked count-model training · separate cell compartments · 20 CPU epochs")
    series = {}
    for kind, label, color in (("malignant", "Malignant-enriched proxy", GREEN),
                                ("fibroblast", "Fibroblasts", AMBER)):
        values = d["models"][kind+"-nb"]["manifest"]["training_loss"]
        ax.plot(range(1, len(values)+1), values, "o-", linewidth=3, color=color, markersize=5, label=label)
        series[kind] = values
    ax.set(xlabel="Training epoch", ylabel="Masked negative-binomial loss", xlim=(1, 20), ylim=(1.5, 2.6))
    ax.set_xticks([1, 5, 10, 15, 20])
    ax.grid(color=GRID)
    ax.legend(frameon=False, loc="upper right")
    finish(fig, "ecosystem_nb_training", "Source: docs/ecosystem-training/metrics.json · models.*-nb.manifest.training_loss",
           "Peng training: 16 malignant-enriched donors / 13 fibroblast donors; 32 cells per donor.",
           {"epochs": list(range(1, 21)), "training_loss": series},
           "No per-epoch validation series retained. Compartment labels are expression-based proxies.")

    fig, axes = figure("The simpler cell representation transfers better", "Final held-out error · lower is better · separate from training loss", 2)
    data = {}
    for ax, kind, title, counts in zip(axes, ("malignant", "fibroblast"),
                                      ("Malignant-enriched", "Fibroblasts"),
                                      ("Peng n=8 · Lin n=7", "Peng n=5 · Lin n=9")):
        ax.set_title(title+"\n"+counts, loc="left", pad=20, linespacing=1.3)
        pos = np.arange(3)
        methods = ["cell-pca", "pseudobulk-pca", "nb"]
        data[kind] = {}
        for shift, cohort, label, color in ((-.17, "peng", "Peng held-out", GREEN),
                                            (.17, "lin", "Lin external", AMBER)):
            values = [d["models"][kind+"-"+method]["held_out"][cohort]["donor_mean_reconstruction_mse"] for method in methods]
            ax.barh(pos+shift, values, height=.28, color=color, label=label)
            for y, value in zip(pos+shift, values):
                ax.text(value+.025, y, f"{value:.2f}", va="center", size=18)
            data[kind][cohort] = values
        ax.set_yticks(pos, ["Cell PCA", "Donor PCA", "Masked NB"])
        ax.invert_yaxis()
        ax.set(xlim=(0, 1.55), xlabel="Donor-mean log-library MSE")
        ax.grid(axis="x", color=GRID)
        ax.tick_params(axis="y", length=0)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, loc="center", bbox_to_anchor=(.51, .177), ncols=2)
    finish(fig, "ecosystem_heldout", "Source: docs/ecosystem-training/metrics.json · models.*.held_out.{peng,lin}",
           "Final donor-level errors. No neural advantage observed; cells are not independent donors.",
           data, "Donor PCA is the pseudobulk baseline projected back to cell expression for common error measurement.")

    sets = read("docs/ecosystem-training/set-metrics.json")
    fig, (ax,) = figure("Learned pooling has a measurable training objective", "Measured set-encoder training · donor reconstruction + 0.1 × subbag instability")
    data = {}
    for kind, label, color in (("malignant", "Malignant-enriched proxy", GREEN),
                                ("fibroblast", "Fibroblasts", AMBER)):
        records = sets["models"][kind]["manifest"]["losses"]
        values = [v["reconstruction"]+.1*v["stability"] for v in records]
        ax.plot(range(1, len(values)+1), values, "o-", color=color, linewidth=3, markersize=5, label=label)
        data[kind] = values
    ax.set(xlabel="Training epoch", ylabel="Recorded training objective", xlim=(1, 20))
    ax.set_xticks([1, 5, 10, 15, 20])
    ax.grid(color=GRID)
    ax.legend(frameon=False)
    finish(fig, "ecosystem_set_training", "Source: docs/ecosystem-training/set-metrics.json · models.*.manifest.losses",
           "Training only. Learned pooling did not beat donor-summary PCA on final held-out error.",
           data, "The recorded objective is calculated from the two logged loss terms; no validation curve exists.")


def pharmacotype():
    d = read("docs/pharmacotype-cuda-training.json")
    kinds = ["identity", "pca", "mlp"]
    means = [float(np.mean([t["validation_curve_rmse"] for t in d["trials"] if t["kind"] == k])) for k in kinds]
    fig, axes = figure("Model selection is not proof of pancreatic utility", "Measured PRISM / CCLE development · 245 train / 40 validation / 71 test", 2)
    axes[0].set_title("Validation selection", loc="left", pad=22)
    bars(axes[0], ["Identity + ridge", "PCA + ridge", "Masked MLP\n+ ridge"], means, [MUTED, GREEN, AMBER], xmax=1.5)
    axes[0].set_xlabel("Curve RMSE · lower is better")
    held = d["heldout"]["pancreatic_development"]
    mean = held["training_mean_rmse"]
    pca = float(np.mean(held["selected_model_seed_rmse"]))
    axes[1].set_title("22 pancreatic test groups", loc="left", pad=22)
    bars(axes[1], ["Training mean", "Selected PCA"], [mean, pca], [GREEN, AMBER], xmax=1.3)
    axes[1].set_xlabel("Curve RMSE · lower is better")
    finish(fig, "pharmacotype_cuda", "Source: docs/pharmacotype-cuda-training.json · trials / heldout.pancreatic_development",
           "PCA wins model selection; the mean baseline is better on pancreatic test groups.",
           {"validation_mean_rmse": dict(zip(kinds, means)), "pancreatic_test": {"training_mean": mean, "selected_pca": pca}},
           "Validation mean-baseline RMSE was not recorded, so none is invented. Three-seed means; seeds are not independent data replicates.", aliases=("pharmacotype",))

    d = read("docs/pharmacotype-pdo-auc.json")
    values = [d["mean_baseline"]["validation_auc_rmse"]] + [float(np.mean([t["validation_auc_rmse"] for t in d["trials"] if t["kind"] == k])) for k in kinds]
    fig, (ax,) = figure("On real pancreatic organoids, retain the mean baseline", "Measured Shi 2022 AUC benchmark · 21 train / 5 validation / 12 test patients")
    fig.subplots_adjust(left=.255)
    bars(ax, ["Training mean", "Identity + ridge", "PCA + ridge", "Masked MLP + ridge"], values,
         [GREEN, MUTED, BLUE, AMBER], xmax=.29, digits=4)
    ax.set_xlabel("Validation AUC RMSE · lower is better")
    finish(fig, "pharmacotype_pdo_auc", "Source: docs/pharmacotype-pdo-auc.json · mean_baseline / trials",
           "No learned model improves validation error. Five validation patients limit the conclusion.",
           dict(zip(["training_mean"]+kinds, values)),
           "AUC is normalized area under the drug-response curve. Not a full-curve prediction or confirmation result.", aliases=("pdo",))


def expression_panel():
    prefix = "research/learned-evalue-validation/real-expression/"
    losses = read(prefix+"training.json")["autoencoder"]["training_loss"]
    primary = read(prefix+"evaluation.json")["primary"]
    fig, (left, right) = figure("Learning the representation; measuring the evidence",
                               "Measured expression diagnostic · COVID cohort · no per-epoch validation history", 2)
    fig.subplots_adjust(left=.105, right=.96, wspace=.42, bottom=.30)
    left.set_title("TRAIN · 149 donors", loc="left", pad=22)
    left.plot(range(1, len(losses)+1), losses, color=GREEN, linewidth=4)
    left.set(xlabel="Training epoch", ylabel="Reconstruction MSE", xlim=(1, 100), ylim=(0, 1.2))
    left.grid(color=GRID)
    right.set_title("Fresh-pair evidence", loc="left", pad=22)
    observed = [8, 12, 16, 20, 24, 28, 30]
    data = {"training_loss": losses, "pairs_observed": observed, "evidence": {}}
    for key, label, color in (("autoencoder", "Learned encoder", GREEN),
                              ("pca", "PCA", BLUE), ("scalar", "IFIT3 single gene", AMBER)):
        values = np.exp(primary["methods"][key]["log_wealth_path"])
        right.plot(observed, values, "o-", color=color, linewidth=3, markersize=6, label=label)
        data["evidence"][key] = values.tolist()
    perm = primary["permutation"]["calibrated_e"]
    right.scatter([30], [perm], color=ROSE, marker="D", s=70, label="Permutation e · final only")
    data["calibrated_permutation_final"] = perm
    right.axhline(20, color=IVORY, linestyle=(0, (4, 4)), linewidth=1.5)
    right.text(8.4, 27, "Threshold 20", size=18)
    right.set(yscale="log", ylim=(.8, 20000), xlim=(7.4, 31), xlabel="Pairs observed · 8 burn-in", ylabel="Evidence · log scale")
    right.set_xticks([8, 16, 24, 30])
    right.set_yticks([1, 100, 10000], ["1", "100", "10,000"])
    right.grid(axis="y", which="major", color=GRID)
    handles, labels = right.get_legend_handles_labels()
    fig.legend(handles, labels, loc="center", bbox_to_anchor=(.52, .194), ncols=4,
               frameon=False, columnspacing=1, handlelength=1.5, fontsize=18)
    finish(fig, "expression", "Source: real-expression/{training,evaluation}.json · measured loss / primary evidence paths",
           "Same 30 selected evaluation pairs. IFIT3 is strongest in this primary run; no PDAC result.",
           data, "Training and downstream evidence are different metrics on different data. No validation or permutation trajectory is invented.")


def ecosystem_panel():
    d = read("docs/ecosystem-training/metrics.json")
    fig, (left, right) = figure("A falling loss is only the first check",
                               "Measured cell-compartment models · training histories and separate final held-out errors", 2)
    fig.subplots_adjust(left=.105, right=.96, wspace=.74, bottom=.30)
    left.set_title("TRAIN · masked count models", loc="left", pad=22)
    data = {"training_loss": {}, "final_heldout_mse": {}}
    for kind, label, color in (("malignant", "Malignant-enriched", GREEN), ("fibroblast", "Fibroblasts", AMBER)):
        values = d["models"][kind+"-nb"]["manifest"]["training_loss"]
        left.plot(range(1, len(values)+1), values, color=color, linewidth=3, label=label)
        data["training_loss"][kind] = values
    left.set(xlabel="Training epoch", ylabel="Masked NB loss", xlim=(1, 20), ylim=(1.5, 2.6))
    left.set_xticks([1, 5, 10, 15, 20])
    left.grid(color=GRID)
    left.legend(frameon=False, fontsize=18, loc="upper right")
    right.set_title("FINAL · held-out reconstruction", loc="left", pad=22)
    conditions = [("malignant", "peng"), ("malignant", "lin"), ("fibroblast", "peng"), ("fibroblast", "lin")]
    for method, label, color, marker in (("cell-pca", "Cell PCA", GREEN, "o"),
                                       ("pseudobulk-pca", "Donor PCA", BLUE, "s"),
                                       ("nb", "Masked NB", AMBER, "D")):
        values = [d["models"][kind+"-"+method]["held_out"][cohort]["donor_mean_reconstruction_mse"] for kind, cohort in conditions]
        right.scatter(values, range(4), color=color, marker=marker, s=105, label=label, zorder=3)
        data["final_heldout_mse"][method] = values
    right.set_yticks(range(4), ["Malignant · Peng", "Malignant · Lin", "Fibroblast · Peng", "Fibroblast · Lin"])
    right.tick_params(axis="y", labelsize=18, length=0)
    right.invert_yaxis()
    right.set(xlim=(0, 1.4), xlabel="Donor-mean MSE · lower is better")
    right.set_xticks([0, .4, .8, 1.2])
    right.grid(color=GRID)
    handles, labels = right.get_legend_handles_labels()
    fig.legend(handles, labels, loc="center", bbox_to_anchor=(.53, .194), ncols=3,
               frameon=False, columnspacing=2, fontsize=18)
    finish(fig, "ecosystem", "Source: docs/ecosystem-training/metrics.json · models.*.manifest.training_loss / held_out",
           "Cell PCA wins every shown held-out comparison. No per-epoch validation history recorded.",
           {**data, "condition_order": conditions},
           "Malignant is an enriched proxy. Held-out donor counts: Peng 8/5, Lin 7/9 (malignant/fibroblast); not independent cells.")


def protein():
    relative = "docs/protein-training.md"
    raw = (REPO / relative).read_bytes()
    SOURCES[relative] = hashlib.sha256(raw).hexdigest()
    content = raw.decode()
    labels = ["Training feature mean", "PCA, 32 components", "Masked denoiser"]
    values = []
    for label in labels:
        match = re.search(r"\|\s*"+re.escape(label)+r"\s*\|\s*(\d+\.\d+)\s*\|", content)
        if not match:
            raise ValueError(f"Missing documented protein result: {label}")
        values.append(float(match.group(1)))
    fig, (ax,) = figure("The protein denoiser does not beat PCA",
                       "Measured hidden-entry reconstruction · CPTAC · 219 TRAIN / 110 LUAD validation cases")
    fig.subplots_adjust(left=.27)
    bars(ax, ["Training feature mean", "PCA · 32 components", "Masked denoiser"], values,
         [MUTED, GREEN, AMBER], xmax=3.65, digits=4)
    ax.set_xlabel("Hidden-entry standardized MSE · lower is better")
    finish(fig, "protein", "Source: docs/protein-training.md · protein-s10-20260906-v2 · frozen reconstruction table",
           "Final held-out error, not an epoch curve. No reconstruction history was retained.",
           dict(zip(labels, values)),
           "Documentation-sourced measured values. Evaluation mask differs from the mask used for checkpoint selection. No training was performed for this figure.")


def external_protein():
    d = read("docs/protein-external-results.json")
    training = read("docs/protein-external-training.json")
    keys = ["rank_pca", "rank_linear", "fixed_modules", "missingness", "rank_kernel"]
    labels = ["Rank-PCA · PRIMARY", "Linear rank", "Fixed modules", "Missingness", "RBF rank kernel · secondary"]
    records = [d["results"][key]["groups"]["all_graded"] for key in keys]
    counts = records[0]
    assert all((r["n"], r["G1_G2"], r["G3"], r["pairs"]) ==
               (counts["n"], counts["G1_G2"], counts["G3"], counts["pairs"]) for r in records)
    fig, (ax,) = figure("A real external benchmark, with mixed results",
                       f"Fudan PDAC · {counts['n']} graded tumors / {counts['pairs']} possible grade pairs · 95% bootstrap intervals")
    fig.subplots_adjust(left=.345)
    for i, (key, row) in enumerate(zip(keys, records)):
        value = row["auroc"]
        lo, hi = row["bootstrap_ci95"]
        color = GREEN if key == "rank_pca" else AMBER if key == "rank_kernel" else MUTED
        ax.errorbar(value, i, xerr=[[value-lo], [hi-value]], fmt="o", color=color,
                    markersize=11, capsize=6, linewidth=2.5)
        ax.text(.822, i, f"{value:.3f}", va="center", size=21, color=color)
    ax.axvline(.5, color=IVORY, linewidth=1.5, linestyle=(0, (4, 4)))
    ax.set_yticks(range(len(keys)), labels)
    ax.invert_yaxis()
    ax.set(xlim=(.37, .875), xlabel="Grade-ranking AUROC · 0.5 = chance")
    ax.set_xticks([.4, .5, .6, .7, .8])
    ax.tick_params(axis="y", length=0, pad=10, labelsize=20)
    ax.grid(axis="x", color=GRID)
    finish(fig, "external_protein", "Source: docs/protein-external-{results,training}.json · all_graded / bootstrap_ci95",
           "Cross-assay exploratory benchmark. Primary transfer is weak; secondary result needs a new cohort.",
           {"primary_view": d["primary_view"], "all_graded": dict(zip(keys, records)),
            "training_source_grade_donors": training["source_grade_donors"],
            "interval_replicates": d["bootstrap_replicates"]},
           "95% stratified bootstrap intervals condition on the frozen model and observed cases; not adjusted for multiple views. "
           "224 graded tumors comprise 159 G3 and 65 G2; 65 is the possible pair count, not a native sequential-confirmation sample. "
           "The primary rank-PCA head and secondary RBF rank kernel were prespecified. Kernel balanced accuracy at the source-fixed threshold is 0.553; "
           "published cohort preprocessing and prior exposure preclude untouched confirmation. No model is refit for this plot.")


def synthetic_null():
    d = read("research/learned-evalue-validation/expanded-null.json")["scenarios"]["null"]
    keys = ["identity", "pca", "autoencoder", "scalar", "fixed_projection", "permutation_p", "permutation_calibrated_e"]
    labels = ["Identity", "PCA", "Learned encoder", "Single feature", "Fixed projection", "Permutation p*", "Calibrated perm. e*"]
    values = np.array([d[k]["crossing_rate"]*100 for k in keys])
    intervals = np.array([d[k]["crossing_ci95"] for k in keys])*100
    fig, (ax,) = figure("How often is a difference flagged when none exists?", "Measured synthetic null audit · 10,000 runs per method · threshold 20 / nominal 5%")
    fig.subplots_adjust(left=.26)
    pos = np.arange(len(keys))
    for i, key in enumerate(keys):
        ax.errorbar(values[i], i, xerr=[[values[i]-intervals[i, 0]], [intervals[i, 1]-values[i]]],
                    fmt="o", color=GREEN if key == "autoencoder" else BLUE if key.startswith("permutation") else MUTED,
                    capsize=5, markersize=10, linewidth=2)
        ax.text(6.75, i, f"{values[i]:.2f}%", va="center", size=20, color=GREEN if key == "autoencoder" else IVORY)
    ax.axvline(5, color=AMBER, linestyle=(0, (5, 4)), linewidth=2)
    ax.set_yticks(pos, labels)
    ax.invert_yaxis()
    ax.set(xlim=(-.1, 7.5), xlabel="Ever-crossing rate (%) · pointwise 95% Wilson intervals")
    ax.set_xticks([0, 1, 2, 3, 4, 5, 6])
    ax.tick_params(axis="y", length=0, pad=10)
    ax.grid(axis="x", color=GRID)
    finish(fig, "synthetic_null", "Source: research/learned-evalue-validation/expanded-null.json · scenarios.null",
           "* Fixed-horizon comparators. Invalid label-memorization control: 100% (10,000 / 10,000).",
           {"methods": keys, "rates_percent": values.tolist(), "wilson95_percent": intervals.tolist(),
            "invalid_control_percent": d["INVALID_label_memorization"]["crossing_rate"]*100},
           "Synthetic standalone component audit. Lower null crossing does not establish greater power; not a product error rate.")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    style()
    expression()
    ecosystems()
    pharmacotype()
    synthetic_null()
    expression_panel()
    ecosystem_panel()
    protein()
    external_protein()
    snapshot = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    (OUT / "manifest.json").write_text(json.dumps({"source_snapshot": snapshot,
        "sources_sha256": SOURCES, "figures": FIGURES, "generation": "matplotlib; no training or data acquisition"}, indent=2)+"\n")
    print(f"Rendered {len(FIGURES)} figures as 1600×900 PNG and standalone PDF in {OUT}")


if __name__ == "__main__":
    main()
