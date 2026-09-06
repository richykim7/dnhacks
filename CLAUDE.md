@AGENTS.md
@ARCHITECTURE.md

# Working agreement for this repo

## GPU compute — read before planning training

Read `gpu-ssh-handoff/README.md` for the available remote GPU and connection instructions.
Use `gpu-ssh-handoff/connect.sh` to verify the live GPU before selecting CPU/GPU run budgets.
The directory is local and ignored; use its SSH launcher without reading credential files or
copying connection details into tracked documentation. Shared repository rules are in `AGENTS.md`.

## Working rules

1. **Explain as you build**, in plain prose. Keep key terms, define them in passing, no decorated callout boxes.
2. **Pressure-test rather than reassure.** Surface flaws and run the adversarial check; accuracy over agreement.
3. **Lazy about plumbing, never about rigor.** Reuse what is in the repo, prefer the stdlib, no abstraction with
   one caller. Never trade away input validation, error handling, or a reasoning agent's rigor for a shorter diff.
4. **Observe every run.** Unit-test the math first, then integration, then the smallest possible live slice.
   Watch runs as they go and key completion on the run's own terminal marker.
5. **Verify UI changes by looking at them.** Screenshot light and dark and check the geometry.
6. Never commit secrets, credentials, personal identifiers, or publisher full text. Never read credential files.
7. `src/dnhacksbio/` is the live engine: `explorer/` (the reasoning agent), `litmap/` (literature to
   knowledge graph), `falsifier.py` + `methods.py` (the rigor layer), `llm.py` (model seam),
   `webui/` (review dashboard). Check callers before crediting a capability.
