# Historical CIViC forecasting packet

The tracked packet in `demo/forecasting/scenarios/civic-2018-2022/` is a derived historical dataset. Read `historical.json` for scoring and graph display. Open `outcomes.json` only after predictions are saved. The separate audit `manifest.json` includes outcome counts and must also stay outside model input.

The scenario contains `id`, `title`, `dataset`, `cutoff`, `horizon`, `manifest`, `nodes`, `claims`, `evidence`, and `candidates`. Outcome packets contain `scenario_id`, `horizon`, `manifest`, `outcomes`, and later `evidence`. Python shapes live in `forecasting/records.py`; `forecasting.snapshots.load_scenario(path)` never opens sibling files. All records are plain JSON, with no model or database dependency.

## Rebuild

Download the two public releases listed in the packet manifest into a local cache, then run:

```sh
uv run python scripts/build_forecast_data.py \
  --historical data/cache/graph-forecasting/civic-01-Jan-2018.tsv \
  --future data/cache/graph-forecasting/civic-01-Mar-2022.tsv
```

The January 2018 source SHA-256 is `8895ce10b7c119856c3cbd38d8cf08fb597dbd294b06e22eaf50c35ba0db05d3`; March 2022 is `121486e06d1133cc20c669b223a32e5c7e0f30a12be1ef05b7dee93b419f1537`. Raw TSVs remain untracked. Derived data is redistributed under CIViC's [CC0 data terms](https://docs.civicdb.org/en/latest/about.html), with source URLs and content hashes retained.

## Meaning of the task

The builder selects up to 24 variants by distinct therapy-group degree in accepted historical predictive evidence, then up to 36 therapy groups by historical evidence count for those variants. Stable IDs break ties. Only endpoints still represented in the resulting graph are retained. The historical input is built before the later release is opened; there is no case selection using later labels. The candidate universe is the full Cartesian product of those endpoints minus all accepted historical predictive associations.

Each candidate asks whether new accepted predictive evidence for that variant–therapy-group association appears in the later CIViC release. An observed label requires an evidence ID absent from the entire earlier release. Edits to existing IDs cannot create positive labels. An unobserved label means “not observed under this protocol by the horizon,” not disproven. Curation additions can cite older publications; this is database-addition forecasting, not worldwide first discovery or prediction of a therapy's efficacy.

Variant IDs preserve the biological variant. Whole therapy groups are case/whitespace normalized and sorted for identity; they are never split into independent drug claims. Only commas outside parentheses delimit members, so parenthesized aliases such as `BEZ235 (NVP-BEZ235, Dactolisib)` remain one member, including nested parentheses. The old release does not distinguish combinations from substitutes or sequential use, so missing interaction types remain null. Disease, evidence direction, clinical significance, evidence level, and therapy members remain attached to every source context. Therapy aliases are not resolved; name changes may prevent matches. Publication years come only from citation text and stay null when missing; `available_at` is the release date.

Imported association IDs use a `civic:association` namespace. They are not asserted to equal the engine's ontology-normalized Claim atom IDs. `associated_with` is an index relation that may aggregate resistance, sensitivity, and conflicting evidence; inspect the contexts. `has_variant` links preserve gene/variant structure. This packet does not mutate the existing ClaimGraph or the experiment forest.

## Review

The derived packet is deterministic and source-linked. Tests cover grouped therapies, old/new citation schema, historical endpoint eligibility, temporal separation, exclusion of edited historical evidence, snapshot identity, and tracked hashes/references. No model scoring or end-to-end forecasting advantage is claimed by this data change.
