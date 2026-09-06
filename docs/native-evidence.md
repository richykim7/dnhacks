# Native frozen association evidence

`dnhacksbio.native_evidence` provides the shared `native-two-view-four-term-v1`
kernel and an operator-only SQLite process ledger. This is infrastructure, not
an audited biological confirmation design. Adapters must enforce access,
independent sampling, immutable measurement, representation separation and
predeclared power before enabling a private experiment.

`association_factor([c11,c22,c12,c21], stake)` computes
`1 + stake * (c11+c22-c12-c21)/4`, with scores bounded in [-1,1] and
stake in [0,.9]. Under the registered independence null and fresh IID donor
pairs all four conditional expectations coincide. One two-donor block supplies
one factor; cells or the four critic evaluations are not replicates.

`PrivateProcessStore(directory)` supports:

- `register(receipt, spec)`: durable receipt only, with aliases sharing the hash
  of the complete immutable specification.
- `advance(receipt, number, donors, x, y)`: operator-only atomic transition with
  a frozen `tanh(x W y)` critic. Locked donor order, observations, factor, cursor,
  critic snapshot and log wealth commit together. Identical retries do nothing;
  conflicting retries fail. Deterministic replays cannot increment twice.
- `export(receipt)`: operator-only final log wealth and diagnostic path. Running
  maxima are threshold-crossing diagnostics, not replacement e-values.

The specification declares kernel, measured null, population, panel, two model
hashes, QC/data/crosswalk/acquisition hashes, family/parent, sampling assumptions,
exclusions, frozen weights/stake and ordered eligible canonical donors. Schedule
is `fully-frozen-v1`; optimizer and RNG snapshots are explicitly null because
this version has neither adaptive updates nor scoring randomness. Adaptive
score-before-train requires a future version with atomic optimizer/RNG state.

The reuse policy `globally-disjoint-canonical-donors-v1` rejects consumed donors
across every process **in the same store**. All adapters in an investigation
must use the same private ledger directory. Separate directories cannot enforce
cross-tool reuse. Canonical identity must be established by an external audited
crosswalk; different strings do not prove biological independence. An unused
odd final donor contributes no factor. No unrelated process multiplication is
implemented.

Keep the ledger behind an actual filesystem/service identity boundary. Owner
mode bits and a separate process alone do not hide data from a discovery agent
running as that owner. No HTTP result route or discovery integration is provided
by this core. Adapters are responsible for receipt-only transport and private
logs/errors/results. Tests cover kernel symmetry and bounds, 10,000 synthetic
null streams, atomic crash rollback, replay equivalence and duplicate-donor
rejection; they do not establish power or assay validity.
