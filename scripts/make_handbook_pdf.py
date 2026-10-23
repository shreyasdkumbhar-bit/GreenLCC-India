"""Build GreenLCC_Team_Handbook.pdf: a 6-page, plain-language explanation of the tool for teammates.

Every number is computed live from the engine, so the handbook cannot drift from the tool.
Run:  python scripts/make_handbook_pdf.py [output.pdf]
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer  # noqa: E402

from core import cashflow, igbc, optimizer, report, risk  # noqa: E402
from core.exports import DEEP, GREEN, GRID, INK, INK2, MINT, grid_table, safe, styles  # noqa: E402
from core.finance import crf  # noqa: E402
from core.io import load_dataset  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else (ROOT / "docs" if (ROOT / "docs" / "PROJECT_LOG.md").exists() else ROOT.parent) / "GreenLCC_Team_Handbook.pdf"
W = A4[0] - 32 * mm
st = styles()
st["body"].fontSize, st["body"].leading, st["body"].spaceAfter = 9.2, 12.6, 3.5
st["cell"].fontSize, st["cell"].leading = 7.9, 9.6
st["cellb"].fontSize, st["cellb"].leading = 7.9, 9.6
st["h2"].fontSize, st["h2"].spaceBefore, st["h2"].spaceAfter = 13, 4, 4
st["h3"].fontSize, st["h3"].spaceBefore, st["h3"].spaceAfter = 9.8, 5, 2
st["bullet"] = st["body"].clone("bullet", leftIndent=11, bulletIndent=1, spaceAfter=2, fontSize=8.8, leading=11.8)
st["formula"] = st["body"].clone("formula", fontName="Helvetica-Oblique", backColor=colors.HexColor(MINT), borderPadding=(3, 5, 3, 5),
                                 leftIndent=6, rightIndent=6, spaceBefore=3, spaceAfter=6, textColor=colors.HexColor(DEEP))

M = report.money


def _fmt(s: str) -> str:
    s = escape(safe(s)).replace("CO2", "CO<sub>2</sub>")
    for a, b in (("&lt;b&gt;", "<b>"), ("&lt;/b&gt;", "</b>"), ("&lt;i&gt;", "<i>"), ("&lt;/i&gt;", "</i>")):
        s = s.replace(a, b)
    return s


def P(text, style="body"):
    return Paragraph(_fmt(text), st[style])


def B(items):
    return [Paragraph(_fmt(i), st["bullet"], bulletText="•") for i in items]


# ---------------------------------------------------------------- live numbers
ds, errs = load_dataset()
assert not errs, errs
p = ds.project
n = p.study_period
df = optimizer.enumerate_portfolios(ds)
mev = optimizer.evaluate_measures(ds)
res = report.collect_results(ds, df, "Gold", "net_lcc", runs=5000)
rec, ch, mc, be = res["recommended"], res["cheapest_upfront"], res["monte_carlo"], res["break_even"]
rsel = optimizer.best(df, ds, "Gold", "net_lcc")["selection"]
feasible_gold = len(optimizer.feasible(df, ds, "Gold"))

# worked example: 100 kWp solar
pv = ds.measure("PV_100")
pvm = mev["PV_100"]
S = pvm.streams
repl_years = [(t, S.repl[t]) for t in range(n + 1) if S.repl[t] > 0]
resid_val = S.resid[n]
gen_kwh = pv.kwp * p.pv_yield_kwh_per_kwp
blend = p.pv_self_consumption * p.grid_tariff + (1 - p.pv_self_consumption) * p.export_tariff
yr1_saving = gen_kwh * blend
CRF = crf(p.discount_rate, n)
eac_pv = pvm.lcc * CRF

# worked example: IGBC scoring on the recommended portfolio
sc = igbc.score(ds, [ds.measure(i) for i in rsel])
mt = sc.metrics
pts = sc.breakdown.set_index("credit_id")["points"]
n_opt_groups = len(optimizer.groups(ds))
s_summary = cashflow.summarize(risk.portfolio_streams(ds, rsel), p)

resid_parts = []
for c in ds.comps_for("PV_100"):
    t_last = int((n - 1e-9) // c.life_years * c.life_years)
    frac = max(0.0, (t_last + c.life_years - n) / c.life_years)
    val = c.cost * (1 + p.inflation) ** t_last * frac
    if val > 0:
        resid_parts.append((c.component.lower(), t_last, frac, val))


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


# ---------------------------------------------------------------- drawings
def box(d, x, y, w, h, title, sub="", fill=MINT, stroke=GREEN, fg=DEEP, hot=False):
    d.add(Rect(x, y, w, h, rx=3, ry=3, fillColor=colors.HexColor(GREEN if hot else fill), strokeColor=colors.HexColor(stroke), strokeWidth=0.8))
    c = colors.white if hot else colors.HexColor(fg)
    d.add(String(x + 3, y + h - 8.5, title, fontName="Helvetica-Bold", fontSize=7.6, fillColor=c))
    if sub:
        d.add(String(x + 3, y + h - 17, sub, fontName="Helvetica", fontSize=6.5, fillColor=c))


def arrow(d, x1, y1, x2, y2):
    d.add(Line(x1, y1, x2, y2, strokeColor=colors.HexColor(INK2), strokeWidth=1.1))
    d.add(Polygon([x2, y2, x2 - 4, y2 + 2.4, x2 - 4, y2 - 2.4], fillColor=colors.HexColor(INK2), strokeColor=colors.HexColor(INK2)))


def flow() -> Drawing:
    h = 122
    d = Drawing(W, h)
    cw = (W - 2 * 14 * mm) / 3
    xs = [0, cw + 14 * mm, 2 * (cw + 14 * mm)]
    d.add(String(xs[0], h - 7, "WHAT GOES IN", fontName="Helvetica-Bold", fontSize=7.2, fillColor=colors.HexColor(INK2)))
    d.add(String(xs[1], h - 7, "WHAT THE TOOL DOES", fontName="Helvetica-Bold", fontSize=7.2, fillColor=colors.HexColor(INK2)))
    d.add(String(xs[2], h - 7, "WHAT COMES OUT", fontName="Helvetica-Bold", fontSize=7.2, fillColor=colors.HexColor(INK2)))
    ins = [("Project settings", "building, tariffs, target"), ("Measure library", "what each option costs and saves"), ("Replacement parts", "inverters, compressors..."),
           ("IGBC credits and levels", "how points are earned"), ("Vendor quote PDFs", "read by AI, reviewed by you")]
    for i, (t, s) in enumerate(ins):
        box(d, xs[0], h - 22 - i * 24, cw, 20, t, s, fill="#FFFFFF", stroke="#C3C2B7")
    steps = [("1  Check the inputs", "bad rows reported in plain words"), ("2  Cost every measure", "over its whole life"), ("3  Score IGBC points", "credit by credit"),
             ("4  Find the best portfolio", "tests every legal combination"), ("5  Stress-test the answer", "break-even, Monte Carlo")]
    for i, (t, s) in enumerate(steps):
        box(d, xs[1], h - 22 - i * 24, cw, 20, t, s, hot=(i == 3))
    outs = [("4 screens, one verdict each", "answer first, charts below"), ("Decision report", "PDF, 6 pages"), ("Results workbook", "Excel, 10 sheets"),
            ("Project file", "reopen the setup later"), ("Owner memo", "on screen, copy button")]
    for i, (t, s) in enumerate(outs):
        box(d, xs[2], h - 22 - i * 24, cw, 20, t, s, fill="#FFFFFF", stroke="#C3C2B7")
    arrow(d, xs[0] + cw + 1, h / 2 - 2, xs[1] - 2, h / 2 - 2)
    arrow(d, xs[1] + cw + 1, h / 2 - 2, xs[2] - 2, h / 2 - 2)
    return d


# ---------------------------------------------------------------- page frame
def frame(canvas, doc):
    canvas.saveState()
    w, h = A4
    if doc.page > 1:
        canvas.setFillColor(colors.HexColor(DEEP))
        canvas.rect(0, h - 9 * mm, w, 9 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(16 * mm, h - 6 * mm, "Inside GreenLCC  ·  team handbook")
    canvas.setFillColor(colors.HexColor(INK2))
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(16 * mm, 8 * mm, "CM 617 · Topic 6 · illustrative prototype data")
    canvas.drawRightString(w - 16 * mm, 8 * mm, f"{doc.page} / 6")
    canvas.restoreState()


story = []

# ================================================================ PAGE 1: big picture
story += [
    P("Inside GreenLCC", "title"),
    P("A plain-language guide for the team: what goes in, how the numbers are made, what comes out, and why it matters", "sub"),
    P("The 30-second pitch", "h2"),
    P("Developers chase an IGBC rating (Silver, Gold, Platinum) and usually pick the green measures with the lowest <b>upfront price</b>. But a building is paid for over decades: "
      "electricity, maintenance, replacements. GreenLCC costs every measure over its <b>whole life</b>, works out which combination earns your target rating for the "
      "<b>least lifetime cost</b>, and shows how safe that answer is if tariffs and interest rates move."),
    Spacer(1, 3), flow(), Spacer(1, 4),
    P("One decision, traced end to end", "h2"),
    grid_table([
        ["Step", "What happens", "In the demo project"],
        ["Quote arrives", "A vendor PDF is read and turned into a measure (you review it first)", "SunRise Solar 100 kWp quote: Rs 44 L, maintenance Rs 0.8 L a year, inverter Rs 5 L every 12 years"],
        ["Costed", "Every measure gets a lifetime cost over 25 years", f"100 kWp solar: lifetime cost {M(pvm.lcc)} (negative = it pays for itself)"],
        ["Scored", "Each measure earns IGBC points through the credit tables", f"Recommended package reaches {rec['points']:g} points: {rec['level']}"],
        ["Optimised", f"All {len(df):,} legal combinations are compared", f"Cheapest-upfront Gold: {M(ch['capex'])} capex.  Recommended Gold: {M(rec['capex'])} capex"],
        ["Stress-tested", "Rates, tariffs and costs are varied thousands of times", f"Recommended route wins in {mc['p_recommended_beats_cheapest']*100:.0f}% of {mc['runs']:,} simulated futures"],
        ["Delivered", "One PDF report, one Excel workbook, one project file", f"About {M(res['lifetime_gain_vs_cheapest'])} better over {n} years for the same rating"],
    ], [W * .14, W * .38, W * .48], st),
    Spacer(1, 3),
    P("Inside this handbook", "h2"),
    grid_table([
        ["Page", "Read it to understand", "Page", "Read it to understand"],
        ["2  Input files", "What we feed the tool and who owns each file", "5  Significance", "What each result means, and what we must be honest about"],
        ["3  How it works", "The maths, step by step, with a worked example", "6  Cheat sheet", "Run it, find things, who owns what, fixing problems"],
        ["4  Reports", "Every chart and file, and the decision each supports", "", ""],
    ], [W * .14, W * .36, W * .14, W * .36], st),
    Spacer(1, 3),
    P("Everything shown in this handbook uses the <b>illustrative demo data</b> (a made-up Pune office). The method is real; the prices, tariffs and IGBC point tables are placeholders "
      "until we replace them with verified values (see page 5).", "small"),
    PageBreak(),
]

# ================================================================ PAGE 2: input files
story += [
    P("1. The input files", "h2"),
    P("Six inputs drive everything. The tool checks each one on loading; if anything is wrong it lists <b>every</b> problem in plain words, for example: "
      "<i>'measures.csv row 1: capex: Input should be greater than or equal to 0'</i>. Nothing is silently accepted."),
    grid_table([
        ["File", "What it holds", "Key fields, with the demo example", "Suggested owner", "Status"],
        ["project_demo.json", "One building and its money assumptions",
         f"Plot {p.plot_area_m2:,.0f} m², FSI {p.fsi}, roof {p.roof_area_m2:,.0f} m²; energy use {p.baseline_energy_kwh/1e6:.1f} M kWh/yr; tariff Rs {p.grid_tariff:g}/kWh rising {p.tariff_escalation*100:.0f}%/yr; "
         f"discount rate {p.discount_rate*100:.0f}%; {n}-year study; target {p.target_level}; {p.base_points:g} base points", "Finance lead, Data lead", "Dummy"],
        ["measures.csv", "The menu of green measures",
         "Per measure: capex, yearly maintenance, kWh or kL saved, IGBC credit, and an 'exclusive group' (options in a group are alternatives, e.g. VRF or chiller). "
         "VRF example: Rs 60 L extra cost, saves 72,000 kWh/yr", "Data lead", "Dummy"],
        ["components.csv", "Parts that must be re-bought",
         "Part, cost today, life in years. Examples: solar inverter Rs 5 L every 12 years; chiller overhaul Rs 30 L every 15 years", "Data lead", "Dummy"],
        ["igbc_credits.csv", "How each credit earns points",
         "Credit, category, maximum points, rule. 'Fixed' credits give set points; 'threshold' credits depend on the % saved (energy: 3%→1 pt, 6%→3, ... 18%→11). Mandatory flag for water", "Data lead, Documentation lead", "Illustrative: replace with IGBC guide"],
        ["igbc_levels.csv", "Points needed per level", "Certified 50, Silver 60, Gold 70, Platinum 80", "Data lead", "Illustrative"],
        ["sample_quotes/*.pdf", "Vendor quotations for the AI reader", "Three fictional quotes: solar 100 kWp, VRF 120 TR, low-e glazing 1,800 m²", "Tool developer", "Fictional"],
    ], [W * .17, W * .14, W * .40, W * .15, W * .14], st),
    P("Three ideas that make the inputs work", "h2"),
]
story += B([
    "<b>Costs are incremental to a code-minimum baseline.</b> We compare each measure with what you would build anyway. A VRF quote of Rs 1.92 Cr replaces split ACs worth Rs 1.32 Cr, so the measure "
    "enters the library at <b>Rs 60 L</b>. The quote importer has boxes for the baseline cost to subtract.",
    "<b>Exclusive groups stop nonsense combinations.</b> You can't install two HVAC systems or two solar sizes; the tool picks at most one per group. Solar must also fit the roof "
    f"({p.roof_area_m2:,.0f} m² at {p.pv_area_per_kwp_m2:g} m² per kWp = {p.roof_area_m2/p.pv_area_per_kwp_m2:.0f} kWp).",
    "<b>Quotes are drafts, not facts.</b> The AI (or an offline reader if there's no API key) pulls out vendor, price, maintenance and the replaceable part. "
    "A quote doesn't say how much energy a system saves, so <b>you</b> enter that, then review and approve before it joins the library.",
])
story += [
    P("What the tool refuses", "h3"),
    P("Negative costs or lives, a subsidy bigger than the price, a discount rate outside 0-30%, a credit name that doesn't exist, a replaceable part linked to a measure that isn't in the library, "
      "a target level that isn't in the levels file. All are listed together so you fix them in one pass."),
    PageBreak(),
]

# ================================================================ PAGE 3: how it works
story += [
    P("2. How the numbers are made", "h2"),
    P("Step A: life-cycle cost of one measure (worked example: 100 kWp rooftop solar)", "h3"),
    P("Money later is worth less than money now, so every future rupee is shrunk to today's value (its <b>present worth</b>) at the discount rate:"),
    P(f"Present worth  =  amount in year t  ÷  (1 + {p.discount_rate*100:.0f}%) to the power t", "formula"),
    P(f"Lifetime cost (LCC)  =  all costs  -  all savings, each at present worth, added up over {n} years", "formula"),
    grid_table([
        ["Piece", "How it is worked out", "Present worth"],
        ["Upfront capex", f"Paid in year 0: Rs {pv.capex/1e5:.1f} L", M(pvm.capex_pv)],
        ["Maintenance", f"Rs {pv.om_annual/1e5:.2f} L in year 1, growing {pv.om_escalation*100:.0f}% a year", M(pvm.om_pv)],
        ["Inverter replacement", "; ".join(f"year {t}: Rs {v/1e5:.1f} L" for t, v in repl_years) + f" (Rs 5 L today, inflated {p.inflation*100:.0f}%/yr)", M(pvm.repl_pv)],
        ["Residual value", f"Unused life is credited back at year {n}: " + "; ".join(f"{nm} bought in year {t}, {fr*100:.0f}% of its life left = Rs {v/1e5:.1f} L" for nm, t, fr, v in resid_parts)
                       + f" (total Rs {resid_val/1e5:.1f} L)", f"-{M(pvm.resid_pv)}"],
        ["Energy savings", f"{gen_kwh:,.0f} kWh a year; {p.pv_self_consumption*100:.0f}% used on site at Rs {p.grid_tariff:g}, {100-p.pv_self_consumption*100:.0f}% exported at Rs {p.export_tariff:g} "
                           f"= Rs {blend:.2f}/kWh, so Rs {yr1_saving/1e5:.1f} L in year 1; tariff +{p.tariff_escalation*100:.0f}%/yr, panels lose {pv.degradation*100:.1f}%/yr", f"-{M(pvm.energy_pv)}"],
        ["Lifetime cost (LCC)", "Capex + maintenance + replacements - residual - savings", M(pvm.lcc)],
    ], [W * .17, W * .65, W * .18], st),
    P(f"To compare options with different lives fairly, the LCC is spread into an equal yearly amount: <b>EAC = LCC × d ÷ (1 - (1+d)^-N) = LCC × {CRF:.4f}</b>. "
      f"For this solar system that is {M(eac_pv)} a year (negative = a yearly profit).", "body"),
    P("Step B: IGBC points", "h3"),
    P(f"Fixed credits add their points (LED lighting and controls: 3). Threshold credits look at the <b>whole portfolio</b>, so savings are never double counted. For the recommended package: "
      f"energy saved = {mt['eff_kwh']:,.0f} of {p.baseline_energy_kwh:,.0f} kWh = <b>{mt['energy_eff_pct']:.1f}%</b>, which clears the 12% step: <b>{pts['EE-C2']:g} points</b>. "
      f"Solar supplies {mt['energy_re_pct']:.1f}% of the remaining demand, clearing the 10% step: <b>{pts['EE-C3']:g} points</b>. "
      f"Add the {p.base_points:g} base points and the other credits to reach <b>{sc.total:g}</b>: level <b>{sc.level}</b>. Credits are capped at their maximum, and mandatory credits (water fixtures) must score above zero."),
    P("Step C: finding the best portfolio", "h3"),
    P(f"With one choice per group (or none) there are <b>{len(df):,}</b> combinations that fit the roof; <b>{feasible_gold:,}</b> reach Gold with all mandatory credits met. The tool tests them <i>all</i>, "
      f"so the winner is provably the best, not a guess. It ranks three ways: <b>cheapest upfront</b> (today's habit), <b>lowest lifetime cost</b>, and lowest lifetime cost <b>net of the extra-floor-area value</b> "
      f"the rating may unlock (assumed at Rs {p.far_net_value_per_m2:,.0f} per extra m², counted once). Result: cheapest-upfront Gold costs {M(ch['capex'])} and ends at {M(ch['net_lcc'])}; "
      f"the recommended Gold costs {M(rec['capex'])} and ends at {M(rec['net_lcc'])}."),
    P("Step D: how safe is the answer?", "h3"),
]
story += B([
    f"<b>Break-even:</b> the tool finds the exact value at which the two routes cost the same. Here the ranking flips only if the discount rate passes <b>{report.pct(be['discount'])}</b> "
    + ("or electricity prices <b>stop rising altogether</b>." if abs(be["tariff_escalation"]) < 0.0005 else
     f"or tariff escalation drops below <b>{report.pct(be['tariff_escalation'])}</b> a year."),
    "<b>Tornado:</b> change one assumption at a time by ±20% (or ±2 percentage points) and see how far the lifetime cost moves. Wide bars = verify that number first.",
    f"<b>Monte Carlo:</b> {mc['runs']:,} imagined futures with random tariff growth (average {p.tariff_escalation*100:.0f}%, spread {p.tariff_escalation_sd*100:.0f} points), discount rate (-2/+3 points), "
    "capex (-10%/+20%) and solar output (±7%). The share of futures in which the recommended route is cheaper is the win rate.",
])
story.append(PageBreak())

# ================================================================ PAGE 4: reports and outputs
story += [
    P("3. Every report and output, and what it is for", "h2"),
    P("On-screen reports (the web app)", "h3"),
    grid_table([
        ["Report", "Where", "What it shows", "Decision it supports"],
        ["Answer card", "Home", "The headline in one sentence as soon as a project is loaded", "Is it worth reading further?"],
        ["Tariff path", "1 Set up", "Expected electricity price per year, with an uncertainty band", "Is our tariff assumption sensible?"],
        ["Verdict + cost build-up", "2 Recommendation", "Spend X more, save Y; capex, maintenance, replacements, residual and savings for both routes", "What does choosing on first cost really cost?"],
        ["Quick what-if", "2 Recommendation", "Two sliders (price growth, discount rate) re-cost both routes instantly", "Does the answer survive my own guess?"],
        ["Points vs cost; upgrade path", "2 Recommendation", "Every mix as a dot with the cheapest frontier; step-up cost between levels", "How much does each extra point cost? Is Platinum worth it?"],
        ["Credits earned", "2 Recommendation", "Points vs maximum, credit by credit, plus the mandatory-credit check", "Which credits are we missing?"],
        ["Compare measures", "2 Recommendation", "Lifetime cost, cost per year and payback of up to 5 options; carbon cost curve", "Which single option is cheapest to own?"],
        ["Win rate + tipping points", "3 Can we trust it?", "How often the recommendation wins; where it would flip; what matters most", "How much should we trust the answer?"],
    ], [W * .19, W * .15, W * .38, W * .28], st),
    P("Files you can download (Report page) - three, each for a different reader", "h3"),
    grid_table([
        ["File", "Format", "Contains", "Who uses it"],
        ["Decision report", "PDF, 6 pages", "1 answer and memo, 2 the two routes and cost build-up, 3 IGBC checklist with documents, 4 what to buy, 5 risk, 6 assumptions and yearly cash flow", "Owner, client, professor, IGBC consultant, tender team"],
        ["Results workbook", "Excel, 10 sheets", "Every number unrounded: summary, checklist, shortlist, cash flow, all Monte Carlo runs, top 200 portfolios, all inputs", "Finance lead, validation engineer"],
        ["Project file", "JSON", "Building, measures, parts and IGBC tables in one file; open it from Home to continue (tested round-trip)", "Whoever continues the work"],
    ], [W * .17, W * .13, W * .45, W * .25], st),
    P("Version 1 had eleven downloads (six CSVs, a ZIP, a memo); they repeated what the PDF and Excel already hold, so they were folded in. "
      "The PDF and Excel always use the same deterministic numbers, so a printed report can be reproduced exactly.", "small"),
    PageBreak(),
]

# ================================================================ PAGE 5: significance, limits, glossary
story += [
    P("4. Why these results matter", "h2"),
    grid_table([
        ["Number", "The question it answers", "How to read it"],
        ["Lifetime cost (LCC)", "What does this package really cost to own?", "Negative = pays for itself over the study period. Smaller is better."],
        ["Equivalent annual cost (EAC)", "What is that per year, so options with different lives compare fairly?", "Same sign rule; use it when lives differ."],
        ["Cheapest upfront vs recommended", "Are we falling into the first-cost trap?", f"Same rating, but the recommended route is about {M(res['lifetime_gain_vs_cheapest'])} better over {n} years."],
        ["Break-even", "At what point would our recommendation stop being best?", "The farther the break-even is from today's assumption, the safer the answer."],
        ["Monte Carlo win rate", "How often does the recommendation win if the future is uncertain?", f"{mc['p_recommended_beats_cheapest']*100:.0f}% here. Above ~90% is robust; near 50% is a coin toss."],
        ["Payback, SIR, IRR", "How fast and how well does the money come back?", f"Recommended package: payback {s_summary['payback']:.1f} years, savings-to-investment {s_summary['sir']:.1f}, IRR {s_summary['irr']*100:.0f}%."],
        ["CO2 avoided and cost per tonne", "What carbon do we save, and at what price?", f"{rec['co2_tonnes']:,.0f} tonnes over {n} years for the recommended package."],
        ["IGBC checklist", "What must we document to claim each point?", "Turns the optimiser's answer into an action list for the rating consultant."],
    ], [W * .24, W * .38, W * .38], st),
    P("5. What we must be honest about", "h2"),
]
story += B([
    "<b>The data is illustrative.</b> Prices, tariffs, the IGBC point tables and the extra-floor-area bonus are placeholders. Open items: verify the Maharashtra FAR bonus (Q-001), get the real IGBC v4.0 "
    "point tables (Q-002), get the real commercial tariff and its history (Q-003). Until then the <i>method</i> is solid but the <i>conclusions</i> are a demonstration.",
    "<b>Savings simply add up.</b> In reality a better building envelope shrinks the benefit of efficient AC. A full energy simulation would refine this.",
    "<b>One tariff path and a fixed grid emission factor.</b> Real projects would use state tariff schedules and a falling emission factor.",
    "<b>The Claude-powered parts need an API key.</b> Without one, a built-in reader and a template do the job; the Claude paths are written but not yet tested live (Q-006).",
    "<b>Still to do:</b> look at every screen on the presentation display (Q-005) and build the independent Excel cross-check (Q-007).",
])
story += [
    P("Glossary", "h3"),
    grid_table([
        ["Term", "Meaning", "Term", "Meaning"],
        ["IGBC", "Indian Green Building Council; rates buildings Certified/Silver/Gold/Platinum", "FAR / FSI", "Floor area ratio / floor space index: how much you may build on the plot"],
        ["Present worth", "Future money expressed in today's rupees", "Discount rate", "How strongly we shrink future money; higher favours cheaper-upfront options"],
        ["Escalation", "Yearly rise in a price (tariff, maintenance)", "Residual value", "Worth of unused life left at the end of the study period"],
        ["Portfolio", "A set of measures chosen together", "Net-metering", "Rooftop solar exports surplus power and is credited by the utility"],
    ], [W * .12, W * .38, W * .12, W * .38], st),
    PageBreak(),
]

# ================================================================ PAGE 6: cheat sheet
story += [
    P("Cheat sheet", "h2"),
    P("Pin this page. Everything a teammate needs to run, find, check and rebuild.", "sub"),
    P("Run it", "h3"),
]
story += B([
    "Open a terminal in the <b>greenlcc</b> folder and type <b>python -m streamlit run app.py</b>. The app opens in your browser (usually http://localhost:8501).",
    "Home page: click <b>Try the Pune demo</b>. Then follow the <b>Next</b> buttons: Set up, Recommendation, Can we trust it?, Report. Target level and the FAR switch are in the sidebar.",
    "Optional: set <b>ANTHROPIC_API_KEY</b> to let Claude read quotes and polish the memo. Without it everything still works.",
])
story += [
    P("Where things live", "h3"),
    grid_table([
        ["What", "Where", "Why you would open it"],
        ["Input files", "greenlcc / data", "Change a price, a credit table, a measure, the target level"],
        ["Sample quotes", "greenlcc / sample_quotes", "Try the AI quote reader"],
        ["Progress log", "PROJECT_LOG.md (work folder)", "Decisions D-, what worked W-, what didn't X-, open questions Q- (has an index)"],
        ["User guide PDF", "GreenLCC_India_Guide.pdf", "For the professor and new users"],
        ["This handbook", "GreenLCC_Team_Handbook.pdf", "For the team"],
        ["Test results", "greenlcc / tests", f"{N_TESTS} automated checks; run them after any change"],
    ], [W * .2, W * .32, W * .48], st),
    P("Who owns what (by role)", "h3"),
    grid_table([
        ["Role", "Also known as", "Look after"],
        ["Finance lead", "Project lead, finance modeller", "Discount rate, inflation, tariff assumptions; the cost method in section 2"],
        ["Tool developer", "AI and tool developer", "The app, quote reader, memo writer, exports"],
        ["Data lead", "Data lead", "All files in data/; verifying prices, tariffs, IGBC tables and the FAR bonus (Q-001 to Q-003)"],
        ["Documentation lead", "Documentation and reflection", "PROJECT_LOG.md, both PDFs, the demo script"],
        ["Validation lead", "Validation engineer", "Independent Excel check of the cost maths (Q-007); review of test cases"],
    ], [W * .13, W * .27, W * .60], st),
    P("If something goes wrong", "h3"),
    grid_table([
        ["Symptom", "Likely cause and fix"],
        ["Red error list on loading or applying", "An input row is invalid. The message names the file, row and field; fix that and reload"],
        ["'Target not reachable'", "The library can't reach that level. The message says how many points are missing; add measures or choose a lower level"],
        ["Results look unrealistic", "Check measure costs are <b>incremental to baseline</b>, and units (kWh per year, not per month)"],
        ["Quote reading looks wrong", "The AI/offline reader only drafts. Correct the fields in the review form before adding"],
        ["Numbers differ from the PDFs", "Rebuild the PDFs after any data change: run the two document scripts (handbook and guide) in greenlcc/scripts"],
    ], [W * .3, W * .7], st),
    P("When you change the data: edit the file → reload the demo or reapply on the Set up page → check the Recommendation and risk pages → rebuild the PDFs → add a line to PROJECT_LOG.md.", "small"),
]

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                        title="Inside GreenLCC - team handbook", author="CM 617 team")
doc.build(story, onFirstPage=frame, onLaterPages=frame)
print("wrote", OUT)
