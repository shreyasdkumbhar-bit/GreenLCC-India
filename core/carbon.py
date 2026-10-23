"""Lifetime CO2 avoided and marginal abatement cost."""
from __future__ import annotations

from .cashflow import Streams
from .schemas import Project


def lifetime_co2_t(p: Project, S: Streams) -> float:
    """Tonnes CO2 avoided over the study period (constant grid factor; exports displace grid power)."""
    kwh = (S.kwh_eff + S.kwh_re_self + S.kwh_re_exp).sum()
    return float(kwh / 1000.0 * p.grid_emission_factor)


def cost_per_tonne(lcc: float, co2_t: float) -> float | None:
    """Rs per tCO2 avoided; negative means the measure saves money while cutting carbon."""
    return None if co2_t <= 0 else lcc / co2_t
