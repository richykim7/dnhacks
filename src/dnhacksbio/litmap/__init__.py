"""litmap: literature to knowledge graph.

Pipeline: find (Europe PMC discovery + open-access full text) -> ingest (clean text with provenance)
-> extract (an LLM reads each paper and emits typed, quoted claims, grounded to identifiers) -> graph
(the DuckDB claim/evidence graph with merge on identity and contradiction detection) -> store (the
explorer's layer: status, tested edges, structural reads). `corpus_build` drives it from a project spec;
`promote` is the human gate into the master graph; `metadata` verifies paper identity.
"""
