# depmap_dependency
**One line:** Does a driver EVENT in gene A (loss-of-function or gain) change a cell line's dependency on gene B?
**trust_class:** audited-statistic
**How to run it:** write your own analysis code reading the mounted tables at `/data/interim/explorer_ready/`
(`cell_line_meta.parquet` + `gene_dependency.parquet`) — the exact schema + a worked example (LOF-vs-WT with a
permutation null over the cell-line unit) is in `/data/interim/explorer_ready/SKILL.md`. Follow the
`experimental-rigor` skill for the ordinary analysis result contract.

## Tests (hypothesis shape)
`A-<event> → selective dependency on B` — i.e. lines carrying the A event need B more (or less) than lines
without it. The workhorse for the KG's mechanistic edges when both A and B are genes screened in DepMap.
- **example:** *DRIVER-LOF → stronger dependency on PARTNER* (expected `−` ΔChronos) — a direct test of
  a driver↔partner KG edge in a functional-genomics readout.

## Inputs → Outputs
Inputs: `A` (HGNC symbol), `B` (HGNC symbol), `mode` (`"lof"` loss | `"gain"` amplification/expression),
optional `augmentations` (generic covariate specs `expr:GENE` / `cn:GENE` / `mut:GENE` the engine names),
`n_perm`. `scan(A)` is the cheap messy first pass over all B; `test(A,B)` is the rigorous single pair.
Outputs (`TestResult` → adapt to `ToolResult`): `beta` (adjusted ΔChronos) → `effect`; `std_effect` →
`effect_size`; `p_perm` → `p_null`; `lolo_sign_stable` → `robust`; `n_lof`/`n_wt` → `n_units`.
- **expected_sign convention:** synthetic-lethal / "needs B more" ⇒ ΔChronos more negative ⇒ `expected_sign
  = -1`. "Loses dependency on B" ⇒ `+1`. The mapper sets this from the claim's polarity/direction.

## Audited statistic and null model
OLS of Chronos(B) on `A_event` + a **generic confounder floor** (lineage one-hot, copy-number of B,
mutation burden, proliferation proxy) + engine augmentations; coefficient = adjusted ΔChronos with robust
HC3 SE + 95% CI. **Primary null = permutation at the CELL-LINE unit** (never the gene): the A-label is
permuted across lines, refit via Frisch–Waugh–Lovell, `p_perm = (#|b|≥|obs| + 1)/(n_perm + 1)`
(Phipson–Smyth, never 0). Robustness = **leave-one-lineage-out** sign stability. Negative controls =
`pan_essential_control` (POLR2A/RPL3/… must not show A-selectivity).

## Data source + fetch (SIZED — no giant downloads)
**Local**, ingested: `data/interim/depmap_24q4/chronos.parquet` (+ cn, expression, damaging,
model). Loaded via `depmap_harmonize.DepMap`. No network. `dataset="DepMap 24Q4"`, sha filled at execute.

## Gotchas / when not to use (operationalization-mismatch triggers)
- Needs **≥8 lines in each of A-event / WT** (`MIN_GROUP`); rare events → `underpowered`, don't force.
- Only for genes **screened in DepMap** (CRISPR-KO Chronos). Non-coding elements, isoform-specific or
  protein-complex-level claims → `operationalization-mismatch`.
- "Significant" ≠ "real": with ~1000 lines a tiny `std_effect` can be significant → the `trivial` floor.
- The confounder floor must stay **answer-agnostic** (generic, relative to B) — never add an
  answer-specific covariate (that's HARKing; the design-card hash guards it).

## Minimal worked example
`Executor().test("DRIVER", "PARTNER", mode="lof")` → `TestResult(beta<0?, p_perm, std_effect, lolo_sign_stable…)`.
Map to `ToolResult(effect=beta, effect_size=std_effect, p_null=p_perm, expected_sign=-1,
robust=lolo_sign_stable, trust_class="audited-statistic", dataset="DepMap 24Q4")`. Falsifier then gates on
direction (β<0), permutation null, effect floor, LOLO, BH-FDR over the run's family.
