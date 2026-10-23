# GreenLCC India

**Reach your IGBC green-building target at the lowest life-cycle cost, with tariff risk measured.**

Most Indian projects pick green measures (solar, efficient air-conditioning, glazing, LED lighting, water fixtures) by lowest upfront price. GreenLCC costs every measure over the building's whole life, searches every legal combination for the cheapest-over-its-life way to reach Certified, Silver, Gold or Platinum, and tests how safe that answer is if electricity prices and interest rates change.

Built for **CM 617, Topic 6 (LCCA decision tool)**.

> **All data in `data/` and `sample_quotes/` is illustrative.** IGBC point tables, tariffs, prices and the FAR bonus are placeholders, not verified values. See `docs/PROJECT_LOG.md`, section 6.

## Documents
| | |
|---|---|
| [`docs/GreenLCC_User_Guide.pdf`](docs/GreenLCC_User_Guide.pdf) | How to install, run and use the tool, screen by screen, plus a 5-minute demo script |
| [`docs/GreenLCC_About.pdf`](docs/GreenLCC_About.pdf) | What the tool is, how it works, and every input file and column it reads |
| [`docs/PROJECT_LOG.md`](docs/PROJECT_LOG.md) | Indexed log of decisions, what worked, what didn't, and open questions |

## Quick start
```bash
pip install -r requirements.txt        # Python 3.10+; with NumPy 1.x also: pip install "pyarrow<22"
python -m streamlit run app.py         # opens http://localhost:8501
```
On Home, click **Try the Pune demo**, then follow the **Next** buttons.

Optional: set `ANTHROPIC_API_KEY` to let Claude read vendor-quote PDFs and polish the memo. Without it, a built-in parser and a template are used, so nothing breaks.

## How it flows
| Step | Screen | What you get |
|---|---|---|
| Home | Try the demo or open a saved project file | The answer in one sentence |
| 1 | Set up | Building and money assumptions, the measure library, AI quote import |
| 2 | Recommendation | Cheapest-upfront vs lowest-lifetime-cost route, cost build-up, quick what-if, upgrade path, measure comparison |
| 3 | Can we trust it? | Monte Carlo win rate, tipping points, sensitivity |
| 4 | Report | Decision report (PDF, 6 pages), results workbook (Excel), project file (JSON) |

The target IGBC level and the FAR switch are in the sidebar and apply to every screen.

## Inputs (`data/`)
| File | Describes |
|---|---|
| `project_demo.json` | The building: areas, energy and water use, tariffs, discount rate, IGBC target, FAR bonus |
| `measures.csv` | Green measures: cost over a code-minimum baseline, maintenance, savings, IGBC credit, exclusive group |
| `components.csv` | Parts re-bought during the study period (inverters, compressors) with cost and life |
| `igbc_credits.csv` | How each credit earns points (fixed, or thresholds on % saving) |
| `igbc_levels.csv` | Points needed for each level |

The About PDF lists every field and column with units and rules.

## Model in one paragraph
Each measure is costed against a code-minimum baseline: capex, plus O&M (escalating), plus component replacements (inflated), minus residual value, minus energy and water savings (tariff escalating, equipment degrading). All of it is discounted at *d* over *N* years: LCC = Σ (Cₜ − Sₜ)/(1+d)ᵗ, and EAC = LCC · CRF.

The optimizer enumerates every feasible portfolio and picks the one with the lowest objective. A portfolio is feasible when it has one option per exclusive group, its solar fits within the roof area, and it meets the mandatory credits.

Risk analysis covers:
- break-even values found by root finding
- a discount-rate sweep
- a tornado chart
- a seeded Monte Carlo on tariff escalation, discount rate, capex and solar yield

## Repository layout
```
app.py            entry point: navigation, sidebar controls
pages/            0_home, 1_setup, 2_recommendation, 3_trust, 4_report
core/             engine: finance, cashflow, igbc, optimizer, risk, carbon, extract, report, exports, charts, ui, state, io, schemas
data/             illustrative inputs
sample_quotes/    three illustrative vendor quotations (PDF)
tests/            pytest suite: hand-checked maths, IGBC, optimizer, risk, exports, every screen (AppTest)
scripts/          rebuild the docs PDFs, the sample quotes and the log index
docs/             user guide, about document, project log
```

## Tests and rebuilding
```bash
python -m pytest tests -q
python scripts/make_docs_pdfs.py       # rebuild docs/GreenLCC_User_Guide.pdf and docs/GreenLCC_About.pdf with live numbers
python scripts/make_dummy_data.py      # regenerate the sample quote PDFs
python scripts/update_log_index.py     # refresh the index at the top of docs/PROJECT_LOG.md
```

## Team
Built by a five-member student team for CM 617: project lead and finance, AI and tool development, data, documentation, and validation.
