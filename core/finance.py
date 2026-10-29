"""Pure engineering-economics functions, named as in CE 725 (Ch 2, 3, 5-8).

Factor notation (X/Y, i, n) = "find X given Y": pf = (P/F, i, n), ap = (A/P, i, n), and so on.
"""
from __future__ import annotations

import numpy as np

# ---------- discrete interest factors (Ch 3, Table 3.1) ----------


def fp(i: float, n: float) -> float:
    """(F/P, i, n) single-payment compound amount."""
    return (1 + i) ** n


def pf(i: float, n: float) -> float:
    """(P/F, i, n) single-payment present worth."""
    return (1 + i) ** -n


def fa(i: float, n: int) -> float:
    """(F/A, i, n) uniform-series compound amount."""
    return n if i == 0 else ((1 + i) ** n - 1) / i


def af(i: float, n: int) -> float:
    """(A/F, i, n) sinking fund."""
    return 1 / fa(i, n)


def pa(i: float, n: int) -> float:
    """(P/A, i, n) uniform-series present worth."""
    return n if i == 0 else ((1 + i) ** n - 1) / (i * (1 + i) ** n)


def ap(i: float, n: int) -> float:
    """(A/P, i, n) capital recovery factor."""
    return 1 / pa(i, n)


def pg(i: float, n: int) -> float:
    """(P/G, i, n) arithmetic-gradient present worth."""
    return ((1 + i) ** n - i * n - 1) / (i**2 * (1 + i) ** n)


def ag(i: float, n: int) -> float:
    """(A/G, i, n) arithmetic-gradient uniform series."""
    return 1 / i - n / ((1 + i) ** n - 1)


def pa_geo(g: float, i: float, n: int) -> float:
    """(P/A1, g, i, n) geometric-gradient present worth: A1 in year 1, growing g a year (escalating tariffs, O&M)."""
    return n / (1 + i) if abs(i - g) < 1e-12 else (1 - ((1 + g) / (1 + i)) ** n) / (i - g)


def real_rate(nominal: float, inflation: float) -> float:
    """Fisher equation (Ch 2): (1 + i_f) = (1 + i)(1 + f)  ->  real i."""
    return (1 + nominal) / (1 + inflation) - 1


# ---------- annual worth (Ch 6) ----------


def crf(d: float, n: int) -> float:
    """Capital recovery factor (A/P, d, n): converts a present worth into an equivalent uniform annual amount."""
    return 1.0 / n if d == 0 else ap(d, n)


def pv_factor(d, t):
    return (1.0 + d) ** -t


def eac(lcc: float, d: float, n: int) -> float:
    """Equivalent uniform annual cost (EUAC) = PW of cost × (A/P, d, n)."""
    return lcc * crf(d, n)


def capital_recovery(p: float, s: float, i: float, n: int) -> float:
    """CR = (P − S)(A/P, i, n) + S·i  (Ch 6): annual cost of owning an asset bought for P and sold for S after n years."""
    return (p - s) * ap(i, n) + s * i


# ---------- payback ----------


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
    """Payback on present-worth flows; unlike simple payback it respects the time value of money (Ch 1 pitfall)."""
    t = np.arange(net.size)
    return payback_year(net * pv_factor(d, t))


# ---------- rate of return (Ch 7, 8) ----------


def sign_changes(cash: np.ndarray) -> int:
    """Number of sign changes in a cash-flow series (zeros skipped). Descartes: at most this many IRRs."""
    s = np.sign(np.asarray(cash, float))
    s = s[s != 0]
    return int((s[1:] != s[:-1]).sum())


def irr_roots(cash: np.ndarray) -> list[float]:
    """Every real IRR > -100% of a series (benefits positive): roots of Σ F_t x^t with x = 1/(1+i)."""
    c = np.asarray(cash, float)
    roots = np.roots(c[::-1])  # highest power first: F_n x^n + ... + F_0
    out = sorted({round(1 / r.real - 1, 10) for r in roots if abs(r.imag) < 1e-9 and r.real > 0})
    return [float(x) for x in out]


def irr(cash: np.ndarray) -> float | None:
    """IRR of a series with benefits positive and investment negative. None if undefined."""
    import numpy_financial as npf

    try:
        r = npf.irr(np.asarray(cash, float))
    except Exception:
        return None
    return None if r is None or not np.isfinite(r) else float(r)


def mirr(cash: np.ndarray, finance_rate: float, reinvest_rate: float) -> float | None:
    """Modified IRR (Ch 8): outflows discounted at the finance rate, inflows compounded at the reinvestment rate."""
    import numpy_financial as npf

    c = np.asarray(cash, float)
    if not (c > 0).any() or not (c < 0).any():
        return None
    r = npf.mirr(c, finance_rate, reinvest_rate)
    return None if not np.isfinite(r) else float(r)


def rate_of_return(cash: np.ndarray, marr: float) -> dict:
    """IRR when the series is simple (one sign change), MIRR at MARR otherwise, with the flag the UI shows."""
    n = sign_changes(cash)
    out = {"sign_changes": n, "irr": irr(cash) if n == 1 else None, "mirr": mirr(cash, marr, marr)}
    out["rate"] = out["irr"] if n == 1 else out["mirr"]
    out["method"] = "IRR" if n == 1 else "MIRR"
    return out
