"""The audited-statistic contract: the one shape every rigorous result carries through the loop.

`ToolResult` is the common shape the falsifier judges (`falsifier.soundness_floor_tool`). It is emitted by
the explorer's verify queue (`explorer/verifyqueue.py`) when it standardizes a self-run experiment for
verification. The trust boundary lives in the `trust_class` field: only a result tagged
`"audited-statistic"` carries a number the falsifier may gate a kill on.

This module holds only the contract; the explorer writes its own analysis code.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

TRUST_CLASSES = {"audited-statistic"}


def _sign(x: float | None) -> int:
    """Sign as -1/0/+1; None or NaN -> 0 (no estimable direction)."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return 0
    return (x > 0) - (x < 0)


def result_problem(result: dict) -> str | None:
    """Strict shared RESULT schema; never infer a successful scientific check."""
    if not isinstance(result, dict):
        return "RESULT must be an object"
    for field in ("effect", "p_null"):
        value = result.get(field)
        try:
            finite = type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            return f"{field} must be a finite number"
    if not 0 < result["p_null"] <= 1:
        return "p_null must be in (0,1]; permutation probabilities cannot be zero"
    if type(result.get("n_units")) is not int or result["n_units"] < 1:
        return "n_units must be a positive integer at the independent unit"
    if not isinstance(result.get("null_model"), str) or not result["null_model"].strip():
        return "null_model must describe the null test"
    if type(result.get("robust")) is not bool:
        return "robust must explicitly be true or false"
    return None


@dataclass
class ToolResult:
    """The common audited-statistic contract every rigorous result emits. `expected_sign` is set by the
    hypothesis (what the claim predicts: +1/-1, or 0 for two-sided), not the tool; the measured fields
    (`effect`, `p_null`, `robust`) are filled by whatever computed the number."""
    tool: str
    effect: float | None                 # point estimate, native units
    p_null: float                        # p vs the null model (Phipson-Smyth; never floors at 0)
    null_model: str                      # one line: what was permuted/shuffled to build the null
    n_units: int                         # sample size at the exchangeable unit (lines/donors/shuffles)
    expected_sign: int = 0               # what the hypothesis predicts: +1 / -1 / 0 (two-sided)
    robust: bool = True                  # robustness check held (e.g. leave-one-group-out sign stability)
    trust_class: str = "audited-statistic"
    observed_sign: int = 0               # sign(effect), filled in __post_init__
    dataset: str = ""
    method: str = ""

    def __post_init__(self):
        self.observed_sign = _sign(self.effect)
        if self.trust_class not in TRUST_CLASSES:
            raise ValueError(f"trust_class must be one of {TRUST_CLASSES}, got {self.trust_class!r}")
        if self.expected_sign not in (-1, 0, 1):
            raise ValueError(f"expected_sign must be -1/0/1, got {self.expected_sign!r}")

    def as_dict(self) -> dict:
        return asdict(self)
