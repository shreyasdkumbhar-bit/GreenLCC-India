"""IGBC points engine: scores a set of selected measures against the credit and level tables.

The point tables shipped in data/ are ILLUSTRATIVE (see PROJECT_LOG.md Q-002); the engine itself
is table-driven, so real IGBC values can be dropped in without code changes.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .schemas import Dataset, Measure, Project


@dataclass
class Score:
    total: float
    level: str
    rank: int
    mandatory_ok: bool
    missing_mandatory: list[str]
    breakdown: pd.DataFrame
    metrics: dict


def metrics(p: Project, selected: list[Measure]) -> dict:
    eff_kwh = sum(m.energy_saving_kwh for m in selected)
    re_kwh = sum(m.kwp for m in selected) * p.pv_yield_kwh_per_kwp
    water = sum(m.water_saving_kl for m in selected)
    proposed = max(p.baseline_energy_kwh - eff_kwh, 1.0)
    return {
        "energy_eff_pct": 100 * eff_kwh / p.baseline_energy_kwh,
        "energy_re_pct": 100 * re_kwh / proposed,
        "water_pct": 100 * water / p.baseline_water_kl if p.baseline_water_kl > 0 else 0.0,
        "eff_kwh": eff_kwh,
        "re_kwh": re_kwh,
        "water_kl": water,
        "kwp": sum(m.kwp for m in selected),
    }


def _threshold_points(pct: float, thresholds: list[tuple[float, float]]) -> float:
    pts = 0.0
    for t_pct, t_pts in sorted(thresholds):
        if pct >= t_pct:
            pts = t_pts
    return pts


def score(ds: Dataset, selected: list[Measure]) -> Score:
    p = ds.project
    mt = metrics(p, selected)
    rows = [{"credit_id": "BASE", "category": "Base design credits", "name": "Already earned in base design",
             "points": p.base_points, "max": p.base_points}]
    missing = []
    for c in ds.credits:
        if c.rule == "fixed":
            pts = sum(m.points_fixed for m in selected if m.credit_id == c.credit_id)
        else:
            pts = _threshold_points(mt[{"energy_eff": "energy_eff_pct", "energy_re": "energy_re_pct",
                                        "water": "water_pct"}[c.basis]], c.thresholds)
        pts = min(pts, c.max_points)
        if c.mandatory and pts <= 0:
            missing.append(c.credit_id)
        rows.append({"credit_id": c.credit_id, "category": c.category, "name": c.name,
                     "points": pts, "max": c.max_points})
    bd = pd.DataFrame(rows)
    total = float(bd["points"].sum())
    level, rank = "Not certified", 0
    for lv in sorted(ds.levels, key=lambda x: x.rank):
        if total >= lv.min_points:
            level, rank = lv.level, lv.rank
    return Score(total, level, rank, not missing, missing, bd, mt)


def max_reachable(ds: Dataset) -> float:
    """Upper bound on points (all credits at max) - used only for friendly messages."""
    return ds.project.base_points + sum(c.max_points for c in ds.credits)
