"""The CE 725 worked examples, recomputed with core/finance.py (numbers from the chapter PDFs)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import finance as f  # noqa: E402


# ---------- Ch 3: interest factors ----------
def test_ch3_factor_values():
    assert 10_000 * f.fp(0.08, 5) == pytest.approx(14_693.28, abs=0.01)          # CAF example
    assert 5_000 * f.fp(0.12, 5) == pytest.approx(8_811.71, abs=0.01)             # benchmark #0 part 1
    assert 400 * f.pa(0.15, 5) == pytest.approx(1_340.86, abs=0.01)               # deferred series, value at t=2
    assert 850_000 * f.ap(0.01, 48) == pytest.approx(22_383.73, abs=0.05)         # equipment EMI
    assert f.ap(0.10, 4) == pytest.approx(0.315471, abs=1e-6)                     # Ch 6 amortisation table
    assert f.af(0.15, 13) == pytest.approx(0.02911, abs=1e-5)                     # Ch 5 road relay
    assert f.ap(0.10, 5) == pytest.approx(f.af(0.10, 5) + 0.10)                   # (A/P) = (A/F) + i


def test_ch3_gradient_factors():
    assert f.ag(0.05, 4) == pytest.approx(1.439, abs=1e-3)                        # Ch 7 Ex 7.2
    assert f.pg(0.10, 4) == pytest.approx(f.ag(0.10, 4) * f.pa(0.10, 4))
    # geometric gradient = explicit sum of A1(1+g)^(t-1)/(1+i)^t
    g, i, n = 0.05, 0.10, 25
    assert f.pa_geo(g, i, n) == pytest.approx(sum((1 + g) ** (t - 1) / (1 + i) ** t for t in range(1, n + 1)))
    assert f.pa_geo(0.10, 0.10, 5) == pytest.approx(5 / 1.10)


def test_ch2_fisher():
    assert f.real_rate(0.155, 0.05) == pytest.approx(0.10)                        # 1.155 = 1.10 × 1.05


# ---------- Ch 5: present worth ----------
def test_ch5_equal_lives_machine_selection():
    pw_a = 25_000 + 9_000 * f.pa(0.10, 5) - 2_000 * f.pf(0.10, 5)
    pw_b = 35_000 + 7_000 * f.pa(0.10, 5) - 3_500 * f.pf(0.10, 5)
    # the notes print 57,877.20 / 59,364.00; their own factors give 57,875.3 / 59,362.3 (arithmetic slip in the notes)
    assert pw_a == pytest.approx(57_877.20, abs=2.5)
    assert pw_b == pytest.approx(59_364.00, abs=2.5)
    assert pw_a < pw_b                                                            # choose A


def test_ch5_capitalized_cost_bridge():
    truss = 22_300_000 + 8_000 / 0.06 + 10_000 * f.af(0.06, 3) / 0.06 + 45_000 * f.af(0.06, 10) / 0.06
    assert truss == pytest.approx(22_542_587.5, rel=1e-4)


# ---------- Ch 6: EUAW and capital recovery ----------
def test_ch6_unequal_lives_euaw():
    a = -11_000 * f.ap(0.15, 6) - 3_500 + 1_000 * f.af(0.15, 6)
    b = -18_000 * f.ap(0.15, 9) - 3_100 + 2_000 * f.af(0.15, 9)
    assert a == pytest.approx(-6_292.37, abs=0.5)
    assert b == pytest.approx(-6_753.18, abs=0.5)


def test_ch6_capital_recovery_two_forms_agree():
    p, s, i, n = 25_000, 2_000, 0.10, 5
    assert f.capital_recovery(p, s, i, n) == pytest.approx(p * f.ap(i, n) - s * f.af(i, n))
    pw_a = 25_000 + 9_000 * f.pa(0.10, 5) - 2_000 * f.pf(0.10, 5)
    assert f.eac(pw_a, 0.10, 5) == pytest.approx(15_267.34, abs=0.5)               # EUAW = PW × (A/P), Ch 6 case A
    assert f.capital_recovery(25_000, 2_000, 0.10, 5) + 9_000 == pytest.approx(15_267.34, abs=0.5)


# ---------- Ch 7: IRR and incremental IRR ----------
def test_ch7_concrete_pump_irr():
    r = f.irr(np.array([-8_200] + [2_000] * 5))
    assert r == pytest.approx(0.0702, abs=0.001)                                  # interpolated 7.02% in the notes


def test_ch7_gradient_rig_irr():
    assert f.irr(np.array([-700, 100, 175, 250, 325])) == pytest.approx(0.070, abs=0.002)


def test_ch7_scale_trap_incremental():
    a, b = np.array([-100, 120]), np.array([-50, 65])
    assert f.irr(a) == pytest.approx(0.20) and f.irr(b) == pytest.approx(0.30)
    assert f.irr(a - b) == pytest.approx(0.10)                                    # IROR = MARR: indifferent


# ---------- Ch 8: multiple IRR and MIRR ----------
def test_ch8_three_roots():
    cash = np.array([-100, 330, -362.75, 132.825])
    assert f.sign_changes(cash) == 3
    assert f.irr_roots(cash) == pytest.approx([0.05, 0.10, 0.15], abs=1e-6)


def test_ch8_mirr_unified_case():
    cash = np.array([3_000, 0, -10_000, 2_000, 2_000, 2_000, 2_000])
    assert f.mirr(cash, 0.08, 0.10) == pytest.approx(0.092740, abs=1e-5)
    rr = f.rate_of_return(cash, 0.10)
    assert rr["sign_changes"] == 2 and rr["method"] == "MIRR" and rr["irr"] is None


def test_ch8_ranking_paradox_npw_wins():
    x = np.array([-1_000, 100, 350, 600, 850])
    y = np.array([-1_000, 1_000, 200, 200, 200])
    npw = lambda c: sum(v * f.pf(0.10, t) for t, v in enumerate(c))  # noqa: E731
    assert npw(x) == pytest.approx(411.52, abs=0.05) and npw(y) == pytest.approx(361.34, abs=0.1)  # notes round to 361.34
    assert f.irr(x) == pytest.approx(0.2340, abs=2e-3) and f.irr(y) == pytest.approx(0.3436, abs=2e-3)  # notes: 23.40% / 34.36%; exact 23.27% / 34.26%
    assert npw(x) > npw(y) and f.irr(x) < f.irr(y)


def test_simple_series_uses_irr():
    rr = f.rate_of_return(np.array([-8_200] + [2_000] * 5), 0.10)
    assert rr["method"] == "IRR" and rr["rate"] == pytest.approx(0.0702, abs=0.001)
