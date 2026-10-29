# GreenLCC India

**Reach your IGBC green-building target at the lowest life-cycle cost, with tariff risk measured.**

Most Indian projects pick green measures (solar, efficient air-conditioning, glazing, LED lighting, water fixtures) by lowest upfront price. GreenLCC costs every measure over the building's whole life at the owner's MARR. It then searches every legal combination for the cheapest-over-its-life way to reach Certified, Silver, Gold or Platinum. Finally it checks whether the extra upfront money earns more than the MARR, and how safe that answer is if electricity prices and interest rates change.

Built for **CM 617, Topic 6 (LCCA decision tool)**, using the methods of **CE 725**: present worth over a planning horizon, EUAC, BCR, IRR / incremental IRR / MIRR, discounted payback, sensitivity, break-even and Monte Carlo.

> **Data status.** The demo is a 12,000 m² Pune office sized from one consistent basis. Prices and tariffs are sourced estimates, and every value carries its source in the input workbook. The IGBC point tables are **illustrative**. See `docs/PROJECT_LOG.md`, section 6.

## Start it
| Way | How |
|---|---|
| **Windows, nothing installed** | Unzip `GreenLCC_Windows.zip` and double-click `GreenLCC.exe`. Your browser opens the app. |
| **Windows, with Python 3.10+** | Double-click `Start_GreenLCC.bat`. The first run sets up `.venv` (a few minutes); later runs start at once. |
| **Any OS** | `pip install -r requirements.txt` then `python launcher.py` (or `python -m streamlit run app.py`) |

On Home, click **Try the Pune demo**, then follow the **Next** buttons.

Optional: set `ANTHROPIC_API_KEY` to let Claude read vendor-quote PDFs and polish the memo. Without it, a built-in parser and a template are used, so nothing breaks.

## Documents
| | |
|---|---|
| [`docs/GreenLCC_Glossary.pdf`](docs/GreenLCC_Glossary.pdf) | Every term the tool uses: meaning and formula, CE 725 chapter, and why it matters for the decision |
| [`docs/PROJECT_LOG.md`](docs/PROJECT_LOG.md) | Indexed log of decisions, what worked, what didn't, open questions, data sources, course alignment |
| [`docs/progress.md`](docs/progress.md) | Checklist of the current change set |
| `docs/GreenLCC_User_Guide.pdf`, `docs/GreenLCC_About.pdf` | v2 documents; **out of date** for v3 (FAR, CSV inputs) until rebuilt |

## How it flows
| Step | Screen | What you get |
|---|---|---|
| Home | Try the demo, open your input workbook, or download it to fill in | The answer in one sentence |
| 1 | Set up | Building, MARR (with real MARR via Fisher), tariffs, the measure library, AI quote import |
| 2 | Recommendation | Cheapest-upfront vs lowest-LCC route, **return on the extra capex vs MARR**, cost build-up, what-if, upgrade path, measure comparison (PW, EUAC, BCR, IRR/MIRR, discounted payback, cash flow diagram), factor hand-check |
| 3 | Can we trust it? | Break-even MARR / tariff growth / capex, tornado sensitivity, MARR sweep, Monte Carlo |
| 4 | Report | Decision report (PDF, 6 pages), results workbook (Excel), input workbook (Excel) |

The target IGBC level is in the sidebar and applies to every screen.

## Input: one workbook
`data/demo_input.xlsx` (rebuilt by `scripts/make_demo_input.py`, which holds the sizing basis and sources):

| Sheet | Holds |
|---|---|
| README | How to fill it in, and the meaning and unit of every Measures column |
| Project | One row per input: value, unit, meaning, source/status. % fields are typed as percent |
| Measures | One row per green option, **incremental over the code-minimum option**: capex, life, O&M, energy/water saved, solar kWp, degradation, one replaceable part (cost, life), IGBC credit, group |
| IGBC_credits / IGBC_levels | How credits earn points (fixed, or thresholds on % saving) and the points each level needs |

## Model in one paragraph
Each measure is costed against the code-minimum baseline over one study period N (planning-horizon method). The costs are capex at year 0, plus O&M escalating with inflation, plus re-purchases when the measure or its part wears out (inflated). Subtracted from that are salvage at year N and energy and water savings (tariffs escalating, equipment degrading). All of it is discounted at the nominal MARR: LCC = Σ (Cₜ − Sₜ)/(1+i)ᵗ and EUAC = LCC · (A/P, i, N).

The optimizer checks every portfolio that has one option per group, fits the roof and meets the mandatory credits. It returns the lowest-capex and lowest-LCC mixes for the target. The incremental rate of return of one mix over the other is an IRR when the incremental cash flow changes sign once, and an MIRR at the MARR otherwise.

## Repository layout
```
app.py, launcher.py   Streamlit entry point; one-click launcher (also the exe entry point)
Start_GreenLCC.bat    Windows start from source
pages/                0_home, 1_setup, 2_recommendation, 3_trust, 4_report
core/                 finance (CE 725 factors, IRR/MIRR), cashflow, igbc, optimizer, risk, carbon, extract, report,
                      exports, charts, glossary, ui, state, io (input workbook), schemas
data/demo_input.xlsx  the demo inputs
sample_quotes/        three illustrative vendor quotations (PDF)
tests/                pytest: CE 725 textbook examples, engine hand-checks, IGBC, optimizer, risk, exports, every screen
scripts/              make_demo_input, make_glossary_pdf, build_exe, make_dummy_data, update_log_index (+ v2 doc builders)
docs/                 glossary, project log, progress
```

## Tests and rebuilding
```bash
python -m pytest tests -q
python scripts/make_demo_input.py      # rebuild data/demo_input.xlsx from the sized, sourced values
python scripts/make_glossary_pdf.py    # rebuild docs/GreenLCC_Glossary.pdf
python scripts/make_dummy_data.py      # regenerate the sample quote PDFs
python scripts/build_exe.py            # build dist/GreenLCC/GreenLCC.exe and dist/GreenLCC_Windows.zip (needs requirements-build.txt)
python scripts/update_log_index.py     # refresh the index at the top of docs/PROJECT_LOG.md
```

## Team
Built by a five-member student team for CM 617: project lead and finance, AI and tool development, data, documentation, and validation.
