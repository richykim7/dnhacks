# Experiment artifacts

Write deliverables under `/work/output` (also `DN_ARTIFACT_DIR`). This directory is collected before
the sandbox is removed. A file elsewhere is not a durable artifact. Never read credentials or copy
secrets into outputs. Text redaction is best-effort, not permission to include sensitive material.

Write `manifest.json` as `{"schema_version":1,"artifacts":[...]}`. Each artifact declares `path`
(relative to the output directory), `kind: "molecular_structure"`, `format: "pdb"` or `"cif"`, and
`provenance` with `category` (`experimental_reference`, `prediction`, `derived_geometry`, or
`illustration`), `source_ids` (array), `tool`, and `tool_version`. Include input hashes, units, and
chain/residue conventions when applicable. Do not label generated geometry as an experimental structure.

Limits: 8 artifacts per experiment, 20 MB each / 40 MB total, 100,000 atoms per structure. Only regular
contained files are accepted; symlinks, traversal, unknown renderers and invalid structures are rejected.
No HTML, scripts, external artifact URLs or automatic fallback structures. Results may have no renderable
artifact. Failed experiments may retain diagnostics, explicitly associated with the failure.

Statistics still use the established `RESULT:` JSON contract. Artifact availability does not validate
the science or imply a prediction service exists. Geometry colours are decorative unless explicitly
backed by recorded measurements and provenance.
