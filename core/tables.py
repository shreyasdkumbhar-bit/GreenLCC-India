"""Ready-to-use tables derived from a chosen portfolio (feed the PDF report and the Excel workbook)."""
from __future__ import annotations

import pandas as pd

from . import cashflow, igbc, risk
from .schemas import Dataset

# Indicative evidence an IGBC submission usually needs; verify against the official reference guide.
EVIDENCE = {
    "EE-C2": "Whole-building energy simulation report vs baseline; ECBC/ECSBC compliance sheet; HVAC and glazing datasheets",
    "EE-C3": "Solar PV single-line diagram; generation estimate; net-metering approval; inverter and module datasheets",
    "EE-C4": "Lighting power density calculation; luminaire schedule; controls layout",
    "EE-C5": "Metering schematic; BMS points list; commissioning report",
    "WE-C1": "Fixture schedule with flow rates; water-balance calculation; manufacturer cut-sheets",
    "WE-C2": "STP design basis; treated-water reuse calculation; O&M plan",
    "SS-C3": "Roof layout with SRI values; coating datasheet; area calculation",
    "IEQ-C1": "Glazing specification (VLT, SHGC, U-value); daylight simulation report",
    "BASE": "Documents for credits already earned in the base design",
}


def checklist(ds: Dataset, sel) -> pd.DataFrame:
    chosen = [ds.measure(i) for i in sel]
    sc = igbc.score(ds, chosen)
    kind_for = {"energy_eff": "efficiency", "energy_re": "renewable", "water": "water"}
    credit = {c.credit_id: c for c in ds.credits}
    rows = []
    for _, r in sc.breakdown.iterrows():
        cid = r["credit_id"]
        if cid == "BASE":
            by = "Base design"
        else:
            c = credit[cid]
            if c.rule == "fixed":
                who = [m.name for m in chosen if m.credit_id == cid]
            else:
                who = [m.name for m in chosen if m.kind == kind_for[c.basis]]
            by = "; ".join(who) or "(nothing selected)"
        rows.append({"Credit": cid, "Category": r["category"], "Credit name": r["name"], "Points earned": r["points"],
                     "Maximum": r["max"], "Earned by": by, "Documents to submit (indicative)": EVIDENCE.get(cid, ""),
                     "Status": "Earned" if r["points"] > 0 else "Not pursued"})
    out = pd.DataFrame(rows)
    out.loc[len(out)] = {"Credit": "TOTAL", "Category": "", "Credit name": f"Level reached: {sc.level}", "Points earned": sc.total,
                         "Maximum": out["Maximum"].sum(), "Earned by": "", "Documents to submit (indicative)": "", "Status": ""}
    return out


def shortlist(ds: Dataset, sel) -> pd.DataFrame:
    """Procurement shortlist: what to buy, what it costs over its life."""
    p = ds.project
    rows = []
    for i in sel:
        m = ds.measure(i)
        comps = ds.comps_for(i)
        S = risk.portfolio_streams(ds, [i])
        ev = cashflow.summarize(S, p)
        rows.append({
            "Measure ID": m.measure_id, "Measure": m.name, "Group": m.exclusive_group or "", "Source": m.source,
            "Upfront capex (Rs)": m.capex - m.subsidy, "Annual O&M, year 1 (Rs)": m.om_annual,
            "Replaceable components": "; ".join(f"{c.component} (every {c.life_years:g} yrs, Rs {c.cost:,.0f})" for c in comps),
            "Energy saved (kWh/yr)": m.energy_saving_kwh or m.kwp * p.pv_yield_kwh_per_kwp,
            "Water saved (kL/yr)": m.water_saving_kl, "IGBC credit": m.credit_id,
            f"LCC over {p.study_period} yrs (Rs)": ev["lcc"], "EAC (Rs/yr)": ev["eac"], "Simple payback (yrs)": ev["payback"],
        })
    return pd.DataFrame(rows)


def cashflow_table(ds: Dataset, sel) -> pd.DataFrame:
    return cashflow.yearly_table(risk.portfolio_streams(ds, sel), ds.project)


def mc_runs(ds: Dataset, a, b, runs: int = 5000, seed: int = 42) -> pd.DataFrame:
    mc = risk.monte_carlo(ds, a, b, runs, seed)
    return pd.DataFrame({"run": range(1, runs + 1), "net_lcc_A_cheapest_upfront_Rs": mc.lcc_a, "net_lcc_B_recommended_Rs": mc.lcc_b})
