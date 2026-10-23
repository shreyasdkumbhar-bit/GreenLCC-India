"""Pure engineering-economics functions."""
from __future__ import annotations

import numpy as np


def crf(d: float, n: int) -> float:
    """Capital recovery factor: converts a present worth into an equivalent annual cost."""
    return 1.0 / n if d == 0 else d / (1.0 - (1.0 + d) ** -n)


def pv_factor(d, t):
    return (1.0 + d) ** -t


def eac(lcc: float, d: float, n: int) -> float:
    return lcc * crf(d, n)


def payback_year(net: np.ndarray) -> float | None:
    """Year at which cumulative net cost (cost positive) first reaches <= 0, interpolated."""
    cum = np.cumsum(net)
    if cum[0] <= 0:
        return 0.0
    hit = np.nonzero(cum <= 0)[0]
    if hit.size == 0:
        return None
    t = int(hit[0])
    return (t - 1) + cum[t - 1] / (cum[t - 1] - cum[t])


def discounted_payback_year(net: np.ndarray, d: float) -> float | None:
    t = np.arange(net.size)
    return payback_year(net * pv_factor(d, t))


def irr(net: np.ndarray) -> float | None:
    """IRR of the net saving stream (savings positive). None if undefined."""
    import numpy_financial as npf

    try:
        r = npf.irr(-np.asarray(net, float))
    except Exception:
        return None
    return None if r is None or not np.isfinite(r) else float(r)
