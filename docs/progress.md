# Progress – v3 "simplify + align with CE 725"

> Working checklist for the v3 change set. Decisions and reasons live in `PROJECT_LOG.md` (D-022 to D-029, section 9);
> this file only tracks what is done and what is next. Tick a line when it is finished and tested.

**Goal:** a smaller, course-aligned tool. Every input is needed for the maths, every output is a CE 725 concept,
the demo data is realistic and sourced, and the tool starts with one double-click.

**Started:** 2026-10-29 · **Tests at start:** 60 passing · **Tests now:** 83 passing

## Checklist
- [x] 1. progress.md created, plan logged in PROJECT_LOG
- [x] 2. Course interest factors, IRR / incremental IRR / MIRR / sign-change helpers + textbook tests (Ch 3, 5, 6, 7, 8) — `core/finance.py`, `tests/test_course.py`
- [x] 3. Simplified data model (no FAR, no subsidy, no per-measure O&M escalation, no `kind`, components merged into measures)
- [x] 4. Realistic, sourced demo data + one Excel input workbook (download from Home, open from Home) — `scripts/make_demo_input.py`
- [x] 5. Optimizer, risk, UI labels and the 4 pages updated (course terms, incremental-return headline, cash flow diagram, factor hand-check)
- [x] 6. PDF report, Excel results and memo updated (visually checked: PDF rendered to images)
- [x] 7. Glossary PDF (47 terms: meaning, course link, relevance) — `docs/GreenLCC_Glossary.pdf`
- [ ] 8. One-click launcher: `launcher.py` + `Start_GreenLCC.bat` done and tested. `dist/GreenLCC/GreenLCC.exe` built; it starts the server and serves the page (HTTP 200). **Still to do: open it in a real browser and click through the pages** (headless checks could not confirm the pages render). First build placed `app.py` in the wrong folder; fixed in `scripts/build_exe.py` and in the existing bundle
- [x] 9. README, PROJECT_LOG (both copies), log index

## What changed for a user
| Before (v2) | Now (v3) |
|---|---|
| 5 input files (4 CSV + JSON) | 1 Excel workbook with units, meanings and sources |
| 28 project inputs incl. plot, FSI, FAR bonus, BUA | 19 inputs, each used by the maths |
| "Lifetime cost", "Cost per year", "₹ saved per ₹ spent", simple payback | Life-cycle cost (PW), EUAC, BCR, IRR/MIRR, discounted payback, incremental IRR vs MARR |
| Pareto and MACC charts, 4 break-evens | Cash flow diagram, factor hand-check, 3 break-evens |
| Start from a terminal | Double-click `GreenLCC.exe` or `Start_GreenLCC.bat` |

## Next
- Q-005: look at every page in a real browser (the Chrome extension was not connected on 2026-10-29)
- Q-011: rewrite or retire the v2 User Guide / About / handbook builders (they still describe FAR and CSV inputs)
- Q-012: verify the estimated demo values (tariff after the March 2026 MERC order, HVAC ₹/TR, water tariff)
- Commit and push v3 to GitHub when the team has reviewed it
