# learned-evalue

**One line:** Train a neural bettor on earlier independent units and accumulate two-sample distribution evidence on fresh batches; diagnostic only.
**Category:** bulk-rna-seq statistics
**Open-source:** Repository implementation of Pandeva et al., AISTATS 2024; Torch dependency.
**Install:** `uv sync --extra dev --extra evalue`

## When to use

Use for the null that two populations have the same distribution of expression vectors, with iid
independent units within groups and independent groups. It does not test the direction of a gene
effect, a particular mechanism, or causality. It does not replace the primary effect, primary
`p_null`, robustness checks, or the existing falsifier verdict.

Read the [plan](../../plans/PLAN-learned-evalue.md) and
[paper guide](../../research/deep-anytime-valid-hypothesis-testing/README.md).
The neural network learns a betting payoff, not an LLM evaluation policy.

## Required data contract

- Real expression input is finite, nonnegative TPM with unique gene names, donor IDs, a stable donor
  namespace, a source/release description and documented sampling assumptions. IDs alone cannot
  establish independence. Counts, log counts and TPM are not interchangeable.
- A donor cannot appear in both groups. Repeated donors are rejected unless an explicit `mean_tpm`
  aggregation protocol is declared. Aggregate only compatible technical replicates under a matched
  measurement design; different replicate counts or dependent biological samples need separate review.
- Use an external, frozen encoder whose training cohort excludes experiment units. Namespace-based
  overlap checking detects known overlap, but cannot detect aliases or a donor represented by different
  identifiers. Resolve identifiers and establish cohort separation before running.
- `aggregated` mode accepts predeclared features and requires real unit IDs and provenance.
  Feature preprocessing must be fixed independently of the tested data. `synthetic` mode is explicit
  iid simulated data and can generate row identifiers automatically.
- The caller predeclares pairing seed, encoder, features, hyperparameters and total data budget.
  Do not rerun seeds or switch encoders after seeing wealth and report the strongest outcome.

## Invocation

```python
from dnhacksbio.learned_evalue import (
    LearnedEConfig, SamplingContract, learned_two_sample_e,
)

# Xa/Xb: rows are samples, columns are the named genes.
result = learned_two_sample_e(
    Xa, Xb, genes=genes, unit_a=donors_a, unit_b=donors_b,
    sampling=SamplingContract(
        mode="expression", source="REPLACE with release and accession",
        assumptions="REPLACE with independent-donor sampling design and exclusions",
        unit_namespace="REPLACE with shared donor identifier system",
        input_scale="TPM",
    ),
    config=LearnedEConfig(encoder="data/processed/expr-pca.npz", seed=0),
)
diagnostic = result.to_dict()
```

Run with the installed repository package in the actual experiment environment. The module uses CPU
float64. The CLI benchmark sets its own thread budget; the library preserves the caller's CPU RNG
state and leaves thread settings alone. Concurrent calls that manipulate Torch's global RNG must be
isolated in separate processes.

## Results and interpretation

`status="ok"` returns **final** `e_value`, batch factors, log wealth, configuration and replay metadata.
It is possible to cross `1/alpha` earlier and finish below it. The path supports an anytime rejection
diagnostic under the declared assumptions; its running maximum is not an e-value.
Overflow serialization caps wealth conservatively; underflow becomes zero. Keep `log_final_wealth`.

`status="unavailable"` returns `e_value=None` when fewer than six complete batches are available
(48 pairs with default batch size eight). This is a data policy, not a power guarantee. Invalid data
or contracts raise `ValueError`; report the error and fix the design instead of silently retrying.

`n_pairs` includes burn-in; `n_batches` includes the final partial batch; `n_scored` counts scored
batches. `metadata.scored_pairs` counts scored pairs; `independent_units` contains per-group counts.
Two batches are unscored training/validation. Every subsequent batch is scored before it can enter
training or validation. No missing rows are silently dropped. Missing genes use stored transformed
training means, subject to the predeclared maximum fraction.

Store this as a separate diagnostic artifact. Existing RESULT submission fields and verification
decisions are unchanged; do not put this e-value or a converted p-value into the primary `p_null`
field. No investigation-wide multiple-testing guarantee is provided.

## Training and validation

Create a separate training NPZ with numeric `X`, string `genes` and string `units` arrays; no Python
object arrays. Input is one row per independent training donor. Document evaluation exclusions in
the source description. Artifacts belong in ignored `data/processed/`.

```sh
uv run --extra evalue python scripts/train_expr_encoder.py training.npz data/processed/expr-pca.npz --kind pca --components 64 --source 'release/accession; evaluation exclusions' --sampling 'independent training donors' --unit-namespace 'donor-id-system'
uv run --extra evalue python scripts/train_expr_encoder.py training.npz data/processed/expr-ae.npz --kind autoencoder --components 128 --source 'release/accession; evaluation exclusions' --sampling 'independent training donors' --unit-namespace 'donor-id-system'
uv run --extra dev --extra evalue pytest tests/test_learned_evalue.py
uv run --extra evalue python scripts/evalue_harness.py --repetitions 100 --output data/processed/evalue-validation.json
```

The PCA trainer uses a full SVD; budget memory and time for large cohorts. The autoencoder uses fixed
epochs and masked-entry MSE; tune only on separate development data. No real-cohort encoder is
bundled. Synthetic results cannot establish biological utility or prove null validity. The harness
includes identity, PCA, learned encoder, scalar, fixed projection, permutation-p and calibrated-p
comparisons, plus a clearly labeled invalid label-memorization control. Report failures and losses
against baselines. A lossy representation can entirely hide an alternative.
