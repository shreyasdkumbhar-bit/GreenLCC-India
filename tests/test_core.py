"""Hand-calculation checks for the LCCA engine, IGBC scoring and optimizer."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import cashflow, finance, igbc, optimizer, risk  # noqa: E402
from core.io import DATA_DIR, load_dataset  # noqa: E402
from core.schemas import Component, Measure, Project  # noqa: E402


def make_project(**over) -> Project:
    raw = json.loads((DATA_DIR / "project_demo.json").read_text())
    raw = {k: v for k, v in raw.items() if not k.startswith("_")}
    base = dict(discount_rate=0.10, inflation=0.0, grid_tariff=1.0, tariff_escalation=0.0, study_period=10)
    raw.update({**base, **over})
    return Project(**raw)


def annuity(d, n):
    return (1 - (1 + d) ** -n) / d


# ---------- finance ----------
def test_crf_matches_textbook():
    assert finance.crf(0.10, 10) == pytest.approx(0.162745, abs=1e-6)
    assert finance.eac(1000, 0.10, 10) == pytest.approx(162.745, abs=1e-3)


def test_payback_interpolates():
    net = np.array([100.0, -40.0, -40.0, -40.0])
    assert finance.payback_year(net) == pytest.approx(2.5)
    assert finance.payback_year(np.array([100.0, 10.0])) is None


# ---------- cash-flow engine ----------
def test_simple_measure_lcc_hand_calc():
    p = make_project()
    m = Measure(measure_id="X", name="x", capex=1000, energy_saving_kwh=100)
    S = cashflow.measure_streams(p, m, [])
    got = cashflow.evaluate(S, p).scalar("lcc")
    assert got == pytest.approx(1000 - 100 * annuity(0.10, 10), abs=1e-6)


def test_replacement_inside_period_and_none_at_end():
    p = make_project()
    m = Measure(measure_id="X", name="x", capex=0)
    S = cashflow.measure_streams(p, m, [Component(measure_id="X", component="c", cost=200, life_years=5)])
    assert S.repl[5] == 200 and S.repl[10] == 0       # replaced at 5, not at the very end
    assert S.resid[10] == 0                           # exactly used up
    assert cashflow.evaluate(S, p).scalar("repl") == pytest.approx(200 / 1.1**5)


def test_residual_value_linear_remaining_life():
    p = make_project(study_period=8)
    m = Measure(measure_id="X", name="x", capex=0)
    S = cashflow.measure_streams(p, m, [Component(measure_id="X", component="c", cost=200, life_years=5)])
    assert S.repl[5] == 200
    assert S.resid[8] == pytest.approx(200 * 0.4)     # bought at t=5, 2 of 5 years left
    assert cashflow.evaluate(S, p).scalar("resid") == pytest.approx(80 / 1.1**8)


def test_escalation_and_degradation():
    p = make_project(tariff_escalation=0.05)
    m = Measure(measure_id="X", name="x", capex=0, energy_saving_kwh=100, degradation=0.01)
    S = cashflow.measure_streams(p, m, [])
    expected = sum(100 * 0.99 ** (t - 1) * 1.05 ** (t - 1) / 1.1**t for t in range(1, 11))
    assert -cashflow.evaluate(S, p).scalar("lcc") == pytest.approx(expected)


def test_pv_splits_self_use_and_export():
    p = make_project(pv_self_consumption=0.5, export_tariff=0.0, pv_yield_kwh_per_kwp=1000)
    m = Measure(measure_id="PV", name="pv", kind="renewable", capex=0, kwp=1)
    S = cashflow.measure_streams(p, m, [])
    # only the self-consumed half is worth the retail tariff; export earns 0 here
    assert -cashflow.evaluate(S, p).scalar("lcc") == pytest.approx(500 * annuity(0.10, 10))


def test_vectorised_matches_scalar():
    p = make_project(tariff_escalation=0.04)
    m = Measure(measure_id="X", name="x", capex=500, om_annual=10, energy_saving_kwh=120)
    S = cashflow.measure_streams(p, m, [])
    d = np.array([0.06, 0.08, 0.10])
    vec = cashflow.evaluate(S, p, d=d).lcc
    for i, di in enumerate(d):
        assert vec[i] == pytest.approx(cashflow.evaluate(S, p, d=di).scalar("lcc"))


def test_yearly_table_sums_to_lcc():
    ds, errs = load_dataset()
    assert not errs
    S = risk.portfolio_streams(ds, ["HVAC_VRF", "PV_100", "LIGHT_LED"])
    tab = cashflow.yearly_table(S, ds.project)
    assert tab["Present worth"].sum() == pytest.approx(cashflow.evaluate(S, ds.project).scalar("lcc"))


# ---------- IGBC ----------
@pytest.fixture(scope="module")
def ds():
    d, errs = load_dataset()
    assert not errs, errs
    return d


def test_base_points_only(ds):
    s = igbc.score(ds, [])
    assert s.total == ds.project.base_points
    assert not s.mandatory_ok and s.missing_mandatory == ["WE-C1"]   # no fixtures yet


def test_threshold_and_fixed_points(ds):
    sel = [ds.measure(i) for i in ("LIGHT_LED", "WTR_FIX", "PV_100")]
    s = igbc.score(ds, sel).breakdown.set_index("credit_id")["points"]
    assert s["EE-C4"] == 3                  # fixed credit
    assert s["WE-C1"] == 1                  # 20% water saving crosses the 15% threshold only
    assert s["EE-C3"] == 4                  # ~8% renewable -> 5% threshold
    assert s["EE-C2"] == 1                  # LED saves 54k/1.8M = 3.0% -> first threshold (3%) = 1 pt


def test_credit_cap_respected(ds):
    everything = [m for m in ds.measures]
    bd = igbc.score(ds, everything).breakdown
    assert (bd["points"] <= bd["max"] + 1e-9).all()


# ---------- optimizer ----------
@pytest.fixture(scope="module")
def table(ds):
    return optimizer.enumerate_portfolios(ds)


def test_one_option_per_exclusive_group(ds, table):
    grp = {m.measure_id: m.group for m in ds.measures}
    for sel in table["selection"]:
        groups = [grp[i] for i in sel]
        assert len(groups) == len(set(groups))


def test_roof_limit_respected(ds, table):
    cap = ds.project.roof_area_m2 / ds.project.pv_area_per_kwp_m2
    assert all(sum(ds.measure(i).kwp for i in sel) <= cap for sel in table["selection"])


def test_best_is_feasible_and_optimal(ds, table):
    for obj in ("capex", "lcc", "net_lcc"):
        b = optimizer.best(table, ds, "Gold", obj)
        f = optimizer.feasible(table, ds, "Gold")
        assert b["points"] >= 70 and b["mandatory_ok"]
        assert b[obj] == f[obj].min()


def test_min_lcc_never_costlier_than_min_capex_in_lcc(ds, table):
    assert optimizer.best(table, ds, "Gold", "lcc")["lcc"] <= optimizer.best(table, ds, "Gold", "capex")["lcc"]


def test_infeasible_target_is_reported(ds):
    small = ds.model_copy(update={"measures": [ds.measure("LIGHT_LED"), ds.measure("WTR_FIX")]})
    t = optimizer.enumerate_portfolios(small)
    assert optimizer.best(t, small, "Platinum", "lcc") is None
    assert "Platinum needs" in optimizer.infeasible_message(t, small, "Platinum")


def test_pareto_is_non_dominated(table):
    par = optimizer.pareto(table)
    pts, cost = par["points"].to_numpy(), par["lcc"].to_numpy()
    for i in range(len(par)):
        assert not ((pts > pts[i]) & (cost <= cost[i])).any()


def test_breakdown_sums_to_lcc(table):
    r = table.iloc[40]
    assert sum(optimizer.breakdown(r).values()) == pytest.approx(r["lcc"])


# ---------- risk ----------
def test_monte_carlo_is_reproducible(ds, table):
    a = optimizer.best(table, ds, "Gold", "capex")["selection"]
    b = optimizer.best(table, ds, "Gold", "lcc")["selection"]
    r1, r2 = risk.monte_carlo(ds, a, b, runs=500, seed=7), risk.monte_carlo(ds, a, b, runs=500, seed=7)
    assert np.array_equal(r1.lcc_b, r2.lcc_b) and 0 <= r1.p_b_better <= 1


def test_break_even_is_a_real_root(ds):
    a, b = ("WTR_STP", "COOLROOF"), ("PV_100",)
    x = risk.break_even(ds, a, b, "tariff_mult")
    if x is not None:
        assert risk.lcc(ds, a, tariff_mult=x) == pytest.approx(risk.lcc(ds, b, tariff_mult=x), abs=1.0)
