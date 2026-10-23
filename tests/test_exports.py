"""Output files: PDF, Excel and the project file must be valid, complete and consistent with the engine."""
import io
import json
import sys
from pathlib import Path

import pandas as pd
import pdfplumber
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import exports, optimizer, report, risk, tables  # noqa: E402
from core.io import dump_bundle, load_bundle, load_dataset  # noqa: E402


@pytest.fixture(scope="module")
def ds():
    d, errs = load_dataset()
    assert not errs
    return d


@pytest.fixture(scope="module")
def files(ds):
    return exports.build_files(ds, "Gold", "net_lcc", runs=400)


def test_build_files_complete(files):
    assert files["feasible"]
    for k in ("pdf", "xlsx", "memo"):
        assert files[k], k
    assert not {"zip", "checklist", "shortlist", "cashflow", "mc"} & set(files)   # the CSV/ZIP clutter is gone


def test_pdf_is_valid_and_contains_key_facts(files):
    with pdfplumber.open(io.BytesIO(files["pdf"])) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        assert 5 <= len(pdf.pages) <= 7
    for heading in ("IGBC decision report", "The answer", "two routes", "credit checklist", "What to buy", "Can we trust it", "Yearly cash flow"):
        assert heading in text, heading
    assert "Documents to submit" in text
    assert "Pune" in text and "Gold" in text
    assert "■" not in text and "-0.0%" not in text       # no black boxes / negative zero


def test_excel_sheets_and_numbers(ds, files):
    xls = pd.ExcelFile(io.BytesIO(files["xlsx"]))
    assert xls.sheet_names[0] == "Summary"
    assert {"IGBC checklist", "Procurement shortlist", "Recommended cash flow", "Monte Carlo runs", "Portfolios (top 200)", "Project", "Measures"} <= set(xls.sheet_names)
    cf = xls.parse("Recommended cash flow", index_col=0)
    assert cf["Present worth"].sum() == pytest.approx(risk.lcc(ds, files["rec_sel"]), rel=1e-6)
    summary = xls.parse("Summary")
    assert "RECOMMENDED PORTFOLIO" in summary["Item"].values


def test_checklist_total_matches_optimizer(ds, files):
    cl = tables.checklist(ds, files["rec_sel"])
    df = optimizer.enumerate_portfolios(ds)
    best = optimizer.best(df, ds, "Gold", "net_lcc")
    assert cl.iloc[-1]["Points earned"] == best["points"]
    assert (cl.iloc[:-1]["Points earned"] <= cl.iloc[:-1]["Maximum"]).all()


def test_shortlist_lists_each_selected_measure(ds, files):
    sl = tables.shortlist(ds, files["rec_sel"])
    assert list(sl["Measure ID"]) == list(files["rec_sel"])
    assert (sl["Upfront capex (Rs)"] >= 0).all()


def test_project_file_roundtrip(ds):
    """The single project file must reopen as the same dataset, carrying the chosen target."""
    back, errs = load_bundle(dump_bundle(ds, "Platinum"))
    assert not errs, errs
    assert back.project.target_level == "Platinum"
    assert back.model_copy(update={"project": ds.project}) == ds


def test_project_file_rejects_junk(ds):
    assert load_bundle(b"not json")[0] is None
    assert load_bundle(b'{"a": 1}')[1]
    raw = json.loads(dump_bundle(ds))
    raw["measures"][0]["credit_id"] = "XX-C9"
    back, errs = load_bundle(json.dumps(raw))
    assert back is None and any("unknown credit_id" in e for e in errs)


def test_monte_carlo_sheet(files):
    mc = pd.ExcelFile(io.BytesIO(files["xlsx"])).parse("Monte Carlo runs")
    assert len(mc) == 400 and mc.notna().all().all()


def test_unreachable_target_gives_valid_pdf(ds):
    small = ds.model_copy(update={"measures": [ds.measure("LIGHT_LED")], "components": []})
    f = exports.build_files(small, "Platinum", "lcc", runs=200)
    assert not f["feasible"]
    df = optimizer.enumerate_portfolios(small)
    pdf = exports.decision_pdf(small, df, f["res"], (), ())
    with pdfplumber.open(io.BytesIO(pdf)) as p:
        assert "Target not reachable" in (p.pages[0].extract_text() or "")


def test_negative_zero_percent_helper():
    assert report.pct(-0.0001) == "0.0%" and report.pct(0.143) == "14.3%" and report.pct(-0.02) == "-2.0%"
