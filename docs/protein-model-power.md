# Actual frozen-model power protocol

Before simulation results: retain minimum effect0.4, alpha0.05,16 unscored burn-in
pairs and final wealth. Compare the saved CPTAC-fitted rank kernel against a fixed
measured-mitotic-module witness. The kernel artifact is the one evaluated on Fudan;
its weights are not refitted and Fudan labels/values do not fit this generator.

Fit a Gaussian factor generator on the 219 non-PDAC TRAIN cases on CUDA: source
gene means/scales,32 covariance factors and diagonal residual variances. Generate
fresh continuous protein vectors, not duplicate real patients. Use the selected
2,000-protein panel and the source observed fractions for independent missingness,
with the four measured mitotic genes observed in this favorable scenario. Inject
the shift into standardized protein abundances before the actual within-donor rank
transform. Shift every available mitotic member by the same amount so that the
equal-weight latent module's mean difference is exactly0.4 of its generator SD.
This explicitly models the measured shared subset, not absent proteins or a causal
grade effect. The original development effect estimate and this generator need
biological compatibility review before any release certificate.

Freeze stake selection on2,048 separate generated calibration pairs: choose from
0,0.125,0.25,0.5,1,2 times a source-only score normalization, using average log payoff.
Use no external outcomes, never invert an externally evaluated model's direction,
and retain a zero stake if the model cannot exploit the prespecified shift.
Evaluate independent null and shifted streams at60,192 and384 total pairs.
Pilot256 streams first; full study requires10,000 per case and uncertainty intervals.
The fixed module is an actual source-fitted witness with known injected signal;
its success cannot be relabeled as success of the rank kernel.

Neither simulation manufactures eligible patients nor establishes independent
sampling, processing or deployment privacy. The thread's full goal remains active.

## Completed modeled experiment

The256-stream pilot took1.51 seconds and used77.4 MB peak CUDA allocation. The full
10,000-stream-per-case run completed in41.9 seconds. Repeating it while saving the
generator and actual module-witness coefficients produced identical rejection counts.
The report is [protein-model-power.json](protein-model-power.json); portable arrays
are local at `data/interim/protein/model-power-v1/full-v2.npz`, with the SHA256 in
the report. The kernel artifact hash matches the external benchmark.

| Total pairs | Fixed-module final power | Fixed-module anytime power | Null anytime rejection |
|---|---:|---:|---:|
|60|26.99%|36.76%|1.97%|
|192|77.98%|89.27%|4.05%|
|384|95.18%|98.46%|4.04%|

The384-pair module result exceeds80% even at the pointwise95% lower bound. This is
success for the stated Gaussian factor scenario and fixed measured four-protein
witness only. Under the prespecified nonnegative-stake calibration, the frozen
rank kernel chose zero and rejected no streams. That does not erase its separate
external grade-ranking result, but it does show that the current ranking model
has not met this targeted protein-effect power requirement. Neither witness result
establishes a real grade effect or independent confirmation release.

The generator assumes a fully measured shared mitotic subset (ATM, GSK3B, PPP1CB,
PPP1R12A), source-fitted Gaussian factors, diagonal residual noise, and independent
missingness elsewhere. Those are favorable modeling assumptions requiring further
checks; absent proteins are not represented. Actual-model adequacy remains open.

## Korean cohort metadata audit

The primary Supplementary Tables1–7 workbook, SHA256
`573760cab764488d0bfda7d980dbec16ef320445742a1cc1b31324bce9240315`, resolves the
PDC catalog discrepancy. Source clinical TableS1a has196 patients; TableS1b has150
unique measured patients with complete clinical joins. Of those,143 are explicitly
ductal adenocarcinoma:107 moderate,8 well,25 poor and3 undocumented grades. The
remaining7 have other histologies. Therefore this source adds at most **25 compatible
grade pairs before treatment/coverage exclusions**, not75 or154.

PDC currently reports154 cases and170 clinical aliquot rows, all with grade Not
Reported, and mostly endocrine-tumor diagnosis labels. Those catalog labels cannot
override the publication's patient-level pathology table. The public normalization
[source code](https://github.com/doyoungh/Hyeon_et_al_PDAC_Nature_Cancer/blob/main/00_Data_normalization.m)
also fits quantile normalization within TMT sets and across the merged cohort,
plus cohort-wide detection filters. Published processed matrices therefore need
a conditional-processing argument or independently reconstructed measurements;
they cannot simply enter the independent-donor replay. No protein outcome matrix
from this new cohort has been opened. Audit files stay under `data/raw/protein/korea/`.

Another primary source, PRIDE PXD059074, reports115 pancreatic adenocarcinoma samples
from125 collected cases. Its protocol uses survival-blocked preparation batches and
MaxLFQ protein quantification. Actual grade counts and processing independence remain
to be audited. These sample ceilings do not yet supply the384 pairs in this modeled
successful fixed-module case. The goal stays active.
