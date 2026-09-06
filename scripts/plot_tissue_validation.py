#!/usr/bin/env python3
"""Plot computational sensitivity endpoints without biological confidence claims."""

import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = json.loads(args.report.read_text())
    rows = report["endpoints"]
    scenarios = list(dict.fromkeys(r["scenario"] for r in rows))
    x = np.arange(len(scenarios))
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axs = plt.subplots(1, 2, figsize=(15, 6), layout="constrained")
    for condition, label, color in [
        ("baseline", "CAF secretion / uptake intact", "#168d9c"),
        ("secretion_off", "CAF secretion off", "#d69542"),
        ("uptake_suppressed", "Uptake 5% of baseline", "#6b608c"),
    ]:
        for ax, endpoint in zip(axs, ["living_tumor_count", "living_tumor_volume_um3"]):
            values = np.array(
                [
                    [
                        r[endpoint]
                        for r in rows
                        if r["scenario"] == s and r["condition"] == condition
                    ]
                    for s in scenarios
                ]
            )
            if endpoint.endswith("um3"):
                values = values / 1e6
            mean = values.mean(axis=1)
            ax.plot(x, mean, "o-", color=color, label=label, lw=1.7, markersize=4)
            ax.fill_between(
                x, values.min(axis=1), values.max(axis=1), color=color, alpha=0.15
            )
    for ax in axs:
        ax.set_xticks(x, scenarios, rotation=48, ha="right")
        ax.grid(axis="y", alpha=0.18)
        ax.set_xlabel("Declared assumed scenario")
    axs[0].set_ylabel("Living tumor cells at 1,440 min")
    axs[0].set_ylim(-8, 375)
    axs[1].set_ylabel("Living tumor volume (million µm³)")
    axs[1].legend(frameon=False, fontsize=9)
    fig.suptitle(
        "Conditional alanine exchange · native PhysiCell/BioFVM sensitivity",
        fontsize=16,
    )
    fig.supxlabel(
        "Three computational seeds; shading is min–max across seeds. Assumed geometry, kinetics and death law; no biological validation.",
        fontsize=10,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output.with_suffix(".png"), dpi=160)
    fig.savefig(args.output.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
