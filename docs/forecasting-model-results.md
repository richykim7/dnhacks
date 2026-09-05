# Frozen CIViC model experiment: no positive cohort

All three real model conditions completed, but none of the 20 frozen candidate associations
was recorded as a positive in the later CIViC release. **AP and AUROC are undefined; P@5 is
zero for every condition. This run cannot establish forecasting superiority.** The historical
cohort and predictions remain unchanged after opening the outcome packet.

The [evaluation artifact](../demo/forecasting/reasoning/civic-model/evaluation.json) contains
complete labeled rankings, prediction-file hashes, source-parity checks, usage and eligibility
counts. The [comparison](../demo/forecasting/reasoning/civic-model/comparison.json) preserves
prompts, responses and graph revisions; the [cohort](../demo/forecasting/reasoning/civic-model/cohort.json)
and [forecasts](../demo/forecasting/reasoning/civic-model/forecasts.json) were saved before evaluation.

| Condition | Later-recorded positives / candidates | AP | AUROC | P@5 |
| --- | --- | --- | --- | --- |
| Flat log | 0 / 20 | undefined | undefined | 0 / 5 |
| Static graph | 0 / 20 | undefined | undefined | 0 / 5 |
| Evolving graph | 0 / 20 | undefined | undefined | 0 / 5 |
| Historical popularity, same evidence | 0 / 20 | undefined | undefined | 0 / 5 |

The fixed query is **ERBB2 AMPLIFICATION** (`civic:variant:306`). Selection used descending
historical source degree, then query ID; its 20 candidates used historical target degree,
then candidate ID. Recomputing that selection reproduces the frozen cohort exactly. The
cutoff is 2018-01-01 and the outcome horizon is 2022-03-01. Labels mean later CIViC release
inclusion, not first scientific discovery or treatment benefit. Absence in this release
protocol does not experimentally disprove an association.

The four complete rankings include readable therapy-group labels and candidate IDs in the
artifact. They cover Gefitinib; Panitumumab; Regorafenib; Erlotinib; Docetaxel/Selumetinib;
Trametinib; BYL719 (Alpelisib); Ridaforolimus/Temsirolimus; BEZ235/Selumetinib; Crizotinib;
Vemurafenib; RO4987655; Dabrafenib; Docetaxel; BEZ235 (NVP-BEZ235, Dactolisib); BAY 86-9766;
Afatinib/Erlotinib/Gefitinib; Everolimus; AZD5363; and Dabrafenib/Trametinib. Slashes here
separate members of the source therapy group; they do not assert combination treatment.

## Matched evidence, measured usage

Each model condition used `claude-sonnet-5`, two steps, one attempt per call, low effort,
thinking disabled, a one-turn ceiling and a 4,000-output-token ceiling per call. All six
calls succeeded. Every condition received the same six evidence rows at step one and the
same six additional rows at step two: 12 evidence rows from 12 distinct PubMed sources.
The source packet and prompt hashes were independently recomputed before outcomes were
opened. Static graph still receives every later claim in its text log; evidence is not withheld.

| Condition | Calls | Uncached input | Cache creation input | Cache read input | Total input | Output |
| --- | --- | --- | --- | --- | --- | --- |
| Flat log | 2 | 4 | 28,931 | 0 | 28,935 | 5,199 |
| Static graph | 2 | 4 | 28,940 | 0 | 28,944 | 5,111 |
| Evolving graph | 2 | 4 | 24,789 | 0 | 24,793 | 5,098 |

Usage sums the top-level SDK usage messages. Nested `iterations` repeat those counts and
are not added. These are equal allocation ceilings, not equal consumed tokens. No dollar
cost or efficiency advantage is inferred from this single run.

The additional **historical popularity** baseline is the number of distinct historical
neighbors of the target among claims supported by exactly these same 12 evidence rows.
It was computed before opening outcomes, with the same 20 candidates and no model calls.
Its information budget is matched; its compute budget and representation differ. The
report consequently marks the combined four-way budget comparison as `different`.

## Scope and reproduction

This is a functional experiment in model-created and model-consumed graph memory. Retrieval
and the branch scheduler were held fixed. Citation checks establish identity and historical
availability, not entailment or scientific truth; every model hypothesis remains unverified.
Modern model pretraining may contain post-cutoff knowledge, so historical retrieval alone
cannot prove historical ignorance. One query and one model trajectory per condition provide
no general superiority estimate. The separate 683-candidate structural report uses a different
cohort and cannot be compared directly with these numbers.

The existing evaluator computes every metric; no new metric implementation was introduced.
The following reproduces its metric fields from the frozen artifacts, validates their byte
hashes first, and computes the historical comparator before reading outcomes:

```python
from hashlib import sha256
import json
from pathlib import Path
from dnhacksbio.forecasting.evaluation import compare_forecasts
from dnhacksbio.forecasting.scoring import score_candidates

p = Path("demo/forecasting/reasoning/civic-model")
s = Path("demo/forecasting/scenarios/civic-2018-2022")
expected = {
    "comparison.json": "eb949a7b7cb2684112c811c01d18745a7b07853378ee08a3c1e3842b0d981e34",
    "cohort.json": "232a43500dbf49e00429c617e7a54f90a6f7fab1c98737ef4944a27dbbebf220",
    "forecasts.json": "fad6ccfa9640687b122bcd0984f20e42fea83743e6f38cc4eea6f37739e2a0ef",
}
for name, digest in expected.items():
    assert sha256((p / name).read_bytes()).hexdigest() == digest
comparison = json.loads((p / "comparison.json").read_text())
cohort = json.loads((p / "cohort.json").read_text())["candidates"]
frozen = json.loads((p / "forecasts.json").read_text())
assert comparison["comparison_ready"] and comparison["origin"] == "model"
assert all(row["status"] == "complete" for row in comparison["conditions"].values())
scenario = json.loads((s / "historical.json").read_text())
visible = {eid for batch in frozen["protocol"]["evidence_batches"] for eid in batch}
models = dict(frozen["models"])
models["historical_popularity"] = score_candidates(
    {**scenario, "candidates": cohort}, evidence_ids=visible, method="popularity")
ids = {row["id"] for row in cohort}
outcomes = [row for row in json.loads((s / "outcomes.json").read_text())["outcomes"]
            if row["candidate_id"] in ids]
report = compare_forecasts(cohort, models, outcomes)
for name, model in report["models"].items():
    m = model["overall"]
    print(name, m["observed_count"], m["average_precision"], m["at_k"]["5"]["precision"])
```

The full audit also replays historical selection, verifies every step's complete candidate
set, checks prompt hashes and reconstructs source-packet hashes from acquired evidence.
Those validation results and exact historical/outcome/evaluator file hashes are saved in
`evaluation.json`. Neither this artifact nor this document reselects candidates after labels
are known.
