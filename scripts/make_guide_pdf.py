"""Build GreenLCC_India_Guide.pdf: problem, how to use, outputs and impact.

Numbers are computed live from the engine so the document cannot drift from the tool.
Run:  python scripts/make_guide_pdf.py [output.pdf]
"""
import sys
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reportlab.graphics.shapes import Drawing, Line, Rect, String  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer  # noqa: E402

from core import cashflow, exports, optimizer, report, risk  # noqa: E402
from core.exports import DEEP, GREEN, GRID, INK, INK2, MINT, grid_table, safe, styles  # noqa: E402
from core.io import load_dataset  # noqa: E402

def RoundRect(x, y, w, h, r, **kw):
    return Rect(x, y, w, h, rx=r, ry=r, **kw)


OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else (ROOT / "docs" if (ROOT / "docs" / "PROJECT_LOG.md").exists() else ROOT.parent) / "GreenLCC_India_Guide.pdf"
W = A4[0] - 36 * mm
st = styles()
st["bullet"] = st["body"].clone("bullet", leftIndent=12, bulletIndent=2, spaceAfter=3)


def P(text, style="body"):
    t = escape(safe(text)).replace("CO2", "CO<sub>2</sub>")
    for a, b in (("&lt;b&gt;", "<b>"), ("&lt;/b&gt;", "</b>"), ("&lt;i&gt;", "<i>"), ("&lt;/i&gt;", "</i>")):
        t = t.replace(a, b)
    return Paragraph(t, st[style])


def bullets(items):
    return [Paragraph(escape(safe(i)).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>").replace("CO2", "CO<sub>2</sub>"), st["bullet"], bulletText="•") for i in items]


# ---------- live numbers ----------
ds, errs = load_dataset()
assert not errs, errs
p = ds.project
df = optimizer.enumerate_portfolios(ds)
res = report.collect_results(ds, df, "Gold", "net_lcc", runs=5000)
rec, ch, mc, be = res["recommended"], res["cheapest_upfront"], res["monte_carlo"], res["break_even"]
rsel = optimizer.best(df, ds, "Gold", "net_lcc")["selection"]
summ = cashflow.summarize(risk.portfolio_streams(ds, rsel), p)
n_combos = len(df)
extra_pct = (rec["capex"] / ch["capex"] - 1) * 100


def count_tests() -> str:
    import re
    import subprocess

    try:
        out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", str(ROOT / "tests")], capture_output=True, text=True, timeout=120).stdout
        m = re.search(r"(\d+) tests? collected", out)
        return m.group(1) if m else "many"
    except Exception:
        return "many"


N_TESTS = count_tests()
M = report.money


# ---------- drawings ----------
def workflow() -> Drawing:
    steps = [("", "Home", "demo or saved project;\nanswer card"), ("1", "Set up", "building, money,\nmeasures, AI quotes"),
             ("2", "Recommendation", "cheapest lifetime\nroute to the level"), ("3", "Can we\ntrust it?", "win rate,\ntipping points"),
             ("4", "Report", "PDF, Excel,\nproject file")]
    d = Drawing(W, 30 * mm)
    gap = 4 * mm
    bw = (W - 4 * gap) / 5
    for i, (n, title, sub) in enumerate(steps):
        x = i * (bw + gap)
        hot = n == "2"
        d.add(RoundRect(x, 4 * mm, bw, 24 * mm, 3, fillColor=colors.HexColor(GREEN if hot else MINT), strokeColor=colors.HexColor(GREEN), strokeWidth=0.8))
        fg = colors.white if hot else colors.HexColor(DEEP)
        d.add(String(x + 3, 23 * mm, n, fontName="Helvetica-Bold", fontSize=11, fillColor=fg))
        for k, line in enumerate(title.split("\n")):
            d.add(String(x + 3, 17.5 * mm - k * 3.6 * mm, line, fontName="Helvetica-Bold", fontSize=8.6, fillColor=fg))
        for k, line in enumerate(sub.split("\n")):
            d.add(String(x + 3, 8.2 * mm - k * 3 * mm + (0 if title.count("\n") else 0), line, fontName="Helvetica", fontSize=7, fillColor=fg))
        if i < len(steps) - 1:
            d.add(Line(x + bw + 0.6 * mm, 16 * mm, x + bw + gap - 0.6 * mm, 16 * mm, strokeColor=colors.HexColor(INK2), strokeWidth=1))
    return d


def wireframe() -> Drawing:
    """Schematic of the Recommendation page (the centrepiece)."""
    h = 78 * mm
    d = Drawing(W, h)
    ink, soft = colors.HexColor(INK2), colors.HexColor(GRID)
    d.add(RoundRect(0, 0, W, h, 4, fillColor=colors.HexColor("#F7F8F5"), strokeColor=soft))
    d.add(Rect(0, 0, 34 * mm, h, fillColor=colors.HexColor("#EAF0EA"), strokeColor=soft))
    for i, t in enumerate(["GreenLCC India", "Home", "1 Set up", "2 Recommendation", "3 Can we trust it?", "4 Report", "", "Target [Gold]  FAR [on]"]):
        hot = t.startswith("2")
        if hot:
            d.add(RoundRect(2 * mm, h - (16 + i * 6.4) * mm, 30 * mm, 5.2 * mm, 2, fillColor=colors.HexColor(MINT), strokeColor=colors.HexColor(GREEN)))
        d.add(String(4 * mm, h - (14.4 + i * 6.4) * mm, t, fontName="Helvetica-Bold" if (i == 0 or hot) else "Helvetica", fontSize=6.4, fillColor=colors.HexColor(DEEP) if hot else ink))
    d.add(RoundRect(2 * mm, 2 * mm, 30 * mm, 11 * mm, 2, fillColor=colors.white, strokeColor=soft))
    d.add(String(4 * mm, 9 * mm, "Gold - 74 pts OK", fontName="Helvetica-Bold", fontSize=6, fillColor=colors.HexColor("#006300")))
    d.add(String(4 * mm, 5 * mm, "Lifetime / upfront cost", fontName="Helvetica", fontSize=5, fillColor=ink))
    x0 = 38 * mm
    d.add(String(x0, h - 6 * mm, "THE ANSWER: Spend Rs 1.1 Cr more upfront, save Rs 82 L over 25 years", fontName="Helvetica", fontSize=6.6, fillColor=ink))
    kw = (W - x0 - 4 * mm - 4 * 2 * mm) / 5
    for i, (a, b) in enumerate([("IGBC result", "Gold 74"), ("Lifetime cost", "-Rs 3.7 Cr"), ("Better by", "Rs 0.8 Cr"), ("Upfront cost", "Rs 2.8 Cr"), ("CO2 avoided", "7,400 t")]):
        x = x0 + i * (kw + 2 * mm)
        d.add(RoundRect(x, h - 22 * mm, kw, 12 * mm, 2, fillColor=colors.white, strokeColor=soft))
        d.add(String(x + 2, h - 14.5 * mm, a, fontName="Helvetica", fontSize=5.4, fillColor=ink))
        d.add(String(x + 2, h - 19.5 * mm, b, fontName="Helvetica-Bold", fontSize=8, fillColor=colors.HexColor(DEEP)))
    half = (W - x0 - 4 * mm - 2 * mm) / 2
    for i, (t, col) in enumerate([("Cheapest-upfront route", "#FDEEE8"), ("Recommended route", MINT)]):
        x = x0 + i * (half + 2 * mm)
        d.add(RoundRect(x, h - 36 * mm, half, 11 * mm, 2, fillColor=colors.white, strokeColor=soft))
        d.add(String(x + 2, h - 29 * mm, t, fontName="Helvetica-Bold", fontSize=6.4, fillColor=colors.HexColor(INK)))
        for k in range(3):
            d.add(RoundRect(x + 2 + k * 17 * mm, h - 34.5 * mm, 15 * mm, 3.6 * mm, 1.8, fillColor=colors.HexColor(col), strokeColor=soft))
    d.add(RoundRect(x0, 9 * mm, W - x0 - 4 * mm, h - 48 * mm, 2, fillColor=colors.white, strokeColor=soft))
    d.add(String(x0 + 3, h - 44 * mm, "Where the lifetime cost comes from, then a Quick what-if (price growth, discount rate)", fontName="Helvetica", fontSize=6, fillColor=ink))
    for i, (hh, c) in enumerate([(14, "#2A78D6"), (7, "#EB6834"), (4, "#1BAF7A")]):
        d.add(Rect(x0 + 18 * mm + i * 4 * mm, 14 * mm, 3.2 * mm, hh * 0.6 * mm, fillColor=colors.HexColor(c), strokeColor=colors.white))
        d.add(Rect(x0 + 70 * mm + i * 4 * mm, 14 * mm, 3.2 * mm, (hh + 4) * 0.6 * mm, fillColor=colors.HexColor(c), strokeColor=colors.white))
    d.add(Rect(x0 + 18 * mm, 6 * mm, 14 * mm, 7 * mm, fillColor=colors.HexColor("#E87BA4"), strokeColor=colors.white))
    d.add(Rect(x0 + 70 * mm, 6 * mm, 14 * mm, 11 * mm, fillColor=colors.HexColor("#E87BA4"), strokeColor=colors.white))
    for i, t in enumerate(["Other options", "Points vs cost", "Credits earned", "Upgrade path", "Compare measures"]):
        d.add(String(x0 + i * 26 * mm, 3 * mm, t, fontName="Helvetica", fontSize=6, fillColor=ink))
    return d


def footer(canvas, doc):
    if doc.page == 1:
        return
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor(INK2))
    canvas.drawString(18 * mm, 10 * mm, "GreenLCC India - guide - illustrative prototype data")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def cover(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(colors.HexColor(DEEP))
    canvas.rect(0, h * 0.42, w, h * 0.58, stroke=0, fill=1)
    canvas.setFillColor(colors.HexColor(GREEN))
    canvas.rect(0, h * 0.42, w, 6 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 10)
    canvas.drawString(22 * mm, h - 28 * mm, "CM 617  ·  TOPIC 6  ·  LIFE CYCLE COST ANALYSIS DECISION TOOL")
    canvas.setFont("Helvetica-Bold", 38)
    canvas.drawString(22 * mm, h - 70 * mm, "GreenLCC India")
    canvas.setFont("Helvetica", 16)
    for i, line in enumerate(["Reach your IGBC target at the lowest", "life-cycle cost, with tariff risk measured."]):
        canvas.drawString(22 * mm, h - 86 * mm - i * 8 * mm, line)
    canvas.setFont("Helvetica", 10)
    canvas.drawString(22 * mm, h - 118 * mm, "What problem it solves  ·  how to use it  ·  what it delivers  ·  its impact")
    canvas.setFillColor(colors.HexColor(INK))
    canvas.setFont("Helvetica-Bold", 10.5)
    canvas.drawString(22 * mm, h * 0.42 - 16 * mm, "Team")
    canvas.setFont("Helvetica", 10)
    for i, t in enumerate(["Project Lead and Finance Modeller", "AI and Tool Developer", "Data Lead",
                           "Documentation and Reflection Lead", "Validation Engineer"]):
        canvas.drawString(22 * mm, h * 0.42 - 24 * mm - i * 6 * mm, t)
    canvas.setFillColor(colors.HexColor(INK2))
    canvas.setFont("Helvetica", 8.5)
    canvas.drawString(22 * mm, 16 * mm, f"Prototype v1  ·  {date.today():%d %B %Y}  ·  All data in the demo is illustrative.")
    canvas.restoreState()


S = [Spacer(1, 1)]
S.append(PageBreak())

# ---------- 1. problem ----------
S += [P("1. The problem", "h2"),
      P("Indian developers chase an IGBC rating (Silver, Gold or Platinum) for marketing and for incentives such as extra floor area. To reach it they usually "
        "pick green measures by <b>lowest upfront price</b>. But a building lives for decades, and energy, maintenance, replacement and tariff changes over that life "
        "can far exceed the purchase price. Nobody sees the lifetime picture, so the cheapest route to a rating is rarely the cheapest route to <i>own</i>."),
      P("Four things make this hard today:", "h3")]
S += bullets([
    "<b>First-cost bias.</b> Indian studies put the green-building premium at roughly 2-17% (up to 32% in some samples), and that perceived premium is a main barrier to adoption, "
    "even though one review reports lifetime savings above 20% of construction cost.",
    "<b>Uncertain, rising tariffs.</b> Commercial tariffs keep changing; in Maharashtra the surplus rooftop-solar credit for FY25-26 was set at Rs 2.82/kWh, and new multi-year "
    "tariff orders are expected to cut C&I solar savings. A single 'payback = 5 years' number hides that risk.",
    "<b>Cooling demand is exploding.</b> Buildings use about a third of India's electricity (heading toward 55% by 2047) and the India Cooling Action Plan projects building cooling "
    "demand growing roughly 11 times between 2018 and 2038. HVAC choices made on price alone lock in decades of power bills.",
    "<b>Unequal lives and manual data.</b> Inverters, compressors and coatings need replacing at different times, which simple payback ignores, and vendor quotes arrive as PDFs that "
    "consultants retype into spreadsheets.",
])
S += [P("Who it is for", "h3"),
      P("Building owners and developers (primary), architects and MEP consultants justifying specifications, facility managers planning replacement budgets, procurement teams "
        "comparing bids on life-cycle cost, and sustainability consultants evaluating solar and efficiency options.")]

# ---------- 2. what it does ----------
S += [P("2. What GreenLCC does", "h2"),
      P("Every green measure (solar, HVAC, glazing, lighting, water systems, cool roof) is scored over a 25-year study period: capex, escalating maintenance, component "
        "replacements and unused life at the end, minus energy and water savings with tariff escalation. The optimizer then tests every legal combination of measures and "
        f"finds the one that earns your target IGBC level for the least lifetime cost, and shows what picking on first cost would have cost you. In the demo that is "
        f"{n_combos:,} portfolios, searched exhaustively, so the answer is provably optimal."),
      Spacer(1, 4), workflow(), Spacer(1, 2)]

# ---------- 3. interface ----------
S += [P("3. The interface, page by page", "h2"),
      P("Four steps after Home. The sidebar holds the two choices that drive everything (target level and whether to count FAR value) and always shows "
        "the current answer. Every page opens with a one-line verdict and ends with a <b>Next</b> button.")]
rows = [["Page", "What you see", "What you do", "You get"],
        ["Home", "Try the Pune demo or open a saved project file. Once loaded, an answer card shows the result straight away.", "Click <b>Try the Pune demo</b>.", "The headline in one sentence."],
        ["1 Set up", "Tabs: Building and money (form + tariff chart), Measures (editable library, replacement parts, IGBC tables), Import a vendor quote (AI).", "Edit and Apply; or read a quote PDF, review, add.", "All assumptions in one place."],
        ["2 Recommendation", "Verdict, KPI cards with plain names (hover for the textbook term), the two routes, cost breakdown chart, Quick what-if sliders; tabs: other options, points vs cost, credits earned, upgrade path, compare measures, how it's calculated.", "Read the verdict; move the what-if sliders; compare HVAC options.", "The measures to build and why."],
        ["3 Can we trust it?", "Verdict ('wins in x% of futures'), tipping-point cards, then tabs: simulated futures, what matters most (tornado), interest-rate sweep.", "Read where the answer would flip.", "Confidence, in one number."],
        ["4 Report", "Three download cards and the owner memo.", "Download the PDF (and Excel / project file if needed).", "Ready-to-use files (section 5)."]]
S.append(grid_table(rows, [W * .19, W * .38, W * .23, W * .2], st))
S += [Spacer(1, 6), KeepTogether([P("Schematic of the centrepiece page (step 2)", "h3"), wireframe()])]

# ---------- 4. how to use ----------
S += [PageBreak(), P("4. How to use it", "h2"), P("Quick start: the five-minute demo", "h3")]
S += bullets([
    "<b>Start the app:</b> open a terminal in the greenlcc folder and run <b>python -m streamlit run app.py</b>. It opens in your browser.",
    "<b>Home:</b> click <b>Try the Pune demo</b>. The answer card already shows the result; click <b>See why</b>.",
    "<b>1 Set up, Import a vendor quote:</b> choose <b>SunRise_Solar_100kWp_quote.pdf</b>, click <b>Extract fields</b>, check the draft, then "
    "<b>Add to library</b>. You always review before anything enters the model.",
    "<b>2 Recommendation:</b> read the verdict and the two routes, then drag the <b>Quick what-if</b> sliders. Open 'Compare measures' for VRF vs chiller. "
    "Switch the sidebar target to Platinum to see the answer change.",
    "<b>3 Can we trust it?:</b> read the win rate and the tipping points.",
    "<b>4 Report:</b> download the PDF decision report.",
])
S += [P("Using your own project", "h3")]
S += bullets([
    "<b>Set up, Building and money:</b> enter plot area, FSI, roof area, baseline energy and water use, tariffs and the discount rate. Percentages are typed as %.",
    "<b>Set up, Measures:</b> costs are <b>incremental to a code-minimum baseline</b>. A VRF row holds the VRF cost minus the split ACs it replaces. The quote importer has fields "
    "for the baseline cost to deduct.",
    "<b>Exclusive group:</b> measures sharing a group (for example HVAC or PV size) are alternatives; only one is ever chosen. Leave blank for independent measures.",
    "<b>Replacement parts:</b> list parts that need re-buying (inverter, compressor) with their life. Unused life at the end is credited back as residual value.",
    "<b>IGBC tables:</b> the point tables shipped with the demo are <b>illustrative</b>. Replace data/igbc_credits.csv and igbc_levels.csv with values from the official IGBC reference guide.",
    "<b>Errors:</b> every invalid row or inconsistent reference is listed in plain language; nothing silently breaks.",
    "<b>Save and continue later:</b> download the <b>project file</b> on the Report page and open it from Home next time.",
])
S += [P("How to read the key numbers", "h3")]
S.append(grid_table([
    ["Term", "Meaning"],
    ["Net life-cycle cost (LCC)", "Present worth of capex + maintenance + replacements - residual value - savings, against the code-minimum baseline. <b>Negative means the package pays for itself.</b>"],
    ["Equivalent annual cost (EAC)", "The LCC spread as an equal yearly amount, which lets options with different lives be compared fairly."],
    ["Cheapest upfront vs recommended", "The first is what choosing credits on price gives you; the second minimises lifetime cost (or lifetime cost net of the FAR value) for the same level."],
    ["Break-even", "The discount rate, tariff escalation, tariff or capex level at which the two routes cost the same. Beyond it, the ranking flips."],
    ["Monte Carlo win rate", "Share of thousands of simulated futures (uncertain tariff escalation, discount rate, capex, solar yield) in which the recommended route is cheaper."],
    ["SIR / IRR / payback", "Savings-to-investment ratio, internal rate of return and years to recover the investment, simple and discounted."],
], [W * .27, W * .73], st))

# ---------- 5. outputs ----------
S += [PageBreak(), P("5. Ready-to-use outputs", "h2"),
      P("Three files, each for a different reader, all built from the numbers on screen. (Version 1 offered eleven downloads; most repeated each other.)")]
S.append(grid_table([
    ["File", "Format", "Use it for"],
    ["Decision report", "PDF, 6 pages", "The one document to forward: 1 the answer and memo, 2 the two routes and where the cost comes from, 3 IGBC credit checklist with "
     "documents to submit, 4 what to buy, 5 the risk check, 6 assumptions and the yearly cash flow."],
    ["Results workbook", "Excel, 10 sheets", "Every number unrounded for whoever checks the maths: summary, checklist, procurement shortlist, yearly cash flow, all "
     "Monte Carlo runs, top 200 portfolios and every input."],
    ["Project file", "JSON", "Building, measures, parts and IGBC tables in one file. Open it from Home to continue exactly where you left off (tested round-trip)."],
], [W * .2, W * .15, W * .65], st))
S.append(P("The owner memo is shown on the Report page with a copy button; it can be polished by Claude when an API key is set, which is never allowed to change a number.", "small"))

# ---------- 6. impact ----------
S += [P("6. Impact", "h2"),
      P("What the demo project shows (illustrative inputs; Gold target; 8% discount rate; 25 years):", "h3")]
S.append(grid_table([
    ["", "Cheapest upfront route", "Recommended route"],
    ["Upfront capex", M(ch["capex"]), f"{M(rec['capex'])} ({extra_pct:+.0f}%)"],
    ["Net life-cycle cost", M(ch["net_lcc"]), M(rec["net_lcc"])],
    ["IGBC result", f"{ch['level']} ({ch['points']:g} pts)", f"{rec['level']} ({rec['points']:g} pts)"],
    ["CO2 avoided over 25 years", f"{ch['co2_tonnes']:,.0f} t", f"{rec['co2_tonnes']:,.0f} t"],
], [W * .3, W * .35, W * .35], st))
S += [Spacer(1, 5),
      P(f"Spending {M(res['extra_capex'])} more upfront buys a lifetime outcome that is <b>{M(res['lifetime_gain_vs_cheapest'])} better</b> for the same rating, and avoids about "
        f"{rec['co2_tonnes'] - ch['co2_tonnes']:,.0f} t more CO2. The recommended package pays back in about {summ['payback']:.1f} years (simple) with an IRR of {summ['irr']*100:.0f}%. "
        f"It beats the cheapest-upfront route in <b>{mc['p_recommended_beats_cheapest']*100:.0f}%</b> of {mc['runs']:,} simulated futures, and the ranking only flips if the discount rate "
        f"exceeds {report.pct(be['discount'])} or tariff escalation falls below {report.pct(be['tariff_escalation'])}. The IGBC rating may also unlock extra floor area, valued at "
        f"{M(rec['far_benefit'])} on an assumed basis that must be verified locally.")]
S += [P("Why it matters beyond one project", "h3")]
S += bullets([
    "<b>Better decisions at the moment they are made.</b> The first-cost trap is invisible on a quotation but visible in a life-cycle view; the tool puts both side by side.",
    "<b>Risk becomes a number.</b> Instead of 'payback 5 years', an owner sees the range of outcomes and the exact assumptions that would change the answer.",
    "<b>Less manual rework.</b> Reading vendor quotes into the model removes retyping; the time saved has not been measured yet and is not claimed here.",
    "<b>Carbon alongside cost.</b> Each measure carries tonnes avoided and rupees per tonne, so efficiency and solar can be justified on both money and emissions.",
    "<b>Policy-aware.</b> The model is built around IGBC levels, ECBC-style baselines and Indian tariff structures, and the incentive value can be switched on or off.",
])

# ---------- 7. under the hood ----------
S += [P("7. How it works and how it was checked", "h2"),
      P("Cash flows are nominal rupees. Base prices are year-1 prices and escalate from year 2; replacement costs are today's prices inflated to the replacement year; residual value is the "
        "last purchase cost times the remaining-life fraction at the end of the study period. LCC = sum over t of (cost - saving) / (1 + d)^t, and EAC = LCC x d / (1 - (1 + d)^-N). "
        "IGBC points come from table-driven credits: fixed credits add their points, threshold credits (energy, renewables, water) are scored on the combined savings so nothing is double counted. "
        "The optimizer picks at most one option per exclusive group, requires mandatory credits and a roof that fits the solar, and enumerates all combinations. Risk uses a discount sweep, root-finding "
        "for break-even points, a one-at-a-time tornado, and a seeded Monte Carlo."),
      P(f"Checks: {N_TESTS} automated tests covering hand-calculated annuity, replacement, residual, escalation and degradation cases; vectorised results equal to scalar results; IGBC thresholds and caps; "
        "optimizer optimality, exclusivity, roof limit and infeasible targets; bad input files; and every page of the interface rendering with and without a project. "
        "The exported PDF, Excel and project files are tested for completeness and for agreeing with the engine.")]

# ---------- 8. limits ----------
S += [P("8. Limits and next steps", "h2")]
S += bullets([
    "<b>Illustrative data.</b> Prices, tariffs, the IGBC point tables and the FAR bonus are placeholders. Replace them with verified values before any real decision; the model itself is table-driven.",
    "<b>Additive savings.</b> Measures do not interact in the model; a full energy simulation would refine overlapping savings.",
    "<b>Constant emission factor</b> and a single tariff path; a real project would use state tariff schedules and a falling grid emission factor.",
    "<b>AI paths need an API key.</b> Quote extraction and memo polishing use Claude when ANTHROPIC_API_KEY is set; otherwise a deterministic parser and template are used.",
    "<b>Not yet done:</b> a visual review of every screen on the presentation display, and an Excel cross-check sheet by the Validation Engineer.",
    "<b>Next:</b> real IGBC v4 tables, state tariff data, a GRIHA option, battery storage, and a BOQ importer.",
])

# ---------- 9. sources ----------
S += [P("Sources", "h2"),
      P("Facts quoted in section 1 come from the following; several are secondary sources and should be verified before formal use.", "small")]
src = [
    "Green building cost premium in India and life-cycle cost studies: researchsquare.com/article/rs-1498374/v1; teriin.org/project/life-cycle-cost-energy-efficient-buildings",
    "ECBC 2017 rollout, 2-3% cost premium, life-cycle basis: files.acquia.undp.org/public/migration/in/Rolling-out-ECBC-Codes.pdf",
    "MERC rooftop solar tariff Rs 2.82/kWh FY25-26: solarquarter.com (April 2025 article on MERC rooftop solar tariff)",
    "Buildings' electricity share and cooling demand: pmc.ncbi.nlm.nih.gov/articles/PMC9360156; iea.org (Energy Efficiency 2023, India cooling); PRS India draft India Cooling Action Plan release",
    "IGBC Green New Buildings rating and v4.0 transition: igbc.in/igbcgreennewbuildings; simulationhub.com/blog/building-analysis-in-igbc",
    "State incentives for IGBC-rated projects: igbc.in/governmentincentivestoigbc; Maharashtra FAR figures from realtynmore.com (unverified)",
]
S += bullets(src)
for f in S:
    if hasattr(f, "style") and getattr(f.style, "name", "") == "bullet":
        f.style.fontSize = 9

OUT.parent.mkdir(parents=True, exist_ok=True)
doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                        title="GreenLCC India - guide", author="CM 617 team")
doc.build(S, onFirstPage=cover, onLaterPages=footer)
print("wrote", OUT)
