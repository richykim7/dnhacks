# geo_expression

> Robustly load a public GEO expression cohort and get *comparable* gene vectors, program/activity scores,
> and the covariates you must control — so a real-data experiment doesn't die at the gene→probe step or
> attribute a subtype/proliferation confound to mechanism. Informational guidance + a ready helper you may
> import; you are not required to use it — write your own code if you prefer, but honor the invariants below.

**One line:** How do I load a GEO microarray/expression cohort and pull defensible per-gene and gene-set
scores (with subtype / proliferation / sex controls) that are comparable across cohorts?
**Category:** bulk-rna-seq
**Open-source:** GEOparse (MIT) + numpy/pandas/scipy (BSD) — all baked into the sandbox image.
**Install:** none needed. In experiment code: `import sys; sys.path.insert(0, "/opt/sandbox_lib"); import geoharmonize as gh`

## When to use it (and when not)
- **Use when:** you need expression for named genes from a GEO series (`GSExxxxx`) — one gene, a matrix of
  genes, or a gene-set signature — especially when you will compare **across two or more cohorts**, or need
  proliferation / sex covariates.
- **Do not lean on it for:** RNA-seq count modeling (use DESeq2-style tools), single-cell (`.h5ad` →
  scanpy), or anything where you have a local pre-materialized matrix already keyed by gene. And it does not
  decide comparability for you — see the scale warning.

## API (import `geoharmonize as gh`)
- `ds = gh.load("GSExxxxx", destdir="/cache")` → a `Dataset`. Caches the download in `/cache` (persists
  across experiments). Applies log2 **only** when the GEO2R rule says the values are linear; leaves already-
  log or unit-normalized data alone. Multi-platform series: picks the platform with the most samples (or pass
  `platform="GPLxxxx"`). **Raises loudly** if the symbol→probe join is empty.
- `ds.report()` → what loaded: #probes/#samples, #symbols indexed, value range, whether log2 was applied,
  and any notes (multi-platform, duplicate probes, missing genes, scale warning). **Read this first.**
- `ds.gene("GENE_X", collapse="maxmean", z=False, missing="raise")` → one value per sample. `collapse`:
  `maxmean` (default; highest-mean probe — most reproducible across studies, Miller 2011), `maxvar`, `mean`,
  `median`. `missing="raise"` is deliberate — a silent zero-vector manufactures correlations.
- `ds.genes([...], z=True)` → genes×samples DataFrame. `ds.has_gene(g)`, `ds.search("GENE")`.
- `ds.signature(genes, method="singscore")` → per-sample score for any gene list. **`singscore` (default)
  is rank-based and cohort-INDEPENDENT** — a sample's score doesn't depend on the other samples, so it's
  comparable across separately-loaded cohorts. `method="meanz"` is simpler but cohort-DEPENDENT (don't
  compare meanz across cohorts).
- `ds.infer_sex()` → predicted sex (Y genes vs XIST); use to verify a recorded Gender field / catch swaps.
- `gh.compare_scales([ds1, ds2])` → warns when cohorts are on incompatible value scales (e.g. one log2
  `0..18`, one unit-normalized `0..1`). Do not pool those.
- `gh.SIGNATURES` → generic covariate gene sets: `PROLIFERATION`, `SEX_Y`, `SEX_XIST`. Bring your own
  target-program lists for the regulators you study.
- Subtype labels live in the sample characteristics (`ds.meta`, `ds._raw`); parse them with a regex for
  your cohort and carry them as a covariate.

## Rigor — the invariants a good analysis must honor
- **Unit of observation:** the patient/sample. Permute sample labels for a null; never permute genes.
- **Regulator mRNA ≠ regulator activity.** An enzyme's or transcription factor's *mRNA* barely reflects its
  activity (post-translational control; mutations leave mRNA intact). **Read the target program instead:**
  an activator's activity via its target signature; a repressor's activity via the *inverse* of its target
  signature (high activity = low target expression). Treat regulator mRNA as, at most, a weak covariate.
- **Confounders to adjust — cohort subtype first, then proliferation.** In most disease cohorts a subtype
  axis dominates variance and is confounded with the lineage regulators. A raw regulator~regulator
  correlation is over-determined (real regulation + subtype structure + proliferation). Report the
  **partial** correlation conditioning on the subtype covariate and the `PROLIFERATION` signature before
  claiming mechanism. Carry treatment era and sex as covariates too.
- **Circularity guard.** Subtype marker genes are *also* your biology. Don't regress out a subtype score
  built from a gene and then test that same gene — you'll induce spurious anti-correlation. Keep the
  covariate gene set disjoint from the tested genes.
- **Null model:** permutation at the sample unit; `p=(#≥obs+1)/(n+1)`, never 0. **Effect + floor:** report a
  standardized effect and a triviality floor. **Multiple testing:** BH-FDR over every test you ran.
- **Robustness:** replicate in an independent cohort — but score with `singscore` so the values are
  cohort-independent, and check `compare_scales` first.
- **Common pitfalls this removes / warns about:** silent zero-probe mapping; `VALUE` is whatever the
  submitter uploaded (not guaranteed normalized or comparable across GSEs); `log2(x+1)` on already-log data;
  pseudoreplication (four correlations off one confounded signal is not four independent confirmations);
  ComBat batch-correction is **harmful when batch is confounded with the biology** — only opt-in with
  subtype/sex as protected covariates.

## Data sources
- Any GEO series id. Downloads need `network="bridge"` (the default for experiment runs); they cache in
  `/cache` so a cohort is fetched once. Prefer cohorts with a clean subtype field in the characteristics.

## Minimal worked example
```python
import sys; sys.path.insert(0, "/opt/sandbox_lib")
import numpy as np, json
from scipy.stats import spearmanr
import geoharmonize as gh

ds = gh.load("GSExxxxx", destdir="/cache")
print(ds.report())

ACTIVATOR_TARGETS = ["GENE1", "GENE2", "GENE3"]      # your regulator's target program
REPRESSOR_TARGETS = ["GENE4", "GENE5", "GENE6"]
act_a  = ds.signature(ACTIVATOR_TARGETS)             # activator program; singscore = cohort-independent
act_b  = -ds.signature(REPRESSOR_TARGETS)            # repressor program = de-repression (inverse)
prolif = ds.signature(gh.SIGNATURES["PROLIFERATION"])
subtype = ds.signature(["MARKER1", "MARKER2"], method="meanz")   # or a parsed label, coded numerically

def rank(x): r=np.empty(len(x)); r[np.argsort(x)]=np.arange(len(x)); return r
def resid(y, Zs):
    R=np.column_stack([np.ones(len(y))]+[rank(z) for z in Zs]); b,*_=np.linalg.lstsq(R, rank(y), rcond=None)
    return rank(y)-R.dot(b)

raw,_  = spearmanr(act_a, act_b)
part,_ = spearmanr(resid(act_a,[subtype,prolif]), resid(act_b,[subtype,prolif]))   # partial out confounds
# permutation null at the sample unit, on the PARTIALLED statistic
rng=np.random.default_rng(0); ry=resid(act_b,[subtype,prolif]); rx=resid(act_a,[subtype,prolif])
null=[spearmanr(rx, rng.permutation(ry))[0] for _ in range(2000)]
p=(1+np.sum(np.abs(null)>=abs(part)))/2001.0
print("RESULT:", json.dumps({"effect":float(part),"effect_size":float(part),"p_null":float(p),
      "n_units":int(len(act_a)),"robust":None,
      "detail":{"raw_rho":float(raw),"partial_rho":float(part)}}))
```
The defensible quantity is the **partial** correlation after subtype + proliferation, not the raw one — and
the two regulators enter as **activity programs**, not single-gene mRNA.
