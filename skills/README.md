# Skills — method guides the explorer reads before writing code

Each subdirectory holds one `SKILL.md`: informational, rigorous guidance for a method a competent
computational biologist would stand behind. A skill is not a frozen function. The explorer reads it,
then writes its own experiment code inside the sandbox; the skill says what the method is, when to reach
for it, and the statistical invariants the code must not violate. `TEMPLATE.md` is the canonical layout.

## The trust boundary (load-bearing — read first)
The model chooses what to test and HOW; the code it writes computes the statistic. Only a result that
reaches the verify queue as an audited statistic (`trust_class="audited-statistic"` on the `ToolResult`
contract in `src/dnhacksbio/methods.py`) may ground a KILL. An `exploratory` result can suggest a direction
but is never the basis of a verdict. Rigor lives in the null model and the falsifier
(`src/dnhacksbio/falsifier.py`), not in prose.

## The common result contract — `ToolResult`
Every experiment that wants a verdict reports these fields (the falsifier judges this one shape):

| field | meaning |
|---|---|
| `tool` | the method name |
| `effect` | point estimate in native units |
| `p_null` | p-value vs the stated **null model**; Phipson–Smyth `(b+1)/(m+1)` style — **never floors at 0** |
| `null_model` | one line: what was permuted/shuffled/resampled to build the null |
| `n_units` | sample size at the **exchangeable unit** (cell lines / donors / shuffled sequences — never the gene) |
| `robust` | bool — the robustness check held (leave-one-group-out, leave-one-region-out, …) |
| `expected_sign` | `+1 / -1 / 0` — what the **hypothesis** predicts; `0` = two-sided |
| `observed_sign` | `sign(effect)` |
| `trust_class` | `"audited-statistic"` or `"exploratory"` |
| `dataset`, `dataset_sha256`, `method`, `provenance` | reproducibility metadata |

The falsifier's soundness floor, in order: no estimable effect → `invalid`; too few units →
`underpowered`; a malformed p → `invalid`; direction wrong (when `expected_sign != 0`) → `refuted`;
p above the null threshold → `inconclusive`; robustness failed → `refuted`.
Missing or invalid required result fields are `malformed-result`; missing robustness never means pass.
E-value/e-BH helpers are standalone diagnostics, not an active falsifier gate.
**Gate on the number only when `trust_class == "audited-statistic"`.**

## SECURITY (non-negotiable, applies to every skill)
- **No identifying info to any API, ever.** Placeholder email only (`research@example.org`); never a
  real name, email, key, or account.
- **Public / open-access data only.** No paywalled or license-restricted sources; no scraping behind auth.
- Prefer **sized/on-demand** fetches (region sequences, summary endpoints) over multi-GB downloads.

## Data-backed skills
- `depmap_dependency/` — differential dependency (driver status ↔ gene dependency) over the mounted
  `/data/interim/explorer_ready/` tables (see its SKILL.md).
- `co_essentiality/` — genome-wide co-essentiality partners of a query gene (DepMap gene-effect matrix).
- `geo_expression/` — loading and harmonizing a public GEO cohort (the `geoharmonize` helper).
- `expression-experiment/` — submit a declared independent-donor TPM comparison using the repository
  command; record its receipt without a RESULT or a verification submission. The agent writes input
  preparation code only; this command does not return analysis statistics.

- `dependency-experiment/` — submit an operator-registered Chronos comparison and record only its
  durable receipt. No result statistics or verification submission are returned by this command.

- `drug-response-experiment/` — submit an operator-registered biomarker/AUC association; record the
  durable receipt and continue without a RESULT or verification submission. No drug-response uploads.

Every other directory is a method guide with its own data-source section.
