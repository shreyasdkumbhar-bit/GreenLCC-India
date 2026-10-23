"""Robustness: bad input must produce readable errors, and degenerate models must not crash."""
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import cashflow, extract, optimizer, report, risk  # noqa: E402
from core.io import DATA_DIR, load_dataset, rows_to_models  # noqa: E402
from core.schemas import Measure  # noqa: E402


@pytest.fixture()
def data_copy(tmp_path):
    for f in DATA_DIR.iterdir():
        shutil.copy(f, tmp_path / f.name)
    return tmp_path


def test_bad_rows_are_reported_not_raised(data_copy):
    m = pd.read_csv(data_copy / "measures.csv")
    m.loc[0, "capex"] = -5          # negative capex
    m.loc[1, "subsidy"] = 9e9       # subsidy > capex
    m.loc[2, "credit_id"] = "NOPE"  # unknown credit
    m.to_csv(data_copy / "measures.csv", index=False)
    ds, errs = load_dataset(data_copy)
    assert ds is None
    text = " ".join(errs)
    assert "capex" in text and "subsidy" in text and "NOPE" in text


def test_missing_file_is_reported(data_copy):
    (data_copy / "igbc_levels.csv").unlink()
    ds, errs = load_dataset(data_copy)
    assert ds is None and any("igbc_levels.csv" in e for e in errs)


def test_bad_project_values_rejected(data_copy):
    import json
    raw = json.loads((data_copy / "project_demo.json").read_text())
    raw["discount_rate"] = 0.9
    (data_copy / "project_demo.json").write_text(json.dumps(raw))
    ds, errs = load_dataset(data_copy)
    assert ds is None and "discount_rate" in " ".join(errs)


def test_unknown_target_level_rejected(data_copy):
    import json
    raw = json.loads((data_copy / "project_demo.json").read_text())
    raw["target_level"] = "Diamond"
    (data_copy / "project_demo.json").write_text(json.dumps(raw))
    ds, errs = load_dataset(data_copy)
    assert ds is None and "Diamond" in " ".join(errs)


def test_blank_group_becomes_independent():
    ms, errs = rows_to_models(pd.DataFrame([{"measure_id": "A", "name": "a", "exclusive_group": float("nan"), "capex": 1}]), Measure, "t")
    assert not errs and ms[0].group == "A"


@pytest.fixture(scope="module")
def ds():
    d, errs = load_dataset()
    assert not errs
    return d


def test_zero_benefit_measure_has_positive_lcc(ds):
    m = Measure(measure_id="DUD", name="dud", capex=1_000_000)
    S = cashflow.measure_streams(ds.project, m, [])
    assert cashflow.evaluate(S, ds.project).scalar("lcc") == pytest.approx(1_000_000)
    assert cashflow.summarize(S, ds.project)["payback"] is None   # never pays back


def test_empty_library_still_scores_base(ds):
    empty = ds.model_copy(update={"measures": [], "components": []})
    t = optimizer.enumerate_portfolios(empty)
    assert len(t) == 1 and t.iloc[0]["points"] == ds.project.base_points


def test_too_many_combinations_guarded(ds):
    many = [Measure(measure_id=f"M{i}", name=f"m{i}", capex=1) for i in range(25)]
    big = ds.model_copy(update={"measures": many, "components": []})
    with pytest.raises(ValueError, match="too many"):
        optimizer.enumerate_portfolios(big)


def test_far_benefit_flips_choice_toggle(ds):
    on = optimizer.enumerate_portfolios(ds)
    off_ds = ds.model_copy(update={"project": ds.project.model_copy(update={"use_far_benefit": False})})
    off = optimizer.enumerate_portfolios(off_ds)
    assert (on["net_lcc"] <= on["lcc"]).all()
    assert (off["net_lcc"] == off["lcc"]).all()


def test_short_study_period_runs(ds):
    short = ds.model_copy(update={"project": ds.project.model_copy(update={"study_period": 5})})
    t = optimizer.enumerate_portfolios(short)
    assert len(t) > 0 and t["lcc"].notna().all()


def test_extraction_regex_on_all_samples():
    got = {p.name: extract.extract(str(p)) for p in (Path(__file__).resolve().parent.parent / "sample_quotes").glob("*.pdf")}
    assert len(got) == 3
    assert got["SunRise_Solar_100kWp_quote.pdf"].capex == 4_400_000
    assert got["CoolAir_VRF_120TR_quote.pdf"].component_life_years == 15
    assert all(not q.missing() for q in got.values())


def test_quote_to_measure_is_incremental(ds):
    q = extract.extract(str(Path(__file__).resolve().parent.parent / "sample_quotes" / "CoolAir_VRF_120TR_quote.pdf"))
    m, comps = extract.to_measure(q, measure_id="V", kind="efficiency", baseline_cost=13_200_000, baseline_om=220_000)
    assert m.capex == 6_000_000 and m.om_annual == 200_000 and comps[0].life_years == 15


def test_template_report_never_crashes_and_has_numbers(ds):
    df = optimizer.enumerate_portfolios(ds)
    res = report.collect_results(ds, df, "Gold", "net_lcc", runs=300)
    txt = report.template_narrative(res)
    assert "Recommendation" in txt and "Cr" in txt
    bad = report.collect_results(ds.model_copy(update={"measures": [ds.measure("LIGHT_LED")], "components": []}),
                                 optimizer.enumerate_portfolios(ds.model_copy(update={"measures": [ds.measure("LIGHT_LED")], "components": []})),
                                 "Platinum", "lcc")
    assert not bad["feasible"] and "Platinum" in report.template_narrative(bad)


def test_excel_export_roundtrip(ds):
    import io
    df = optimizer.enumerate_portfolios(ds)
    res = report.collect_results(ds, df, "Gold", "lcc", runs=300)
    rec = optimizer.best(df, ds, "Gold", "lcc")
    xls = pd.ExcelFile(io.BytesIO(report.to_excel(ds, df, rec["selection"], res)))
    assert {"Project", "Measures", "Recommended cash flow", "Results"} <= set(xls.sheet_names)
    cf = xls.parse("Recommended cash flow", index_col=0)
    assert cf["Present worth"].sum() == pytest.approx(risk.lcc(ds, rec["selection"]), rel=1e-6)
