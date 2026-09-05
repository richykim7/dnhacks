"""Path-encoded run_id: the branch's self-describing lineage key.

A run_id is a `~`-separated path. The first segment is the investigation (the root); each fork appends a
child index. From the id alone, by string operations, we recover lineage, depth and tree membership, with
no lineage table and no recursive query:

    myrun                      root                depth 0
    myrun~1                    2nd fork off root   depth 1
    myrun~1~0                  1st child of ~1     depth 2
    myrun~1~3~0                deeper              depth 3

- root       = the investigation (segment before the first `~`)
- depth      = number of `~` (0 = the root run itself)
- ancestors  = self + every prefix down to the root (the lineage a branch may read)
- child      = append `~<idx>`

`~` is reserved: the base investigation id must never contain it (enforced at mint time).

This id is the scoping key over the exploration log, the KG and the verify queue. It is distinct from the
SDK's opaque session UUID (the fork handle). The run_id -> sdk_session_id map is written by `Explorer` at
the end of every `run()` to `<trace_dir>/sessions_<root>.json` (`explorer.sessions_path` /
`load_session_id`), which is what makes `run_explorer.py --resume` possible. The map is written to disk,
because ids held only in the process are lost when a run stops.

Tree membership is tested with `run_id == root OR starts_with(run_id, root + '~')`, not a bare prefix or
LIKE: base ids contain `_` (a SQL LIKE wildcard). The `~` boundary makes membership exact.
"""
from __future__ import annotations

SEP = "~"


def root(run_id: str) -> str:
    """The investigation id — everything before the first separator (the whole id for a root run)."""
    return run_id.split(SEP, 1)[0]


def depth(run_id: str) -> int:
    """How far down the fork tree this branch is; 0 = the root run."""
    return run_id.count(SEP)


def parent(run_id: str) -> str | None:
    """The parent branch's run_id (lop the last segment), or None if this is the root."""
    return run_id.rsplit(SEP, 1)[0] if SEP in run_id else None


def child(run_id: str, idx: int) -> str:
    """The run_id of the idx-th fork off this branch."""
    return f"{run_id}{SEP}{int(idx)}"


def ancestors(run_id: str) -> list[str]:
    """Self + every ancestor prefix, root first: 'a~1~0' -> ['a', 'a~1', 'a~1~0']. This is the lineage a
    branch is allowed to read (its own tree plus the tested layer)."""
    segs = run_id.split(SEP)
    return [SEP.join(segs[: i + 1]) for i in range(len(segs))]


def tree_sql(run_id: str, col: str = "run_id") -> tuple[str, list]:
    """Every run in the investigation tree `run_id` belongs to (the root and all its `~`-descendants) as a
    (sql_fragment, params) pair with no leading AND/WHERE.

    This is the whole-tree predicate, the counterpart to `scope_sql`'s per-branch one. Use it wherever the
    harness acts on an investigation rather than on a branch: draining the verify queue (a worker is
    started with the root id but submissions carry branch ids), or showing a tree's verdicts in the
    dashboard. Membership is `= root OR starts_with(root + '~')`, never a bare LIKE prefix (see the module
    docstring).
    """
    rt = root(run_id)
    return (f"({col} = ? OR starts_with({col}, ?))", [rt, rt + SEP])


def scope_sql(run_id: str, col: str = "run_id") -> tuple[str, list]:
    """The read predicate as a (sql_fragment, params) pair, for scoping a durable read to a branch's
    lineage. A row's run_id is included iff:

      - it is one of this branch's ancestors (self up to the root)  -> its own tree plus the tested layer, or
      - it is not in this fork tree at all                          -> prior or separate runs

    and excluded iff it is in this tree but not an ancestor         -> a concurrent sibling or cousin.

    For a root run with no forks yet this reduces to "everything" (no sibling exists). The fragment has
    no leading AND/WHERE; the caller composes it.
    """
    anc = ancestors(run_id)
    rt = root(run_id)
    placeholders = ",".join("?" * len(anc))
    frag = f"({col} IN ({placeholders}) OR NOT ({col} = ? OR starts_with({col}, ?)))"
    params = [*anc, rt, rt + SEP]
    return frag, params
