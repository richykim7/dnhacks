"""The explorer faculty — curious agents that roam the knowledge graph + read full-text papers, follow
intuitions, write and run their own code in a Docker sandbox, do divergent tree-search over experiments,
and hand promising results to the rigorous verification pipeline while they keep exploring.

Modules:
  sandbox       -- Docker code-execution (ephemeral, isolated, parallel; native docker | sg fallback)
  fulltext      -- local parsed + indexed full-text store (agent reads papers without re-fetching)
  exploration   -- structured episodic memory (the tree-search tree; provenance+context welded)
  skills        -- SKILL.md library (informational + rigor guidance; open-source tools only)
  explorer      -- the explorer agent loop (tree search, self-judgment, submit-for-verification)
  verifyqueue   -- async handoff into engine falsifier -> writeback -> promotion
"""
