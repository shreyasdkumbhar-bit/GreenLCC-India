"""Robustness: bad input must produce readable errors, and degenerate models must not crash."""
import io
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import cashflow, extract, optimizer, report, risk  # noqa: E402
from core.io import input_sheets, load_dataset, read_workbook, rows_to_models  # noqa: E402
from core.schemas import Measure  # noqa: E402

SAMPLES = Path(__file__).resolve().parent.parent / "sample_quotes"


@pytest.fixture(scope="module")
def ds():
    d, errs = load_dataset()
    assert not errs
    return d


def to_xlsx(sheets: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name, index=False)
    return buf.getvalue()


def test_bad_rows_are_reported_not_raised(ds):
    sh = input_sheets(ds)
    m = sh["Measures"]
    m.loc[0, "Capex (incremental)"] = -5           # negative capex
    m.loc[1, "Part cost"] = 50_000                  # part cost without a part life
    m.loc[1, "Part life"] = 0
    m.loc[2, "IGBC credit"] = "NOPE"                # unknown credit
    back, errs = read_workbook(to_xlsx(sh))
    assert back is None
    text = " ".join(errs)
    assert "capex" in text and "part_life" in text and "NOPE" in text


def test_missing_sheet_is_reported(ds):
    sh = input_sheets(ds)
    del sh["IGBC_levels"]
    back, errs = read_workbook(to_xlsx(sh))
    assert back is None and any("IGBC_levels" in e for e in errs)


def test_not_excel_is_reported():
    back, errs = read_workbook(b"not a spreadsheet")
    assert back is None and "Excel" in errs[0]


def _set_project(ds, field, value) -> bytes:
    sh = input_sheets(ds)
    sh["Project"].loc[sh["Project"]["field"] == field, "value"] = value
    return to_xlsx(sh)


def test_bad_project_values_rejected(ds):
    back, errs = read_workbook(_set_project(ds, "discount_rate", 90))   # typed as %: 90% is out of range
    assert back is None and "discount_rate" in " ".join(errs)


def test_percent_fields_are_typed_as_percent(ds):
    back, errs = read_workbook(_set_project(ds, "discount_rate", 12))
    assert not errs and back.project.discount_rate == pytest.approx(0.12)


def test_unknown_target_level_rejected(ds):
    back, errs = read_workbook(_set_project(ds, "target_level", "Diamond"))
    assert back is None and "Diamond" in " ".join(errs)


def test_blank_group_becomes_independent():
    rows = pd.DataFrame([{"measure_id": "A", "name": "a", "exclusive_group": float("nan"), "capex": 1, "life_years": 10}])
    ms, errs = rows_to_models(rows, Measure, "t")
    assert not errs and ms[0].group == "A"


def test_zero_benefit_measure_has_positive_lcc(ds):
    m = Measure(measure_id="DUD", name="dud", capex=1_000_000, life_years=ds.project.study_period)
    S = cashflow.measure_streams(ds.project, m)
    assert cashflow.evaluate(S, ds.project).scalar("lcc") == pytest.approx(1_000_000)
    s = cashflow.summarize(S, ds.project)
    assert s["disc_payback"] is None and s["bcr"] == 0 and s["ror"] is None   # never pays back, no rate of return


def test_empty_library_still_scores_base(ds):
    empty = ds.model_copy(update={"measures": []})
    t = optimizer.enumerate_portfolios(empty)
    assert len(t) == 1 and t.iloc[0]["points"] == ds.project.base_points


def test_too_many_combinations_guarded(ds):
    many = [Measure(measure_id=f"M{i}", name=f"m{i}", capex=1, life_years=10) for i in range(25)]
    with pytest.raises(ValueError, match="too many"):
        optimizer.enumerate_portfolios(ds.model_copy(update={"measures": many}))


def test_short_study_period_runs(ds):
    short = ds.model_copy(update={"project": ds.project.model_copy(update={"study_period": 5})})
    t = optimizer.enumerate_portfolios(short)
    assert len(t) > 0 and t["lcc"].notna().all()


def test_extraction_regex_on_all_samples():
    got = {p.name: extract.extract(str(p)) for p in SAMPLES.glob("*.pdf")}
    assert len(got) == 3
    assert got["SunRise_Solar_150kWp_quote.pdf"].capex == 6_750_000
    assert got["SunRise_Solar_150kWp_quote.pdf"].component_life_years == 12
    assert got["CoolAir_VRF_350TR_quote.pdf"].om_annual == 525_000
    assert all(not q.missing() for q in got.values())


def test_quote_to_measure_is_incremental(ds):
    q = extract.extract(str(SAMPLES / "CoolAir_VRF_350TR_quote.pdf"))
    m = extract.to_measure(q, measure_id="V", life_years=15, baseline_cost=15_750_000, baseline_om=350_000)
    assert m.capex == ds.measure("HVAC_VRF").capex and m.om_annual == ds.measure("HVAC_VRF").om_annual
    q = extract.extract(str(SAMPLES / "SunRise_Solar_150kWp_quote.pdf"))
    m = extract.to_measure(q, measure_id="S", life_years=25, kwp=extract.capacity_kwp(q.capacity))
    assert m.kwp == 150 and m.part_cost == 750_000 and m.part_life == 12


def test_template_report_never_crashes_and_has_numbers(ds):
    df = optimizer.enumerate_portfolios(ds)
    res = report.collect_results(ds, df, "Gold", runs=300)
    txt = report.template_narrative(res)
    assert "Recommendation" in txt and "Cr" in txt and "MARR" in txt
    small = ds.model_copy(update={"measures": [ds.measure("LIGHT_LED")]})
    bad = report.collect_results(small, optimizer.enumerate_portfolios(small), "Platinum")
    assert not bad["feasible"] and "Platinum" in report.template_narrative(bad)


def test_excel_export_cash_flow_matches_engine(ds):
    df = optimizer.enumerate_portfolios(ds)
    res = report.collect_results(ds, df, "Gold", runs=300)
    rec = optimizer.best(df, ds, "Gold", "lcc")
    xls = pd.ExcelFile(io.BytesIO(report.to_excel(ds, df, rec["selection"], res)))
    assert {"Project", "Measures", "IGBC_credits", "IGBC_levels", "Recommended cash flow", "Results"} <= set(xls.sheet_names)
    cf = xls.parse("Recommended cash flow", index_col=0)
    assert cf["Present worth"].sum() == pytest.approx(risk.lcc(ds, rec["selection"]), rel=1e-6)
