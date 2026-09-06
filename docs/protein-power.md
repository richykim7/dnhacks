# Protein success-threshold continuation

The success target remains the original plan's private-evidence release: at least
80% simulated power for minimum standardized effect 0.4, acceptable null behavior,
sufficient independent grade groups, and reviewed sampling, preprocessing, identity
and deployment privacy. External AUROC is not this power threshold. CPTAC and Fudan
have already been examined and cannot be called unopened confirmation cohorts.

## Feasibility before additional outcome access

First quantify the sample budget under an explicit one-dimensional Gaussian shift
with marginal variance one and group mean difference 0.4. This is a transparent
feasibility scenario for the declared standardized effect, not proof that the
mitotic representation or the saved nonlinear model follows that distribution.

Compute two distinct references: a known-variance, direction-known Gaussian test's
optimal fixed-horizon power; and the actual canonical odd-contrast payoff with an
oracle fixed witness g(x)=0.2x. The latter retains 16 unscored burn-in pairs and
evaluates 10,000 fresh generated streams at each prespecified budget (48, 60, 96,
128, 160, 192, 256, 384, 512). Null and effect streams use separate fixed seeds.
No stake or budget is selected using biological confirmation wealth. Report
binomial intervals for final/anytime rejection and retain all budgets. Oracle
results are planning references, never a certificate for the saved protein model.
The next model-specific study must inject the effect into the declared protein
representation, apply its actual frozen transform and witness, and preserve the
current scoring schedule. It must not relabel an easier score-space effect as the
original biological minimum effect.

## Additional source audit

The [Korean proteogenomic study](https://www.nature.com/articles/s43018-022-00479-7)
reports 196 patients with genomic/RNA data and 150 with proteomic measurements.
Thus 150, not 196, is the current protein-sample ceiling (at most 75 grade pairs
before checking group balance). Its proteome accession is PDC000248 and phosphoproteome
PDC000249. Grade counts, prior treatment, per-sample processing and overlap require
metadata audit; no numerical outcome matrix from that cohort has been opened here.
The 2026 NCI precursor study's 104 PDAC proteomes are explicitly a CPTAC reanalysis,
so that release cannot add independent donors. Source:
[NCI study description](https://dctd.cancer.gov/about/news-events/news/2026-news/pdac).

## Measured feasibility result

The L40S run completed 180,000 streams using the imported production payoff,
with peak CUDA allocation 239,075,328 bytes. Full results, fixed seeds (in code),
confidence intervals and code hash are in [the machine-readable report](protein-power.json).

| Total pairs | Scored pairs | Final detection | Anytime detection | Null anytime rejection |
|---|---:|---:|---:|---:|
| 60 | 44 | 23.19% | 30.35% | 1.27% |
| 96 | 80 | 52.11% | 63.80% | 2.57% |
| 128 | 112 | 68.47% | 79.41% | 3.51% |
| 160 | 144 | 79.05% | 88.26% | 3.90% |
| 192 | 176 | 85.75% | 92.68% | 4.02% |
| 256 | 240 | 93.42% | 97.22% | 4.12% |

The first tested budget whose final-power 95% lower bound exceeds 80% is 192 pairs;
160 qualifies for anytime detection, which is a different stopping policy. Retain
final wealth as the current release readout instead of switching policies to pass.
These results establish a plausible planning budget, not actual-model performance
or availability of 384 eligible fresh patients. At 60 pairs, even the Gaussian
oracle test using all pairs has power only 70.7% in this particular effect scenario.
This is not an impossibility claim for every multivariate biological alternative.

## Completion evidence still required

| Requirement | Current evidence |
|---|---|
| Functional exploratory tool and real trained artifacts | Merged PRs 70 and 78; local hashed models and external report |
| Original minimum effect 0.4 | Preserved; not replaced with external AUROC or a larger effect |
| Actual frozen-model native power at least 80% | Not established; oracle study cannot substitute |
| Eligible independent confirmation groups | Existing 60-pair Fudan benchmark is exposed; new-source metadata audit ongoing |
| Acceptable model-specific null diagnostics | Pending actual frozen-model simulation |
| Independent sampling/processing/identity review | Not approved; joint processing and study reuse remain material |
| Deployment-enforced private evidence boundary | Adapter and tests exist; distinct-identity deployment/review not established |

Next work: build the model-specific protein-space effect generator without using
external labels for tuning, audit Korean source metadata and normalization code,
and expand the independent-cohort inventory against the measured budget. The goal
remains active; neither this planning result nor prior external AUROC completes it.
