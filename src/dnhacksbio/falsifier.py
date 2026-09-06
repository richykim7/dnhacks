"""The falsifier: the engine's soundness gate.

It judges statistical and design soundness only, from the numbers the experiment itself reported: is there
an estimable effect, are there enough independent units, does the direction match what the hypothesis
predicted, does it clear a permutation null, and does it survive the tool's robustness check. It does not
judge whether a result matters; that is the human's call at the promotion gate. Output is a kill with a
typed reason, or survived; survived is not true.
"""
from __future__ import annotations

import numpy as np

from dnhacksbio.methods import ToolResult

# Thresholds are calibrated on statistics and design, never on gene identity.
P_PERM_CLEAR_NULL = 0.05    # permutation p above this = not significant
MIN_GROUP = 8               # fewer exchangeable units than this = underpowered
# There is no minimum-effect or triviality gate: `effect_size` is filled by the agent and validated by
# nothing, so one constant compared against incommensurable quantities is not a comparison. Whether a
# result matters is decided at the promotion gate; the falsifier judges whether the number can be trusted.

# Every rejection path returns a stable slug, and each slug maps to exactly one kind. The kind says what
# to do next:
INVALID = "invalid"                # the numbers cannot be trusted; nothing was measured. Fix and re-run.
UNDERPOWERED = "underpowered"      # the test could not decide either way; get more units.
INCONCLUSIVE = "inconclusive"      # the test ran and found nothing; neither supported nor refuted.
REFUTED = "refuted"                # the data actively contradicted the claim; a result in itself.

KILL_KIND: dict[str, str] = {
    "no-effect":             INVALID,
    "malformed-p":           INVALID,
    "malformed-result":      INVALID,
    "too-few-units":         UNDERPOWERED,
    "not-significant":       INCONCLUSIVE,
    "direction-wrong":       REFUTED,         # the data went the other way; the inverse is a lead
    "not-robust":            REFUTED,         # the effect was an artifact of one group, not the claim
}
KILL_KINDS = frozenset(KILL_KIND.values())

# A kill whose kind cannot be named (an unknown slug). Stored instead of guessed: calling it "refuted"
# would assert the data contradicted the claim.
UNKNOWN_KILL = "killed"


def kill_kind(reason: str) -> str | None:
    """The kind of a KILL from its reason slug, or None if the slug is unknown."""
    return KILL_KIND.get((reason or "").strip().lower())


def kind_of_kill(reason: str) -> str:
    """The kind of a kill, always: one of KILL_KINDS, or UNKNOWN_KILL when the slug is not known. This is
    the single router from slug to kind; the storage path and the verify queue both use it."""
    return kill_kind(reason) or UNKNOWN_KILL


def _finite(x) -> bool:
    """True iff x is a real, comparable number (None, bool, NaN and inf are not)."""
    if x is None or isinstance(x, bool):
        return False
    try:
        return bool(np.isfinite(float(x)))
    except (TypeError, ValueError):
        return False


class Falsifier:
    # --- soundness core -------------------------------------------------------------------------
    def _soundness_core(self, *, effect, p_null, expected_sign, robust,
                        underpowered_reason, n_units_note=None) -> tuple[bool, str | None, str]:
        """The tool-agnostic soundness floor. `expected_sign` (+1/-1/0) is what the hypothesis predicts;
        0 is two-sided (direction not gated). Order: no-effect -> power -> direction -> null ->
        robustness."""
        if not _finite(effect):
            return False, "no-effect", "no estimable effect"
        if underpowered_reason:
            return False, "too-few-units", underpowered_reason
        # Every comparison against NaN is False, so a NaN p would pass `p_null > threshold`. Guard by
        # validity, never by comparison.
        if not _finite(p_null) or not (0.0 < p_null <= 1.0):
            return False, "malformed-p", f"p_null is not a probability (p_null={p_null!r})"
        if expected_sign != 0 and int(np.sign(effect)) != expected_sign:
            return False, "direction-wrong", f"effect direction wrong (effect={effect:+.3f}, want sign {expected_sign:+d})"
        if p_null > P_PERM_CLEAR_NULL:
            return False, "not-significant", f"clearly non-significant (p_null={p_null:.3f})"
        if robust is not True:
            return False, "not-robust", "effect failed the tool's robustness check"
        return True, None, f"sound: effect={effect:+.3f}, p_null={p_null:.3g}, n={n_units_note}"

    # --- entry point: any tool's ToolResult ------------------------------------------------------
    def soundness_floor_tool(self, tr: ToolResult) -> tuple[bool, str | None, str]:
        """Judge any tool's ToolResult against the shared floor. Only tools with
        trust_class='audited-statistic' are gated on the number; an 'exploratory' tool passes through
        (its statistic is never the basis of a kill; that is the trust boundary)."""
        if tr.trust_class != "audited-statistic":
            return True, None, f"exploratory tool ({tr.tool}): survives; statistic not gated (trust boundary)"
        up = None
        if tr.n_units is not None and tr.n_units < MIN_GROUP:
            up = f"too few units (n={tr.n_units})"
        return self._soundness_core(effect=tr.effect, p_null=tr.p_null,
                                    expected_sign=tr.expected_sign, robust=tr.robust,
                                    underpowered_reason=up, n_units_note=tr.n_units)
