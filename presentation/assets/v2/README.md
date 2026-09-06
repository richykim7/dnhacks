# Editorial presentation backgrounds

AI-generated conceptual cellular illustrations, created with the user-authorized LaoZhang provider through the existing `rsimg` adapter. These images are decorative: they are not microscopy, molecular structure data or experimental results.

- `cover.jpg` (delivery copy; original: `cover/out_0.png`): mint membrane arc with warm amber core on the right; dark left half reserved for editable PowerPoint typography.
- `closing.jpg` (delivery copy; original: `closing/out_0.png`): quiet cellular landscape along the bottom and right; spacious dark upper-left for closing typography.

Both originals are 5504 × 3072 PNGs (the provider response to 16:9 / 4K). The deck uses the smaller `cover.jpg` and `closing.jpg` delivery copies. The large original PNGs are preserved locally and are not committed to the repository. Their original hashes and dimensions remain recorded in the generation manifests and provenance. Use PowerPoint cover/crop placement for exact slide framing.

The exact prompts are in `cover.prompt.txt` and `closing.prompt.txt`. Each image directory contains the rsimg `manifest.json`; `provenance.json` includes SHA-256 hashes, operation IDs, dimensions, visual review and the task ledger records. Both images were accepted after visual inspection on the first attempt, with no retries.

Recorded task ledger cost: **$0.18 USD** ($0.09 per image), within the **$1.00 USD** authorized session budget. LaoZhang costs in rsimg are recorded estimates from the configured per-image price, not independently verified provider billing receipts. The existing inference key lacks permission to query the account's final balance. No credentials were copied into these artifacts.

Provider pricing reference: https://docs.laozhang.ai/en/api-capabilities/nano-banana-pro-image
