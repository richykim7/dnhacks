"""Evidence utilities. Inputs must already be valid for the declared null/family.

These functions do not repair selection, repeated testing, or dependent products.
They are not connected to the repository falsifier.
"""
from __future__ import annotations

import math
import sys
from collections.abc import Iterable


def _e(value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("e-values must be finite and nonnegative")
    return value


def from_log(log_e: float) -> float:
    """Finite conservative serialization; underflow becomes zero, overflow is capped."""
    if not math.isfinite(log_e):
        raise ValueError("log wealth must be finite")
    return math.exp(min(log_e, math.log(sys.float_info.max)))


def p_to_e(p: float) -> float:
    """Integral-one calibrator for a valid superuniform p. Zero is unsupported."""
    p = float(p)
    if not math.isfinite(p) or not 0 < p <= 1:
        raise ValueError("p must be in (0, 1]; Monte Carlo p needs the plus-one correction")
    return 1 / math.sqrt(p) - 1


def e_to_p(e: float) -> float:
    e = _e(e)
    return 1.0 if e <= 1 else 1 / e


def mean_merge(values: Iterable[float]) -> float:
    values = [_e(v) for v in values]
    if not values:
        raise ValueError("at least one e-value is required")
    maximum = max(values)
    if maximum == 0:
        return 0.0
    return maximum * min(1.0, math.fsum(v / maximum for v in values) / len(values))


def product_merge(values: Iterable[float], *, validity: str) -> float:
    """Caller must establish independence or sequential conditional validity."""
    if validity not in {"independent", "conditional"}:
        raise ValueError("declare independent or conditional validity")
    values = [_e(v) for v in values]
    if not values:
        raise ValueError("at least one e-value is required")
    if 0 in values:
        return 0.0
    return from_log(math.fsum(math.log(v) for v in values))


def e_bh(values: Iterable[float], *, alpha: float = 0.05) -> list[int]:
    """Indices rejected by e-BH for a fixed, complete family of valid e-values."""
    if not math.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    values = [_e(v) for v in values]
    order = sorted(range(len(values)), key=lambda i: values[i], reverse=True)
    k = 0
    for rank, i in enumerate(order, 1):
        if values[i] >= len(values) / (alpha * rank):
            k = rank
    return sorted(order[:k])
