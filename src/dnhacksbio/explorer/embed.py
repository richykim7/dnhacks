"""Shared embedding helper for semantic search (full-text store, exploration log, KG, corpus find).

One all-MiniLM-L6-v2 model, lazy-loaded and cached. Every call is graceful: if sentence-transformers is
unavailable, embed() returns None and callers degrade to keyword search. Vectors are L2-normalized, so
cosine == dot."""
from __future__ import annotations

import numpy as np

_model = None
_MODEL_NAME = "all-MiniLM-L6-v2"
_MAX_THREADS = 8


def _cap_threads() -> None:
    """Cap torch's intra-op threads before the model loads.

    Torch defaults to one thread per core. `EMBED_THREADS` overrides (0/unset = the cap)."""
    try:
        import os

        import torch
        n = int(os.environ.get("EMBED_THREADS") or 0) or min(_MAX_THREADS, os.cpu_count() or _MAX_THREADS)
        torch.set_num_threads(max(1, n))
    except Exception:
        pass


def _get():
    global _model
    if _model is None:
        _cap_threads()
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed(texts: list[str]) -> list[list[float]] | None:
    """Embed a batch → list of normalized float vectors, or None on any failure (caller falls back)."""
    if not texts:
        return []
    try:
        arr = _get().encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        return arr.tolist()
    except Exception:
        return None


def embed_one(text: str) -> list[float] | None:
    out = embed([text or ""])
    return out[0] if out else None


def max_similarity(texts: list[str], anchors: list[str]) -> list[float] | None:
    """For each text, its highest cosine to any of the anchors. Returns None if embedding is unavailable,
    so each caller picks its own fallback.

    This is the relevance-triage primitive shared by corpus discovery and the corpus-build scripts: score
    candidate papers against one or more descriptions of what is wanted, then keep the top k."""
    if not texts or not anchors:
        return None
    tv, av = embed(list(texts)), embed(list(anchors))
    if not tv or not av:
        return None
    sims = np.asarray(tv, dtype=np.float32) @ np.asarray(av, dtype=np.float32).T
    return sims.max(axis=1).tolist()


def rank(query_vec: list[float], rows: list[tuple], vec_key, top_k: int) -> list[tuple]:
    """Rank rows by cosine to query_vec. `vec_key(row)` returns the row's stored vector (or None → skipped).
    Returns [(score, row), ...] best-first, length<=top_k."""
    if query_vec is None or len(query_vec) == 0 or not rows:
        return []
    q = np.asarray(query_vec, dtype=np.float32)
    keep, vecs = [], []
    for r in rows:
        v = vec_key(r)
        if v is None or len(v) != q.shape[0]:      # missing, or a vector of another dimension
            continue
        keep.append(r)
        vecs.append(v)
    if not keep:
        return []
    scores = np.asarray(vecs, dtype=np.float32) @ q          # cosine — vectors are L2-normalized
    idx = np.argsort(-scores, kind="stable")[:top_k]         # stable: ties keep row order
    return [(float(scores[i]), keep[i]) for i in idx]
