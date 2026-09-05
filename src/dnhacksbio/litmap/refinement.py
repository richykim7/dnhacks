"""Is one claim a special case of another?

Claim identity is an exact hash, so "has anyone claimed this?" answers only exact matches; `mutant EGFR
(L858R) binds GRB2` and `EGFR binds GRB2` are two edges. This module computes the general/specific
relation between them on demand, within one `abstract_key` group (same subject, object and property), so
nothing is stored.

The rule is INDRA's, field by field: a claim refines another when every field matches or is a wildcard on
the general side, and at least one is strictly narrower. A blank field is a wildcard only where blank means
general: `variant=""` on a `mutant` claim means "any mutant", but `functional="unknown"` means the actor
was not identified and blocks the link, as does `object_aspect=""`. Siblings never link (`mutant` is not a
kind of `wild-type`); only a declared parent predicate or an explicit `general` state may sit on the broad
side. Identifiers must be equal and no entity hierarchy is walked: `EGFR intron 1` does not refine
`EGFR`, and a protein construct (a piece) never narrows while an isoform (a kind) does.

Context coverage is not answered here; see `ClaimGraph.context_profile`. Support flows specific -> general
only.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dnhacksbio.litmap.vocab import PREDICATE_PARENTS

# Values of `functional` that name no particular form. Only `general` may act as a wildcard; the other two
# mean "not determined", which is the opposite epistemic situation (BioPAX draws the same line).
_UNIDENTIFIED = frozenset({"unknown", "unspecified"})
_WILDCARD_STATE = "general"

# The comparable shape, named for the `claims` table columns so a stored row IS one already.
_SIDES = ("subject", "object")
_STATE_PARTS = ("state", "variant", "isoform", "protein_construct")


def fields(claim: Any) -> dict[str, str]:
    """Normalise a `ClaimSpine`, a `Claim` or a stored `claims` row into one comparable shape, shared by
    the store (rows) and the novelty check (an unwritten candidate)."""
    if isinstance(claim, Mapping):
        return {k: str(claim.get(k) or "") for k in _KEYS}
    spine = getattr(claim, "spine", claim)
    out = {"object_aspect": spine.object_aspect, "relation_class": spine.relation_class,
           "predicate": spine.predicate}
    for side in _SIDES:
        ref = getattr(spine, side)
        out[f"{side}_curie"] = ref.curie
        out[f"{side}_feature_type"] = ref.feature_type
        out[f"{side}_state"] = ref.state.functional
        out[f"{side}_variant"] = ref.state.variant
        out[f"{side}_isoform"] = ref.state.isoform
        out[f"{side}_protein_construct"] = ref.state.protein_construct
    return {k: str(out.get(k) or "") for k in _KEYS}


_KEYS = ("subject_curie", "subject_feature_type", "subject_state", "subject_variant", "subject_isoform",
         "subject_protein_construct",
         "object_curie", "object_feature_type", "object_state", "object_variant", "object_isoform",
         "object_protein_construct",
         "object_aspect", "relation_class", "predicate")


def _predicate_refines(a: str, b: str) -> tuple[bool, bool]:
    """(compatible, strictly narrower). One level of parent, never sibling-to-sibling."""
    if a == b:
        return True, False
    is_child = PREDICATE_PARENTS.get(a) == b
    return is_child, is_child


def _state_refines(a: dict, b: dict, side: str) -> tuple[bool, bool]:
    """(compatible, strictly narrower) for one entity's state block, field by field."""
    fa, fb = a[f"{side}_state"], b[f"{side}_state"]
    narrower = False
    if fb in _UNIDENTIFIED:
        # An unidentified actor generalises nothing, sub-fields included: only an identical state passes.
        return all(a[f"{side}_{p}"] == b[f"{side}_{p}"]
                   for p in ("state", "variant", "isoform", "protein_construct")), False
    if fa != fb:
        if fb != _WILDCARD_STATE:
            return False, False                      # siblings: mutant is not a kind of wild-type
        if fa in _UNIDENTIFIED and not (a[f"{side}_variant"] or a[f"{side}_isoform"]):
            return False, False                      # nothing about `a` is actually more specific
        narrower = True

    # `variant` and `isoform` are narrowing axes; blank on the broad side means "any".
    for part in ("variant", "isoform"):
        va, vb = a[f"{side}_{part}"], b[f"{side}_{part}"]
        if va == vb:
            continue
        if vb:
            return False, False                      # two different forms are siblings, not nested
        narrower = True

    # `construct` matches but never narrows: a property of a part is not a property of the whole, and a
    # differing construct blocks so the two claims stay comparable as different.
    if a[f"{side}_protein_construct"] != b[f"{side}_protein_construct"]:
        return False, False
    return True, narrower


def refinement(specific: Any, general: Any) -> list[str] | None:
    """Why `specific` is a special case of `general`, or None if it is not."""
    a, b = fields(specific), fields(general)
    if a == b:
        return None                                  # the same claim is not a refinement of itself
    for k in ("subject_curie", "subject_feature_type", "object_curie", "object_feature_type",
              "relation_class"):
        if a[k] != b[k]:
            return None
    # A blank aspect means the paper did not say which property changed: unknown, not "any property".
    if a["object_aspect"] != b["object_aspect"]:
        return None

    why: list[str] = []
    ok, narrower = _predicate_refines(a["predicate"], b["predicate"])
    if not ok:
        return None
    if narrower:
        why.append(f"predicate: {a['predicate']} is a kind of {b['predicate']}")
    for side in _SIDES:
        ok, narrower = _state_refines(a, b, side)
        if not ok:
            return None
        if narrower:
            why.append(f"{side} state: {_state_str(a, side)} is a kind of {_state_str(b, side)}")
    return why or None                               # equal on every axis = same claim, not a refinement


def refines(specific: Any, general: Any) -> bool:
    return refinement(specific, general) is not None


def _state_str(f: dict, side: str) -> str:
    parts = [f[f"{side}_state"]] + [f[f"{side}_{p}"]
                                    for p in ("variant", "isoform", "protein_construct") if f[f"{side}_{p}"]]
    return "/".join(parts)


def pairs(claims: list[Any]) -> list[tuple[Any, Any, list[str]]]:
    """Every (specific, general, why) among a set of claims sharing one abstract_key. Quadratic, and only
    called per group, which stays small."""
    out = []
    for i, x in enumerate(claims):
        for j, y in enumerate(claims):
            if i == j:
                continue
            why = refinement(x, y)
            if why:
                out.append((x, y, why))
    return out


def specialises(specific, general) -> bool:
    """Is `specific`'s subject a narrower form of `general`'s subject, regardless of what each claims?
    Unlike `refines`, this is an entity question: `G719S increases stability` and `most exon-19 mutants
    decrease stability` point opposite ways as claims, but G719S is a kind of mutant EGFR, which makes the
    pair an exception rather than a contradiction.
    """
    a, b = fields(specific), fields(general)
    if a["subject_curie"] != b["subject_curie"] or a["subject_feature_type"] != b["subject_feature_type"]:
        return False
    ok, narrower = _state_refines(a, b, "subject")
    return ok and narrower

