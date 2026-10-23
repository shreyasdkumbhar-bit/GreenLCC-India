---
name: greenlcc-run
description: Start, check and demo the GreenLCC India Streamlit app (IGBC credit optimizer with life-cycle costing). Use when asked to run, launch, test, screenshot or demo the tool, or to rebuild its PDFs.
---

# Running GreenLCC India

All commands run from the repository root (the folder with `app.py`).

## Start the app
- `python -m streamlit run app.py --server.headless true --server.port 8501`
- Open http://localhost:8501, then click **Try the Pune demo** on Home.
- Pages: Home, `pages/1_setup.py`, `pages/2_recommendation.py` (centrepiece), `pages/3_trust.py`, `pages/4_report.py`.
- The sidebar (rendered by `app.py` via `ui.sidebar_controls`) holds the target level (`session_state["target"]`) and the FAR switch.

## Check it
- `python -m pytest tests -q`: engine hand-calcs, IGBC, optimizer, risk, exports and headless UI (AppTest).
- AppTest quirk: after the first run with `st.navigation`, AppTest re-runs only the page script, not `app.py`. Test sidebar
  behaviour with `AppTest.from_function` (see `tests/test_ui.py::_sidebar_app`), not via `at.sidebar`.
- To look at a PDF: render pages to PNG with pdfplumber (`page.to_image(resolution=75).save(...)`) and read the image.

## Rebuild documents (after any data or model change)
- `python scripts/make_docs_pdfs.py` rebuilds `docs/GreenLCC_User_Guide.pdf` and `docs/GreenLCC_About.pdf` with live numbers.
- Log the change in `docs/PROJECT_LOG.md`, then `python scripts/update_log_index.py`.

## Rules
- Data in `data/` and `sample_quotes/` is illustrative; never present it as verified.
- Machine has NumPy 1.26: keep `pyarrow<22`. Reportlab base fonts are Latin-1: write "Rs", not ₹, in PDFs.
