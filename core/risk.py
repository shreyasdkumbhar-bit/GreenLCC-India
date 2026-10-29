"""Sensitivity, break-even and Monte Carlo on a portfolio of measures."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from . import cashflow
from .cashflow import Streams, evaluate, measure_streams
from .schemas import Dataset


def portfolio_streams(ds: Dataset, ids) -> Streams:
    S = Streams.zero(ds.project.study_period)
    for i in ids:
        S = S + measure_streams(ds.project, ds.measure(i))
    return S


def lcc(ds: Dataset, ids, **kw) -> float:
    return evaluate(portfolio_streams(ds, ids), ds.project, **kw).scalar("lcc")


def incremental(ds: Dataset, ids_a, ids_b) -> dict:
    """Incremental rate of return of portfolio B over portfolio A (Ch 7), checked against the MARR."""
    return cashflow.incremental(portfolio_streams(ds, ids_a), portfolio_streams(ds, ids_b), ds.project)


def discount_sweep(ds: Dataset, ids_a, ids_b, rates=None) -> pd.DataFrame:
    rates = np.linspace(0.04, 0.20, 33) if rates is None else rates
    Sa, Sb = portfolio_streams(ds, ids_a), portfolio_streams(ds, ids_b)
    a = evaluate(Sa, ds.project, d=rates).lcc
    b = evaluate(Sb, ds.project, d=rates).lcc
    return pd.DataFrame({"discount_rate": rates, "lcc_a": a, "lcc_b": b, "gap": a - b})


BREAK_EVEN_RANGES = {
    "discount": (0.01, 0.30, "MARR (discount rate)"),
    "tariff_escalation": (-0.03, 0.15, "Tariff escalation"),
    "capex_mult": (0.3, 2.5, "Capex multiplier"),
}


def break_even(ds: Dataset, ids_a, ids_b, param: str) -> float | None:
    """Value of `param` at which portfolios A and B have equal LCC (None if they never cross)."""
    lo, hi, _ = BREAK_EVEN_RANGES[param]
    key = {"discount": "d", "tariff_escalation": "g"}.get(param, param)
    Sa, Sb = portfolio_streams(ds, ids_a), portfolio_streams(ds, ids_b)

    def gap(x: float) -> float:
        return evaluate(Sa, ds.project, **{key: x}).scalar("lcc") - evaluate(Sb, ds.project, **{key: x}).scalar("lcc")

    xs = np.linspace(lo, hi, 60)
    gs = [gap(x) for x in xs]
    for x0, x1, g0, g1 in zip(xs, xs[1:], gs, gs[1:]):
        if g0 == 0:
            return float(x0)
        if g0 * g1 < 0:
            return float(brentq(gap, x0, x1))
    return None


def tornado(ds: Dataset, ids, swing: float = 0.20) -> pd.DataFrame:
    p = ds.project
    S = portfolio_streams(ds, ids)
    base = evaluate(S, p).scalar("lcc")
    tests = {
        "Grid tariff (±20%)": ({"tariff_mult": 1 - swing}, {"tariff_mult": 1 + swing}),
        "Tariff escalation (±2 pp)": ({"g": p.tariff_escalation - 0.02}, {"g": p.tariff_escalation + 0.02}),
        "MARR (±2 pp)": ({"d": p.discount_rate + 0.02}, {"d": max(p.discount_rate - 0.02, 0.005)}),
        "Capex (±20%)": ({"capex_mult": 1 + swing}, {"capex_mult": 1 - swing}),
        "O&M (±20%)": ({"om_mult": 1 + swing}, {"om_mult": 1 - swing}),
        "Solar yield (±20%)": ({"yield_mult": 1 - swing}, {"yield_mult": 1 + swing}),
    }
    rows = []
    for name, (bad, good) in tests.items():
        hi = evaluate(S, p, **bad).scalar("lcc")
        lo = evaluate(S, p, **good).scalar("lcc")
        rows.append({"parameter": name, "worse": hi - base, "better": lo - base, "swing": abs(hi - lo)})
    return pd.DataFrame(rows).sort_values("swing", ascending=True).assign(base=base)


@dataclass
class MCResult:
    lcc_a: np.ndarray
    lcc_b: np.ndarray
    p_b_better: float
    p_a_saves: float
    p_b_saves: float
    pct_a: dict
    pct_b: dict
    runs: int
    seed: int


def monte_carlo(ds: Dataset, ids_a, ids_b, runs: int = 5000, seed: int = 42) -> MCResult:
    """A = portfolio to beat (e.g. min-capex), B = challenger (e.g. min-LCC)."""
    p = ds.project
    rng = np.random.default_rng(seed)
    g = np.clip(rng.normal(p.tariff_escalation, max(p.tariff_escalation_sd, 1e-9), runs), -0.02, 0.15)
    d = rng.triangular(max(p.discount_rate - 0.02, 0.01), p.discount_rate, p.discount_rate + 0.03, runs)
    cm = rng.triangular(0.90, 1.0, 1.20, runs)
    ym = np.clip(rng.normal(1.0, 0.07, runs), 0.7, 1.3)
    kw = dict(d=d, g=g, capex_mult=cm, yield_mult=ym)
    a = evaluate(portfolio_streams(ds, ids_a), p, **kw).lcc
    b = evaluate(portfolio_streams(ds, ids_b), p, **kw).lcc

    def pct(x):
        return {"P10": float(np.percentile(x, 10)), "P50": float(np.percentile(x, 50)),
                "P90": float(np.percentile(x, 90)), "mean": float(x.mean())}

    return MCResult(a, b, float((b < a).mean()), float((a < 0).mean()), float((b < 0).mean()),
                    pct(a), pct(b), runs, seed)
