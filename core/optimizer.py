"""IGBC target optimizer: exhaustive search over portfolios of green measures.

One option per exclusive group (or none); independent measures are on/off. With a library of
~12-20 measures this is a few thousand combinations, so exact enumeration is fast and the
result is provably optimal. Portfolio LCC is additive over measures (savings do not interact).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

import pandas as pd

from . import carbon, finance
from .cashflow import Streams, evaluate, measure_streams
from .igbc import score
from .schemas import Dataset, Measure

MAX_COMBOS = 300_000


@dataclass
class MeasureEval:
    measure: Measure
    streams: Streams
    capex_pv: float
    om_pv: float
    repl_pv: float
    resid_pv: float
    energy_pv: float
    water_pv: float
    lcc: float
    co2_t: float


def evaluate_measures(ds: Dataset) -> dict[str, MeasureEval]:
    p, out = ds.project, {}
    for m in ds.measures:
        S = measure_streams(p, m)
        ev = evaluate(S, p)
        out[m.measure_id] = MeasureEval(
            m, S, ev.scalar("capex"), ev.scalar("om"), ev.scalar("repl"), ev.scalar("resid"),
            ev.scalar("energy"), ev.scalar("water"), ev.scalar("lcc"), carbon.lifetime_co2_t(p, S),
        )
    return out


def groups(ds: Dataset) -> dict[str, list[str]]:
    g: dict[str, list[str]] = {}
    for m in ds.measures:
        g.setdefault(m.group, []).append(m.measure_id)
    return g


def combo_count(ds: Dataset) -> int:
    n = 1
    for ids in groups(ds).values():
        n *= len(ids) + 1
    return n


def enumerate_portfolios(ds: Dataset, mev: dict[str, MeasureEval] | None = None) -> pd.DataFrame:
    """Every feasible-by-roof portfolio with points, level, cost and carbon."""
    p = ds.project
    if combo_count(ds) > MAX_COMBOS:
        raise ValueError(f"{combo_count(ds):,} combinations is too many for exact search; "
                         "trim the library or merge exclusive groups.")
    mev = mev or evaluate_measures(ds)
    options = [[None, *ids] for ids in groups(ds).values()]
    roof_kwp_cap = p.roof_kwp_cap
    rows = []
    for combo in itertools.product(*options):
        ids = tuple(i for i in combo if i)
        sel = [mev[i] for i in ids]
        if sum(e.measure.kwp for e in sel) > roof_kwp_cap + 1e-9:
            continue  # does not fit on the roof
        sc = score(ds, [e.measure for e in sel])
        capex = sum(e.streams.capex for e in sel)
        lcc = sum(e.lcc for e in sel)
        rows.append({
            "selection": ids,
            "n_measures": len(ids),
            "capex": capex,
            "capex_pv": sum(e.capex_pv for e in sel),
            "om_pv": sum(e.om_pv for e in sel),
            "repl_pv": sum(e.repl_pv for e in sel),
            "resid_pv": sum(e.resid_pv for e in sel),
            "savings_pv": sum(e.energy_pv + e.water_pv for e in sel),
            "lcc": lcc,
            "eac": finance.eac(lcc, p.discount_rate, p.study_period),
            "points": sc.total,
            "level": sc.level,
            "rank": sc.rank,
            "mandatory_ok": sc.mandatory_ok,
            "co2_t": sum(e.co2_t for e in sel),
        })
    return pd.DataFrame(rows)


def feasible(df: pd.DataFrame, ds: Dataset, target: str) -> pd.DataFrame:
    return df[(df["rank"] >= ds.level_rank(target)) & df["mandatory_ok"]]


def best(df: pd.DataFrame, ds: Dataset, target: str, objective: str) -> pd.Series | None:
    """objective in {'capex','lcc'}; ties broken by lower capex."""
    f = feasible(df, ds, target)
    if f.empty:
        return None
    return f.sort_values([objective, "capex"]).iloc[0]


def infeasible_message(df: pd.DataFrame, ds: Dataset, target: str) -> str:
    ok = df[df["mandatory_ok"]]
    if ok.empty:
        return "No portfolio satisfies the mandatory credits; add a measure that earns them."
    top = ok.sort_values("points", ascending=False).iloc[0]
    need = next(lv.min_points for lv in ds.levels if lv.level == target)
    return (f"{target} needs {need:g} points but the best portfolio in the library reaches "
            f"{top['points']:g} ({top['level']}). Add measures worth at least {need - top['points']:g} more points.")


def upgrade_path(df: pd.DataFrame, ds: Dataset, objective: str = "lcc") -> pd.DataFrame:
    """Best portfolio per IGBC level, with the incremental cost of stepping up."""
    rows, prev = [], None
    for lv in sorted(ds.levels, key=lambda x: x.rank):
        b = best(df, ds, lv.level, objective)
        if b is None:
            continue
        extra = b["points"] - ds.project.base_points
        rows.append({
            "Level": lv.level, "Points": b["points"], "Capex": b["capex"], "LCC": b["lcc"],
            "Incremental LCC vs previous level": None if prev is None else b["lcc"] - prev,
            "Rs per extra point (LCC)": None if extra <= 0 else b["lcc"] / extra,
            "selection": b["selection"],
        })
        prev = b["lcc"]
    return pd.DataFrame(rows)


def breakdown(row: pd.Series) -> dict[str, float]:
    """Components that sum to LCC: costs positive, savings/residual negative."""
    return {
        "Capex": row["capex_pv"], "O&M": row["om_pv"], "Replacements": row["repl_pv"],
        "Residual value": -row["resid_pv"], "Energy & water savings": -row["savings_pv"],
    }
