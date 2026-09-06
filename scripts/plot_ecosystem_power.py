#!/usr/bin/env python3
"""Plot conditional developmental power without implying new biological donors."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import NullFormatter, ScalarFormatter

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--report", required=True)
p.add_argument("--output", required=True)
a = p.parse_args()
r = json.loads(Path(a.report).read_text())
out = Path(a.output)
out.mkdir(parents=True, exist_ok=True)
fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
for ax, (method, result) in zip(axes, r["results"].items()):
    for study, data in result["studies"].items():
        values = [v for v in data["projections"] if v["scenario"] == "empirical-joint"]
        x = [v["simulated_donors"] for v in values]
        ax.plot(
            x,
            [v["anytime_rejection"] for v in values],
            marker=".",
            label=f"{study} ({data['observed_donors']} observed)",
        )
        ax.fill_between(
            x,
            [v["anytime_interval"][0] for v in values],
            [v["anytime_interval"][1] for v in values],
            alpha=0.15,
        )
    ax.axhline(0.8, linestyle="--", color="black", linewidth=1, label="80% target")
    ax.set(
        xscale="log",
        ylim=(0, 1.03),
        xlabel="Simulated IID donors (not acquired donors)",
        ylabel="Anytime rejection probability",
        title=method,
    )
    ax.legend(fontsize=8, frameon=False)
    ax.set_xticks([18, 40, 100, 200, 400])
    ax.xaxis.set_major_formatter(ScalarFormatter())
    ax.xaxis.set_minor_formatter(NullFormatter())
fig.suptitle(
    "Real frozen views · conditional empirical power projections", fontweight="bold"
)
fig.supxlabel(
    "10,000 streams per point; bands show Monte Carlo uncertainty only. Biological gate remains unmet.",
    fontsize=9,
)
for ext in ("png", "pdf"):
    fig.savefig(out / f"growth-power.{ext}", dpi=160, bbox_inches="tight")
