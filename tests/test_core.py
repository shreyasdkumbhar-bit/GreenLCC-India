"""Hand-calculation checks for the LCCA engine, IGBC scoring and optimizer."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import cashflow, finance, igbc, optimizer, risk  # noqa: E402
from core.io import load_dataset  # noqa: E402
from core.schemas import Measure  # noqa: E402


@pytest.fixture(scope="module")
def ds():
    d, errs = load_dataset()
    assert not errs, errs
    return d


@pytest.fixture()
def proj(ds):
    def make(**over):
        base = dict(discount_rate=0.10, inflation=0.0, grid_tariff=1.0, tariff_escalation=0.0, study_period=10)
        return ds.project.model_copy(update={**base, **over})
    return make


def annuity(d, n):
    return (1 - (1 + d) ** -n) / d


def X(**kw) -> Measure:
    return Measure(**{"measure_id": "X", "name": "x", "capex": 0, "life_years": 50, **kw})


# ---------- finance ----------
def test_crf_matches_textbook():
    assert finance.crf(0.10, 10) == pytest.approx(0.162745, abs=1e-6)
    assert finance.eac(1000, 0.10, 10) == pytest.approx(162.745, abs=1e-3)


def test_payback_interpolates():
    net = np.array([100.0, -40.0, -40.0, -40.0])
    assert finance.payback_year(net) == pytest.approx(2.5)
    assert finance.payback_year(np.array([100.0, 10.0])) is None


# ---------- cash-flow engine ----------
def test_simple_measure_lcc_hand_calc(proj):
    p = proj()
    S = cashflow.measure_streams(p, X(capex=1000, life_years=10, energy_saving_kwh=100))
    assert cashflow.evaluate(S, p).scalar("lcc") == pytest.approx(1000 - 100 * annuity(0.10, 10), abs=1e-6)


def test_part_replacement_inside_period_and_none_at_end(proj):
    p = proj()
    S = cashflow.measure_streams(p, X(part_cost=200, part_life=5))
    assert S.repl[5] == 200 and S.repl[10] == 0       # replaced at 5, not at the very end
    assert S.resid[10] == 0                           # exactly used up
    assert cashflow.evaluate(S, p).scalar("repl") == pytest.approx(200 / 1.1**5)


def test_part_residual_linear_remaining_life(proj):
    p = proj(study_period=8)
    S = cashflow.measure_streams(p, X(part_cost=200, part_life=5))
    assert S.repl[5] == 200
    assert S.resid[8] == pytest.approx(200 * 0.4)     # bought at t=5, 2 of 5 years left
    assert cashflow.evaluate(S, p).scalar("resid") == pytest.approx(80 / 1.1**8)


def test_whole_measure_rebought_and_salvaged(proj):
    p = proj(inflation=0.05)
    S = cashflow.measure_streams(p, X(capex=1000, life_years=6))
    assert S.repl[6] == pytest.approx(1000 * 1.05**6)                       # re-bought at today's price, inflated
    assert S.resid[10] == pytest.approx(1000 * 1.05**6 * (12 - 10) / 6)    # 2 of 6 years left at N


def test_part_not_double_bought_with_new_measure(proj):
    p = proj(study_period=15)
    S = cashflow.measure_streams(p, X(capex=1000, life_years=10, part_cost=100, part_life=5))
    assert S.repl[5] == 100 and S.repl[10] == 1000    # year 10: the new measure brings a new part
    assert S.resid[15] == pytest.approx(1000 * 0.5)   # salvage of the year-10 purchase only


def test_om_escalates_at_inflation(proj):
    p = proj(inflation=0.05)
    S = cashflow.measure_streams(p, X(om_annual=100))
    assert S.om[0] == 0 and S.om[1] == 100 and S.om[3] == pytest.approx(100 * 1.05**2)


def test_engine_equals_geometric_gradient_factors(proj):
    """Ch 3 closed forms: LCC = P + A_om (P/A1, f, i, n) − A_sav (P/A1, g, i, n) − S (P/F, i, n)."""
    p = proj(inflation=0.04, tariff_escalation=0.06)
    m = X(capex=1000, om_annual=50, energy_saving_kwh=100)          # 50-yr life: 40/50 of it is salvage at year 10
    hand = (1000 + 50 * finance.pa_geo(0.04, 0.10, 10) - 100 * finance.pa_geo(0.06, 0.10, 10)
            - 1000 * 40 / 50 * finance.pf(0.10, 10))
    assert cashflow.evaluate(cashflow.measure_streams(p, m), p).scalar("lcc") == pytest.approx(hand)


def test_escalation_and_degradation(proj):
    p = proj(tariff_escalation=0.05)
    S = cashflow.measure_streams(p, X(energy_saving_kwh=100, degradation=0.01))
    expected = sum(100 * 0.99 ** (t - 1) * 1.05 ** (t - 1) / 1.1**t for t in range(1, 11))
    assert -cashflow.evaluate(S, p).scalar("lcc") == pytest.approx(expected)


def test_pv_splits_self_use_and_export(proj):
    p = proj(pv_self_consumption=0.5, export_tariff=0.0, pv_yield_kwh_per_kwp=1000)
    S = cashflow.measure_streams(p, X(kwp=1))
    # only the self-consumed half is worth the retail tariff; export earns 0 here
    assert -cashflow.evaluate(S, p).scalar("lcc") == pytest.approx(500 * annuity(0.10, 10))


def test_vectorised_matches_scalar(proj):
    p = proj(tariff_escalation=0.04)
    S = cashflow.measure_streams(p, X(capex=500, om_annual=10, energy_saving_kwh=120))
    d = np.array([0.06, 0.08, 0.10])
    vec = cashflow.evaluate(S, p, d=d).lcc
    for i, di in enumerate(d):
        assert vec[i] == pytest.approx(cashflow.evaluate(S, p, d=di).scalar("lcc"))


def test_yearly_table_sums_to_lcc(ds):
    S = risk.portfolio_streams(ds, ["HVAC_VRF", "PV_100", "LIGHT_LED"])
    tab = cashflow.yearly_table(S, ds.project)
    assert tab["Present worth"].sum() == pytest.approx(cashflow.evaluate(S, ds.project).scalar("lcc"))


def test_summary_metrics_agree(ds):
    for m in ds.measures:
        s = cashflow.summarize(risk.portfolio_streams(ds, [m.measure_id]), ds.project)
        assert s["eac"] == pytest.approx(s["lcc"] * finance.ap(ds.project.discount_rate, ds.project.study_period))
        assert (s["lcc"] < 0) == (s["bcr"] > 1)                       # PW and BCR give the same accept/reject
        if s["ror"] is not None:
            assert (s["lcc"] < 0) == (s["ror"] > ds.project.discount_rate)   # ... and so does IRR/MIRR vs MARR


def test_incremental_irr_zeroes_incremental_pw(ds):
    inc = risk.incremental(ds, ("LIGHT_LED",), ("LIGHT_LED", "PV_100"))
    assert inc["extra_capex"] == ds.measure("PV_100").capex
    assert inc["method"] == "IRR" and inc["sign_changes"] == 1
    gain_at_irr = risk.lcc(ds, ("LIGHT_LED",), d=inc["rate"]) - risk.lcc(ds, ("LIGHT_LED", "PV_100"), d=inc["rate"])
    assert gain_at_irr == pytest.approx(0, abs=1.0)


# ---------- IGBC ----------
def test_base_points_only(ds):
    s = igbc.score(ds, [])
    assert s.total == ds.project.base_points
    assert not s.mandatory_ok and s.missing_mandatory == ["WE-C1"]   # no fixtures yet


def test_threshold_and_fixed_points(ds):
    sel = [ds.measure(i) for i in ("LIGHT_LED", "WTR_FIX", "PV_100")]
    s = igbc.score(ds, sel).breakdown.set_index("credit_id")["points"]
    assert s["EE-C4"] == 3                  # fixed credit
    assert s["WE-C1"] == 1                  # 3,500 / 14,000 = 25% crosses the 15% threshold only
    assert s["EE-C3"] == 4                  # 145 MWh / (1.8 GWh − 108 MWh) = 8.6% -> 5% threshold
    assert s["EE-C2"] == 1                  # LED saves 108 MWh / 1.8 GWh = 6% -> 5% threshold


def test_credit_cap_respected(ds):
    bd = igbc.score(ds, list(ds.measures)).breakdown
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
    assert all(sum(ds.measure(i).kwp for i in sel) <= ds.project.roof_kwp_cap for sel in table["selection"])


def test_best_is_feasible_and_optimal(ds, table):
    for obj in ("capex", "lcc"):
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
    for key, kw in (("capex_mult", "capex_mult"), ("discount", "d")):
        x = risk.break_even(ds, a, b, key)
        if x is not None:
            assert risk.lcc(ds, a, **{kw: x}) == pytest.approx(risk.lcc(ds, b, **{kw: x}), abs=1.0)
