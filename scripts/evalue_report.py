#!/usr/bin/env python3
"""Render aggregate real-expression diagnostics as HTML and exportable figures.

Requires matplotlib, available through the repository's litmap extra. Reads no
patient-level inputs. The HTML is standalone and uses no network resources.
"""

import argparse
import html
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

LABELS = {
    "autoencoder": "Learned encoder (128)",
    "pca": "PCA (64)",
    "scalar": "IFIT3 scalar",
}
COLORS = {"autoencoder": "#087f8c", "pca": "#a65628", "scalar": "#6554c0"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    methods = data["primary"]["methods"]
    alpha = data["protocol"]["alpha"]
    threshold = math.log(1 / alpha)
    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
            "svg.hashsalt": "learned-evalue-report-v1",
        }
    )
    fig, ax = plt.subplots(figsize=(9, 4.8), layout="constrained")
    for key in ("autoencoder", "pca", "scalar"):
        path = methods[key]["log_wealth_path"]
        ax.plot(
            range(len(path)),
            path,
            "o-",
            color=COLORS[key],
            label=LABELS[key],
            lw=2,
            ms=5,
        )
    ax.axhline(
        threshold,
        color="#555555",
        ls="--",
        label=f"Anytime threshold (alpha={alpha:g})",
    )
    ax.axhline(0, color="#cccccc", lw=0.8)
    ax.set(
        xlabel="Scored batch (after two burn-in batches)",
        ylabel="Log wealth",
        title="Held-out day-zero expression: COVID+ vs symptomatic COVID−",
    )
    ax.legend(loc="best", fontsize=9)
    ax.grid(axis="y", alpha=0.2)
    fig.savefig(args.output / "wealth.svg", metadata={"Date": None})
    svg_path = args.output / "wealth.svg"
    svg_path.write_text("\n".join(line.rstrip() for line in svg_path.read_text().splitlines()) + "\n")
    fig.savefig(args.output / "wealth.png", dpi=180)
    rows = ""
    for name, result in methods.items():
        rows += f"<tr><th>{html.escape(LABELS[name])}</th><td>{result['e_value']:.4g}</td><td>{'Yes' if result['final_reject'] else 'No'}</td><td>{'Yes' if result['ever_crossed'] else 'No'}</td></tr>"
    nullrows = ""
    for name, result in data["orientation_null"].items():
        n = result["repetitions"]
        ci = result["crossing_ci95"]
        nullrows += f"<tr><th>{html.escape(LABELS[name])}</th><td>{result['final_rejections']}/{n}</td><td>{result['crossing_rejections']}/{n}</td><td>{ci[0]:.1%}–{ci[1]:.1%}</td></tr>"
    svg = (args.output / "wealth.svg").read_text()
    svg = svg[svg.index("<svg") :]
    svg = svg.replace("<svg", '<svg role="img" aria-label="Log wealth by scored batch for learned encoder, PCA, and IFIT3, with a threshold at log 20"', 1)
    limitations = "".join(f"<li>{html.escape(s)}</li>" for s in data["limitations"])
    p = data["primary"]["permutation"]["p_value"]
    doc = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Learned e-values · Real expression validation</title>
<style>body{{font:17px/1.6 system-ui,sans-serif;color:#172b36;background:#f5f7f9;margin:0}}main{{max-width:1050px;margin:auto;padding:32px 20px}}h1{{font-size:2.1rem;line-height:1.2}}h2{{font-size:1.35rem;margin-top:2em}}.tag{{color:#087f8c;font-weight:700}}.panel{{background:white;padding:24px;border-radius:12px;margin:20px 0}}svg{{width:100%;height:auto}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:10px 8px;border-bottom:1px solid #dbe3e8}}a{{color:#006975}}.scroll{{overflow:auto}}summary{{cursor:pointer;font-weight:650}}small{{color:#526571}}</style>
<main><p class="tag">Standalone diagnostic · GSE212041</p>
<h1>A learned bettor on held-out expression data</h1>
<p>The encoder trained on <b>149 donors using an NVIDIA L40S</b>. The evaluation split contains 151 donors;
its smaller group limits the primary comparison to <b>30 pairs</b>. A separate 74-donor development
split supplied device timing checks. Existing biological verification decisions are unchanged.</p>
<div class="panel">{svg}<p><a href="wealth.svg" download>Download SVG</a> · <a href="wealth.png" download>Download PNG</a> · <a href="evaluation.json">Aggregate data</a></p></div>
<h2>One predeclared primary comparison</h2><p>Seed {data["primary"]["seed"]}. Final wealth is the returned e-value;
a prior crossing supports an anytime diagnostic but the running maximum is not an e-value.</p>
<div class="panel scroll"><table><thead><tr><th>Representation</th><th>Final e-value</th><th>Final ≥ 20</th><th>Ever ≥ 20</th></tr></thead><tbody>{rows}</tbody></table>
<p>Ordinary mean-distance permutation p = {p:.4g}; calibrated e = {data["primary"]["permutation"]["calibrated_e"]:.4g}.
Methods receive the same total donor pairs; the bettors reserve two batches for burn-in.</p></div>
<h2>Real-expression geometry under an artificial null</h2>
<p>Independent fair signs orient fixed, disjoint donor pairs. This audits conditional fairness;
it does not treat clinical COVID labels as randomized.</p>
<div class="panel scroll"><table><thead><tr><th>Representation</th><th>Final rejections</th><th>Crossings</th><th>Crossing 95% interval</th></tr></thead><tbody>{nullrows}</tbody></table></div>
<details class="panel"><summary>Interpretation and limitations</summary><ul>{limitations}</ul></details>
<p><a href="https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE212041">Cohort source</a> ·
<a href="https://proceedings.mlr.press/v238/pandeva24a.html">DAVT paper</a></p>
<small>Distribution-level evidence. No causal interpretation, clinical validation, strongest-seed selection,
or investigation-wide error-control claim.</small></main></html>"""
    (args.output / "index.html").write_text(doc)
    print(args.output / "index.html")


if __name__ == "__main__":
    main()
