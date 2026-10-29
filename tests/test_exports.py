"""Output files: PDF, results Excel and the input workbook must be valid, complete and consistent with the engine."""
import io
import sys
from pathlib import Path

import pandas as pd
import pdfplumber
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import exports, optimizer, report, risk, tables  # noqa: E402
from core.io import load_dataset, read_workbook, write_workbook  # noqa: E402


@pytest.fixture(scope="module")
def ds():
    d, errs = load_dataset()
    assert not errs
    return d


@pytest.fixture(scope="module")
def files(ds):
    return exports.build_files(ds, "Gold", runs=400)


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
    assert "Documents to submit" in text and "MARR" in text and "EUAC" in text and "BCR" in text
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
    best = optimizer.best(df, ds, "Gold", "lcc")
    assert cl.iloc[-1]["Points earned"] == best["points"]
    assert (cl.iloc[:-1]["Points earned"] <= cl.iloc[:-1]["Maximum"]).all()


def test_shortlist_lists_each_selected_measure(ds, files):
    sl = tables.shortlist(ds, files["rec_sel"])
    assert list(sl["Measure ID"]) == list(files["rec_sel"])
    assert (sl["Upfront capex (Rs)"] >= 0).all()


def test_input_workbook_roundtrip(ds):
    """The input workbook must reopen as the same dataset."""
    back, errs = read_workbook(write_workbook(ds))
    assert not errs, errs
    assert back == ds


def test_results_workbook_reopens_as_input(ds, files):
    back, errs = read_workbook(files["xlsx"])
    assert not errs, errs
    assert back == ds


def test_input_workbook_rejects_bad_credit(ds):
    from core.io import input_sheets
    sh = input_sheets(ds)
    sh["Measures"].loc[0, "IGBC credit"] = "XX-C9"
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, d in sh.items():
            d.to_excel(xw, sheet_name=name, index=False)
    back, errs = read_workbook(buf.getvalue())
    assert back is None and any("unknown IGBC credit" in e for e in errs)


def test_monte_carlo_sheet(files):
    mc = pd.ExcelFile(io.BytesIO(files["xlsx"])).parse("Monte Carlo runs")
    assert len(mc) == 400 and mc.notna().all().all()


def test_unreachable_target_gives_valid_pdf(ds):
    small = ds.model_copy(update={"measures": [ds.measure("LIGHT_LED")]})
    f = exports.build_files(small, "Platinum", runs=200)
    assert not f["feasible"]
    df = optimizer.enumerate_portfolios(small)
    pdf = exports.decision_pdf(small, df, f["res"], (), ())
    with pdfplumber.open(io.BytesIO(pdf)) as p:
        assert "Target not reachable" in (p.pages[0].extract_text() or "")


def test_negative_zero_percent_helper():
    assert report.pct(-0.0001) == "0.0%" and report.pct(0.143) == "14.3%" and report.pct(-0.02) == "-2.0%"


def test_glossary_covers_every_screen_label(tmp_path):
    import subprocess

    from core.glossary import TERMS
    from core.ui import LABELS

    keys = {t[-1] for t in TERMS if t[-1]}
    assert set(LABELS) <= keys, set(LABELS) - keys
    root = Path(__file__).resolve().parent.parent
    subprocess.run([sys.executable, str(root / "scripts" / "make_glossary_pdf.py"), str(tmp_path)], check=True, cwd=root)
    with pdfplumber.open(tmp_path / "GreenLCC_Glossary.pdf") as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    assert "Incremental IRR" in text and "MIRR" in text and "CO?" not in text and "= ? (" not in text
