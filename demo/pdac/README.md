# Pancreatic cancer corpus

An explicitly curated collection of 100 full-text papers on pancreatic cancer survival, abnormal
cell division, metabolism, cellular stress and the local tumor environment. The final selection is
in `papers.json`, with per-paper identifiers, publication dates, date sources and scientific rationale.
It includes primary experimental evidence, two historical expression-study anchors, competing
mechanisms and a small number of integrative/methodological papers.

The inclusive publication boundary is **2026-01-25**. The current papers span 2007–2025. Selection
uses individual scientific review and independent metadata checks; rebuilding does not search,
rerank or substitute papers. Relevant historical citations inform the collection, but the reference
list is not imported wholesale. This is a retrospectively curated demonstration corpus; freezing it
does not by itself establish a prospective discovery benchmark or certify a model's training data.

## Build and verify

Install `uv sync --extra dev --extra litmap`. From the repository root:

```bash
uv run --extra dev --extra litmap python scripts/build_pdac_corpus.py \
  --selection demo/pdac/papers.json \
  --retrieval data/raw/pdac-retrieval \
  --output data/corpora/pdac-frozen --fetch --index

uv run --extra dev --extra litmap python scripts/build_pdac_corpus.py \
  --output data/corpora/pdac-frozen --verify
```

`--fetch` retrieves the exact selected identifiers through the existing full-text resolver, including
Europe PMC, PMC, OpenAlex, Unpaywall and alternate public publisher/repository locations. Omit it when
using an already validated retrieval cache. Source availability and access permissions can change;
unavailable or incomplete material causes the build to fail rather than silently reducing the count
or including abstracts. Rerunning against an existing frozen manifest is refused: verify it, or build
a separately named version. Network attempts and rejected sources stay in the retrieval directory.

Every admitted paper retains its original XML/HTML/PDF, readable text, Markdown, source URL/license,
parser version and local image assets. JATS includes floating figures and captions outside the body;
PMC image packages and official article representations supply author-manuscript images. PDF sources
use the existing PyMuPDF4LLM conversion, including rendered picture regions. Figure variants can have
multiple files; image-file counts are not counts of unique numbered scientific figures.

The frozen output contains `MANIFEST.json`, its SHA-256 checksum, checksums for every source/text/image,
`papers/`, `prompt.txt`, `corpus_card.md`, and an offline `index.html` with individual article readers.
Open that index directly in a browser. Only the chosen 100 papers enter the frozen folder. Full text
and image assets are local and ignored by Git; this directory commits curation metadata and workflow
instructions only.

`--index` also writes `pdac-frozen_kg.duckdb` with all 100 complete texts, using the existing store schema.
The app discovers it as an adopted corpus named `pdac-frozen`. Keyword search works immediately;
semantic embeddings additionally require the optional `llm` dependencies and embedding model.
The database is a derived artifact, outside the source freeze checksums. This command **does not run
LLM claim extraction** or discovery experiments; full-text indexing and claim-graph extraction are
separate stages. The research prompt is kept separate from the corpus's descriptive card.

The initial local build contains 7,212,281 readable characters, 856 distinct image files referenced
893 times, and 100 originals (89 JATS XML and 11 article HTML). All image files were decoded and checked;
all selected original, text and image hashes passed verification. Several imprecise metadata dates
were corrected from explicit source publication dates. The known-answer article and its experimental
results are kept outside this corpus.
