"""Year-by-year cash-flow engine (nominal rupees, cost positive, savings negative).

Conventions (CE 725 Ch 5, planning-horizon method)
- Every measure is costed over one common study period N (co-termination), at the MARR.
- Base prices (tariff, O&M, water) are year-1 prices and escalate from year 2 (geometric gradient).
- O&M and re-purchase prices escalate at general inflation.
- A measure is re-bought (at today's incremental price, inflated) when its life ends inside N; its one
  replaceable part (inverter, compressor...) is re-bought every part_life years, except in a year the whole
  measure is re-bought anyway.
- Salvage (residual) value at year N = last purchase cost x remaining-life fraction.
- LCC of a measure = present worth of its net incremental cost vs the code-minimum baseline;
  negative means the measure pays for itself over the study period.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import finance
from .schemas import EXPORT_ESCALATION, Measure, Project


@dataclass
class Streams:
    """Price-independent physical and cost streams, arrays of length n+1 (t = 0..n)."""

    n: int
    capex: float
    om: np.ndarray
    repl: np.ndarray
    resid: np.ndarray
    kwh_eff: np.ndarray
    kwh_re_self: np.ndarray
    kwh_re_exp: np.ndarray
    water: np.ndarray
    kwp: float = 0.0

    def __add__(self, other: "Streams") -> "Streams":
        return Streams(
            n=self.n,
            capex=self.capex + other.capex,
            om=self.om + other.om,
            repl=self.repl + other.repl,
            resid=self.resid + other.resid,
            kwh_eff=self.kwh_eff + other.kwh_eff,
            kwh_re_self=self.kwh_re_self + other.kwh_re_self,
            kwh_re_exp=self.kwh_re_exp + other.kwh_re_exp,
            water=self.water + other.water,
            kwp=self.kwp + other.kwp,
        )

    @staticmethod
    def zero(n: int) -> "Streams":
        z = np.zeros(n + 1)
        return Streams(n, 0.0, z.copy(), z.copy(), z.copy(), z.copy(), z.copy(), z.copy(), z.copy())


def _purchases(n: int, cost: float, life: float, skip: set[int] | None = None) -> tuple[dict[int, float], float, float]:
    """Re-purchase years strictly inside (0, n) at multiples of `life`, plus (year bought last, remaining-life fraction)."""
    buys, j = {}, 1
    while j * life < n - 1e-9:
        ty = int(round(j * life))
        if 0 < ty < n and ty not in (skip or set()):
            buys[ty] = cost
        j += 1
    t_last = np.floor((n - 1e-9) / life) * life
    frac = max(0.0, (t_last + life - n) / life)
    return buys, float(t_last), frac


def measure_streams(p: Project, m: Measure) -> Streams:
    n = p.study_period
    t = np.arange(n + 1)
    yr = t >= 1
    k = np.where(yr, t - 1, 0)

    om = np.where(yr, m.om_annual * (1 + p.inflation) ** k, 0.0)
    degr = np.where(yr, (1 - m.degradation) ** k, 0.0)

    repl = np.zeros(n + 1)
    resid = np.zeros(n + 1)
    whole, t_last, frac = _purchases(n, m.capex, m.life_years)
    for ty, c in whole.items():
        repl[ty] += c * (1 + p.inflation) ** ty
    resid[n] += m.capex * (1 + p.inflation) ** t_last * frac
    if m.part_cost > 0 and m.part_life > 0:
        parts, pt_last, pfrac = _purchases(n, m.part_cost, m.part_life, skip=set(whole))
        for ty, c in parts.items():
            repl[ty] += c * (1 + p.inflation) ** ty
        if pt_last > 0 and int(round(pt_last)) not in whole:  # a part bought with the measure is in the measure's salvage
            resid[n] += m.part_cost * (1 + p.inflation) ** pt_last * pfrac

    kwh_eff = m.energy_saving_kwh * degr
    gen = m.kwp * p.pv_yield_kwh_per_kwp * degr
    kwh_self = gen * p.pv_self_consumption
    kwh_exp = gen * (1 - p.pv_self_consumption)
    water = np.where(yr, m.water_saving_kl, 0.0)

    return Streams(n, m.capex, om, repl, resid, kwh_eff, kwh_self, kwh_exp, water, m.kwp)


@dataclass
class Eval:
    """Present-worth components; every field is an array (length = number of scenarios)."""

    capex: np.ndarray
    om: np.ndarray
    repl: np.ndarray
    resid: np.ndarray
    energy: np.ndarray
    water: np.ndarray
    lcc: np.ndarray
    net_t: np.ndarray = field(repr=False, default=None)

    def scalar(self, name: str) -> float:
        return float(np.asarray(getattr(self, name)).ravel()[0])


def _col(x) -> np.ndarray:
    """Scenario parameter as a column (R, 1); scalars become R = 1."""
    return np.atleast_1d(np.asarray(x, dtype=float))[:, None]


def evaluate(
    S: Streams,
    p: Project,
    *,
    d=None,
    g=None,
    tariff_mult=1.0,
    capex_mult=1.0,
    om_mult=1.0,
    yield_mult=1.0,
) -> Eval:
    """Discount a stream bundle. Scenario parameters may be scalars or 1-D arrays (Monte Carlo)."""
    n = S.n
    t = np.arange(n + 1)
    yr = (t >= 1).astype(float)
    k = np.where(t >= 1, t - 1, 0)

    d = _col(p.discount_rate if d is None else d)
    g = _col(p.tariff_escalation if g is None else g)
    tm, cm, om_m, ym = _col(tariff_mult), _col(capex_mult), _col(om_mult), _col(yield_mult)

    retail = p.grid_tariff * tm * (1 + g) ** k * yr
    export = p.export_tariff * (1 + EXPORT_ESCALATION) ** k * yr
    water_p = p.water_tariff * (1 + p.water_escalation) ** k * yr

    capex_t = np.zeros_like(retail + 0 * cm)
    capex_t[:, 0] = S.capex * cm[:, 0]
    om_t = S.om * om_m
    repl_t = S.repl * cm
    resid_t = S.resid * cm
    energy_t = (S.kwh_eff + S.kwh_re_self * ym) * retail + S.kwh_re_exp * ym * export
    water_t = S.water * water_p

    net = capex_t + om_t + repl_t - resid_t - energy_t - water_t
    df = (1 + d) ** (-t)
    pv = lambda a: (a * df).sum(axis=-1)  # noqa: E731
    return Eval(
        capex=pv(capex_t), om=pv(om_t), repl=pv(repl_t), resid=pv(resid_t),
        energy=pv(energy_t), water=pv(water_t), lcc=pv(net), net_t=net,
    )


def yearly_table(S: Streams, p: Project, **kw) -> pd.DataFrame:
    """Readable year-by-year table for the UI (single scenario)."""
    ev = evaluate(S, p, **kw)
    n = S.n
    t = np.arange(n + 1)
    d = p.discount_rate if kw.get("d") is None else kw["d"]
    cm = kw.get("capex_mult", 1.0)
    om_m = kw.get("om_mult", 1.0)
    ev_parts = {
        "Capex": np.r_[S.capex * cm, np.zeros(n)],
        "O&M": S.om * om_m,
        "Replacement": S.repl * cm,
        "Residual value": -S.resid * cm,
    }
    # savings (costed with the same price paths used by evaluate)
    zero = Streams.zero(n)
    energy_only = Streams(n, 0, zero.om, zero.repl, zero.resid, S.kwh_eff, S.kwh_re_self, S.kwh_re_exp, zero.water)
    water_only = Streams(n, 0, zero.om, zero.repl, zero.resid, zero.kwh_eff, zero.kwh_re_self, zero.kwh_re_exp, S.water)
    ev_parts["Energy savings"] = _saving_series(energy_only, p, **kw)
    ev_parts["Water savings"] = _saving_series(water_only, p, **kw)
    df = pd.DataFrame(ev_parts, index=pd.Index(t, name="Year"))
    df["Net cash flow"] = ev.net_t[0]
    df["Discount factor"] = finance.pv_factor(d, t)
    df["Present worth"] = df["Net cash flow"] * df["Discount factor"]
    df["Cumulative PW"] = df["Present worth"].cumsum()
    df["Cumulative (undiscounted)"] = df["Net cash flow"].cumsum()
    return df


def _saving_series(S: Streams, p: Project, **kw) -> np.ndarray:
    """Negative-cost savings series for a streams bundle that contains only savings."""
    return evaluate(S, p, **kw).net_t[0]


def summarize(S: Streams, p: Project, **kw) -> dict:
    """Headline metrics for one alternative vs doing nothing: PW, EUAC, BCR, rate of return, discounted payback."""
    ev = evaluate(S, p, **kw)
    d = p.discount_rate if kw.get("d") is None else kw["d"]
    lcc = ev.scalar("lcc")
    costs = ev.scalar("capex") + ev.scalar("om") + ev.scalar("repl") - ev.scalar("resid")
    savings = ev.scalar("energy") + ev.scalar("water")
    net = ev.net_t[0]
    rr = finance.rate_of_return(-net, d)  # benefits positive
    return {
        "lcc": lcc,
        "eac": finance.eac(lcc, d, S.n),
        "capex": S.capex,
        "pv_costs": costs,
        "pv_savings": savings,
        "bcr": savings / costs if costs > 0 else None,
        "disc_payback": finance.discounted_payback_year(net, d),
        "ror": rr["rate"],
        "ror_method": rr["method"],
        "sign_changes": rr["sign_changes"],
    }


def incremental(Sa: Streams, Sb: Streams, p: Project, **kw) -> dict:
    """Ch 7 incremental analysis: is the extra money spent on B (over A) earning at least the MARR?"""
    d = p.discount_rate if kw.get("d") is None else kw["d"]
    a, b = evaluate(Sa, p, **kw), evaluate(Sb, p, **kw)
    cash = a.net_t[0] - b.net_t[0]  # what choosing B instead of A gains each year (year 0 = extra capex, negative)
    rr = finance.rate_of_return(cash, d)
    return {
        "extra_capex": Sb.capex - Sa.capex,
        "pw_gain": a.scalar("lcc") - b.scalar("lcc"),
        "rate": rr["rate"], "method": rr["method"], "sign_changes": rr["sign_changes"],
        "disc_payback": finance.discounted_payback_year(-cash, d),
        "marr": d,
    }
