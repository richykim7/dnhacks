# depmap_dependency
**One line:** Explore whether a declared driver event is associated with Chronos dependency on a target.
**trust_class:** audited-statistic
**How to run it:** Read local `cell_line_meta.parquet` and `gene_dependency.parquet` under
`/data/interim/explorer_ready/`; inspect their schema and provenance before writing an analysis.
Follow `experimental-rigor` for the ordinary result contract. For an operator-registered private
comparison, load `dependency-experiment` and use its receipt-only command instead.

## Endpoint and units
Chronos measures complete gene-knockout dependency: more negative means stronger dependency.
Deleted-minus-intact effects therefore have negative expected sign for stronger dependency.
Use one independent donor-derived model per unit; resolve aliases, shared donors, repeated screens
and release overlap before defining groups. Different releases of the same models are not confirmation.

`depmap_harmonize.DepMap` provides local 24Q4 parquet readers. Its generic `lof_call` combines mutation,
copy loss and expression silencing; it is **not** a curated deletion annotation. Verify the actual
release-specific copy-number scale before using thresholds. Missing event calls remain unknown.

## Null and limitations
OLS covariate adjustment with HC3 uncertainty does not establish label exchangeability. Global
shuffling across lineages, screen libraries or other heterogeneous populations can be invalid even
after adjustment. A permutation analysis requires an explicit invariance justification conditional
on frozen scores, eligibility, blocks and group counts. Shuffle only at independent biological units
within prespecified defensible blocks. If that assumption is unsupported, report unavailable evidence.

For a frozen one-sided statistic count ties conservatively. Exact enumeration uses the full-orbit
exceedance fraction; sampled uniform permutations use `(1 + exceedances)/(1 + permutations)`.
Do not add a plus-one correction to an already complete orbit or report zero p-values.
Eight units per group is an operational floor, not a power calculation. Do not expand a narrow cohort
by inspecting outcomes. Leave-one-lineage-out checks and negative controls are diagnostics, not a
repair for a misspecified permutation null. Association does not establish causal synthetic lethality
or sensitivity to a drug with a different intervention mechanism.

## Ordinary verification
Only submit a complete declared ordinary analysis result under `experimental-rigor`. The falsifier
checks required fields, finite effect, unit floor, valid p, predicted direction, significance and
robustness. It does not impose a minimum-effect threshold or apply run-wide BH-FDR. Human review
and a written note are required for promotion; this guide supplies neither an answer key nor a verdict.
