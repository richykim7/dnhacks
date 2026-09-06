# Tracked source architecture map

Graphify 0.9.55 mapped the tracked source at DNHacks commit
[`e04e9ff8bbe6a1abce23ba022518dbdde3ebb370`](https://github.com/richykim7/dnhacks/tree/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370).
This is a source navigation artifact, separate from the product's scientific knowledge graph.
No repository implementation, configuration, datasets or credentials were changed or executed.

Open [graphify-out/graph.html](graphify-out/graph.html) directly in a browser. Search for
`Explorer`, `KGStore`, `run_scenario`, `prepare_reasoning` or `Handler`, click a result,
and follow its neighbors. Community checkboxes reduce the visible graph. The required
vis-network 9.1.6 JavaScript is included locally, so viewing the map makes no external requests.

## Coverage

| Measure | Result |
| --- | ---: |
| Tracked code files inventoried | 137 |
| Files parsed by AST extractors | 130 |
| Parsed languages | 99 Python, 16 TypeScript, 14 TSX, 1 MJS |
| Inventoried but not parsed | 6 CSS; 1 HTML entry point |
| Tracked code lines in inventory | 34,579 |
| Graph nodes | 1,860 |
| Relationships in exported graph | 3,727 |
| Communities | 109 |
| `EXTRACTED` relationships | 3,521 |
| `INFERRED` relationships | 206 |
| Comment/docstring rationale nodes | 510 |
| Model input/output tokens | 0 / 0 |

The input was a temporary snapshot built from `git ls-files` and `git show HEAD:<path>`;
only code extensions under `src/`, `frontend/`, `scripts/`, `tests/` and `research_spikes/`
were copied. The inventory records every path, content hash, size, line count and parse status.
No ignored files, private documents, `.env` files, dataset packets, package directories,
Git metadata or credential files were put in the corpus. Graphify classified the HTML file
as a document, which `--code-only` skipped; its extension detector skipped the six CSS files.

The map therefore describes this exact tracked commit, not uncommitted work, installed
packages, runtime data or future merges. All 130 parsed files have graph nodes. The source
labels `3dmol`, `node:fs/promises`, and the empty label are external/unattributed graph nodes,
not additional source files read by the tool.

## Five central files

Centrality here means the number of distinct **other tracked files** linked through any
exported Graphify relationship. It is undirected adjacency, not execution frequency or a
runtime criticality score. Excluding package initializer shims, these five files lead that count; their responsibilities were
checked against their source.

| File | Neighbor files | Responsibility |
| --- | ---: | --- |
| [`src/dnhacksbio/explorer/explorer.py`](https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/src/dnhacksbio/explorer/explorer.py#L319) | 17 | Live ReAct explorer: reads graph/memory, dispatches actions, runs experiments, forks and judges branches, submits results for verification. |
| [`src/dnhacksbio/litmap/store.py`](https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/src/dnhacksbio/litmap/store.py#L56) | 13 | `KGStore`: saved scientific graph access, claim status, vector storage and engine test/review records. |
| [`src/dnhacksbio/webui/data.py`](https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/src/dnhacksbio/webui/data.py) | 11 | Reads recorded reasoning traces and DuckDB state to construct investigation, graph and review views. |
| [`frontend/src/App.tsx`](https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/frontend/src/App.tsx#L43) | 11 | UI entry point: project selection, routes and research views, including forecasting and investigations. |
| [`src/dnhacksbio/webui/server.py`](https://github.com/richykim7/dnhacks/blob/e04e9ff8bbe6a1abce23ba022518dbdde3ebb370/src/dnhacksbio/webui/server.py#L95) | 11 | Local HTTP/SSE handler connecting the frontend to investigations, projects, graph, review and forecasting adapters. |

The package initializer `webui/__init__.py` also has 13 neighboring files even though
its source contains only a docstring: Graphify uses it as an import anchor. It is excluded
from the five implementation modules above. This is a concrete example of why graph
centrality alone does not establish runtime importance.

The latest snapshot includes the new `explorer/runtime.py` journal (10 neighboring files),
`webui/runtime.py` API and frontend runtime components, as well as the Evidence changes.
An initial `37dabe4` snapshot was evaluated separately in temporary analysis storage; this update adds
18 inventoried files, 16 parsed files, 157 graph nodes and 400 exported relationships.

Three execution paths deserve explicit names when using this map. The live agent is
`Explorer`; the frozen historical structural experiment is `forecasting/runner.py`'s
`run_scenario`. The controlled model-memory experiment is `forecasting/reasoning.py`.
Finding those modules in one source graph does not establish that the forecasting policy
is integrated into the live explorer's branch selection. Cross-language API links and data
artifacts are not automatically traced by this code-only run.

## What the relationships establish

Graphify's [official repository](https://github.com/Graphify-Labs/graphify) describes local
Tree-sitter extraction and distinguishes directly extracted relationships from resolution
inferences. We used upstream commit
[`c9f99018774e2e0380e9f65b3959944559a0d5f6`](https://github.com/Graphify-Labs/graphify/tree/c9f99018774e2e0380e9f65b3959944559a0d5f6),
whose [package metadata](https://github.com/Graphify-Labs/graphify/blob/c9f99018774e2e0380e9f65b3959944559a0d5f6/pyproject.toml)
identifies `graphifyy==0.9.55`. The installed CLI is `graphify`.

The 3,727 exported relationships comprise 1,410 `calls`, 902 `contains`, 510
`rationale_for`, 243 `method`, 207 `imports_from`, 174 `imports`, 150 `references`,
67 `uses`, 38 `indirect_call`, 23 `inherits`, and 3 `dynamic_import` links.
These are Graphify's output labels, not independently established runtime facts.

The [resolution implementation](https://github.com/Graphify-Labs/graphify/blob/c9f99018774e2e0380e9f65b3959944559a0d5f6/graphify/extract.py)
uses import context, symbol labels and language-specific rules to resolve targets. An AST
call site establishes syntax; resolving its receiver or callee may still be heuristic.
`EXTRACTED` and numerical confidence are tool classifications, not measured correctness
probabilities. Dynamic dispatch, callbacks, imports through aliases, runtime-generated
code and framework behavior can be incomplete or misleading. No independent call links
were invented for this report or the file projection.

The exported NetworkX graph explicitly has `directed=false` and `multigraph=false`.
Its visual edges are therefore **not a directed call graph**, and distinct relationship
kinds between the same endpoints can collapse during graph building. Do not derive
control-flow proofs, exact dependency closure or implementation guarantees from its paths.
The 510 rationale nodes come from source comments/docstrings and are not executable units.

Community detection used NetworkX Louvain, because the optional Leiden packages were not
installed. The [upstream cluster implementation](https://github.com/Graphify-Labs/graphify/blob/c9f99018774e2e0380e9f65b3959944559a0d5f6/graphify/cluster.py)
uses deterministic ordering/seeding. Community names were produced with its local
`label_communities_by_hub` helper. They are navigation labels derived from a central symbol,
not a semantic architecture assessment. A second clean extraction reproduced all nodes,
relationships and community IDs exactly, excluding the subsequently added hub-name field.

## Execution and artifacts

The tool was cloned into `/tmp/dnhacks-graphify-tool`, pinned to the commit above, then
installed into `/tmp/dnhacks-graphify-venv` with `uv venv` and
`uv pip install --python /tmp/dnhacks-graphify-venv/bin/python /tmp/dnhacks-graphify-tool`.
[dependencies.txt](dependencies.txt) records the installed dependency versions. No global
skill, hook, MCP configuration or assistant integration was installed.

The exact extraction and report commands were:

```sh
env -i PATH=/tmp/dnhacks-graphify-venv/bin:/usr/bin:/bin PYTHONHASHSEED=0 \
  /tmp/dnhacks-graphify-venv/bin/python \
  /tmp/dnhacks-architecture-map/latest/run_graphify_local.py \
  extract /tmp/dnhacks-architecture-corpus-e04e9ff \
  --code-only --no-dedup --max-workers 1 \
  --out /tmp/dnhacks-architecture-map/latest --timing

env -i PATH=/tmp/dnhacks-graphify-venv/bin:/usr/bin:/bin PYTHONHASHSEED=0 \
  /tmp/dnhacks-graphify-venv/bin/python \
  /tmp/dnhacks-architecture-map/latest/run_graphify_local.py \
  cluster-only /tmp/dnhacks-architecture-map/latest --no-label --timing
```

The small local wrapper invokes the real CLI while rejecting network access, home-file
reads and non-Git subprocesses. Both runs recorded no such attempts. `--no-dedup` avoids
fuzzy entity merging; `--no-label` prevents the clustering CLI's optional model naming pass.
Before clustering, the upstream helper's deterministic hub labels were saved locally.
`cluster-only --no-label` incorporated those saved labels without model calls. This does
not add or modify source edges.
The CLI was independently inspected before execution; its
[`extract` and `cluster-only` branches](https://github.com/Graphify-Labs/graphify/blob/c9f99018774e2e0380e9f65b3959944559a0d5f6/graphify/cli.py)
show the code-only and no-label gates.

The generated HTML's fixed CDN script reference was changed to the included local
vis-network asset. Its CDN-specific integrity/crossorigin attributes were removed for
`file://` viewing; the exact downloaded asset hash is recorded in `audit-summary.json`.
Upstream Graphify notices and the vis-network license accompany the artifact.

- [source-inventory.json](source-inventory.json): exact tracked source coverage and hashes.
- [graphify-out/graph.json](graphify-out/graph.json): complete exported Graphify graph.
- [module-map.json](module-map.json): undirected file projection with every contributing Graphify relationship.
- [graphify-out/GRAPH_REPORT.md](graphify-out/GRAPH_REPORT.md): upstream-generated community report.
- [audit-summary.json](audit-summary.json): tool/source pin, counts, repeatability and limitations.
- [browser-check.json](browser-check.json): canvas, search, node inspection, zero page errors and zero external requests.
- [map-preview.png](map-preview.png): browser capture with the live Explorer selected.

Extraction took 6.8 seconds and clustering/export took 1.3 seconds in this environment.
The extraction worker wrote temporary analysis artifacts; the parent copied the selected
map, report, inventory, browser evidence and licenses into this documentation directory.
The worker validated the interactive artifact and source coverage. Repository gates for
the full documentation change are recorded in [the task review](../../../tasks/todo.md).

The audit wrapper and temporary corpus are machine-local analysis helpers, not application
files or installed project tooling. To regenerate the source relationships elsewhere,
install the pinned upstream package in an isolated environment, reconstruct the allowlisted
files at the pinned commit using the inventory, and run the equivalent upstream CLI:

```sh
graphify extract /path/to/tracked-code-snapshot --code-only --no-dedup --max-workers 1 --out /path/to/map
graphify cluster-only /path/to/map --no-label
```

That plain CLI invocation omits the audit's local access guard and deterministic hub-name
postprocessing. Copying the generated HTML's vis-network dependency locally is also an
explicit packaging step, not behavior implied by those commands. The exported graph and
source inventory are the checkable artifacts; this map does not automatically update when
main changes. Reconcile the snapshot commit before using it as evidence of current behavior.
