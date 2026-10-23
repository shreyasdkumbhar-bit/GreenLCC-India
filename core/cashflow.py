"""Year-by-year cash-flow engine (nominal rupees, cost positive, savings negative).

Conventions
- Base prices (tariff, O&M, water) are year-1 prices and escalate from year 2.
- Component replacement costs are today's prices inflated to the replacement year.
- Residual value at the end of the study period = last purchase cost x remaining-life fraction.
- LCC of a measure = net incremental life-cycle cost vs the code-minimum baseline;
  negative means the measure pays for itself over the study period.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import finance
from .schemas import Component, Measure, Project


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


def measure_streams(p: Project, m: Measure, comps: list[Component]) -> Streams:
    n = p.study_period
    t = np.arange(n + 1)
    yr = t >= 1
    k = np.where(yr, t - 1, 0)

    om = np.where(yr, m.om_annual * (1 + m.om_escalation) ** k, 0.0)
    degr = np.where(yr, (1 - m.degradation) ** k, 0.0)

    repl = np.zeros(n + 1)
    resid = np.zeros(n + 1)
    for c in comps:
        step = c.life_years
        # replacements at L, 2L, ... strictly inside the study period
        j = 1
        while j * step < n - 1e-9:
            ty = int(round(j * step))
            if 0 < ty < n:
                repl[ty] += c.cost * (1 + p.inflation) ** ty
            j += 1
        t_last = np.floor((n - 1e-9) / step) * step
        frac = max(0.0, (t_last + step - n) / step)
        resid[n] += c.cost * (1 + p.inflation) ** t_last * frac

    kwh_eff = m.energy_saving_kwh * degr if m.kind == "efficiency" else np.zeros(n + 1)
    if m.kind == "renewable":
        gen = m.kwp * p.pv_yield_kwh_per_kwp * degr
        kwh_self = gen * p.pv_self_consumption
        kwh_exp = gen * (1 - p.pv_self_consumption)
    else:
        kwh_self = kwh_exp = np.zeros(n + 1)
    water = np.where(yr, m.water_saving_kl, 0.0) if m.kind == "water" else np.zeros(n + 1)

    return Streams(n, m.capex - m.subsidy, om, repl, resid, kwh_eff, kwh_self, kwh_exp, water, m.kwp)


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
    export = p.export_tariff * (1 + p.export_escalation) ** k * yr
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
    """Headline metrics for one alternative."""
    ev = evaluate(S, p, **kw)
    d = p.discount_rate if kw.get("d") is None else kw["d"]
    lcc = ev.scalar("lcc")
    costs = ev.scalar("capex") + ev.scalar("om") + ev.scalar("repl") - ev.scalar("resid")
    savings = ev.scalar("energy") + ev.scalar("water")
    net = ev.net_t[0]
    return {
        "lcc": lcc,
        "eac": finance.eac(lcc, d, S.n),
        "capex": S.capex,
        "pv_costs": costs,
        "pv_savings": savings,
        "sir": savings / costs if costs > 0 else None,
        "payback": finance.payback_year(net),
        "disc_payback": finance.discounted_payback_year(net, d),
        "irr": finance.irr(net),
    }
