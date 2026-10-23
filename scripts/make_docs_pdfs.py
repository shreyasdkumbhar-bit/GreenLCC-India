"""Build the two repo documents in docs/ with live numbers from the engine:

  docs/GreenLCC_User_Guide.pdf   how to install, run and use the tool, screen by screen
  docs/GreenLCC_About.pdf        what the tool is, how it works, and every input file it takes

Run:  python scripts/make_docs_pdfs.py  [output_dir]
"""
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer  # noqa: E402

from core import optimizer, report  # noqa: E402
from core.exports import DEEP, GREEN, GRID, INK, INK2, MINT, grid_table, safe, styles  # noqa: E402
from core.io import load_dataset  # noqa: E402

OUT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs"
W = A4[0] - 36 * mm
st = styles()

# ------------------------------------------------------------------ live numbers
ds, errs = load_dataset()
assert not errs, errs
p = ds.project
df = optimizer.enumerate_portfolios(ds)
res = report.collect_results(ds, df, p.target_level, "net_lcc" if p.use_far_benefit else "lcc", runs=3000)
rec, ch, mc = res["recommended"], res["cheapest_upfront"], res["monte_carlo"]
M = report.money
TARGET, N = res["target"], p.study_period


def count_tests() -> str:
    try:
        out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", str(ROOT / "tests")],
                             capture_output=True, text=True, timeout=180, cwd=ROOT).stdout
        line = next(l for l in out.splitlines() if "tests collected" in l or "test collected" in l)
        return line.split()[0]
    except Exception:
        return "60+"


N_TESTS = count_tests()


def P(text: str, style: str = "body") -> Paragraph:
    t = safe(text).replace("CO2", "CO<sub>2</sub>")
    return Paragraph(t, st[style])


def B(items: list[str]) -> list:
    return [Paragraph(safe(f"&bull;&nbsp; {i}").replace("CO2", "CO<sub>2</sub>"), st["body"]) for i in items]


def T(rows: list[list], widths: list[float]):
    return grid_table(rows, [W * w for w in widths], st)


def frame(title: str):
    def draw(canvas, doc):
        canvas.saveState()
        w, h = A4
        canvas.setFillColor(colors.HexColor(DEEP))
        canvas.rect(0, h - 8 * mm, w, 8 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(18 * mm, h - 5.4 * mm, f"GreenLCC India  ·  {title}")
        canvas.setFillColor(colors.HexColor(INK2))
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(18 * mm, 9 * mm, "CM 617 · Topic 6 · prototype with illustrative data; verify prices, tariffs and IGBC tables before real decisions.")
        canvas.drawRightString(w - 18 * mm, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()
    return draw


def box(d, x, y, w, h, title, sub="", hot=False, fill=None):
    d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=colors.HexColor(GREEN if hot else (fill or MINT)),
               strokeColor=colors.HexColor(GREEN), strokeWidth=0.8))
    fg = colors.white if hot else colors.HexColor(DEEP)
    d.add(String(x + 5, y + h - 11, title, fontName="Helvetica-Bold", fontSize=8.2, fillColor=fg))
    for k, line in enumerate(sub.split("\n") if sub else []):
        d.add(String(x + 5, y + h - 21 - k * 8.5, line, fontName="Helvetica", fontSize=6.8, fillColor=fg))


def arrow(d, x1, y1, x2, y2):
    c = colors.HexColor(INK2)
    d.add(Line(x1, y1, x2 - 4, y2, strokeColor=c, strokeWidth=1))
    d.add(Polygon([x2, y2, x2 - 5, y2 + 3, x2 - 5, y2 - 3], fillColor=c, strokeColor=c))


def build(path: Path, title: str, story: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm, bottomMargin=17 * mm,
                            title=f"GreenLCC India - {title}", author="CM 617 team")
    doc.build(story, onFirstPage=frame(title), onLaterPages=frame(title))
    print(f"wrote {path}")


# ================================================================== USER GUIDE
def screen_map() -> Drawing:
    """The 5 screens in order, with what each one answers."""
    h = 34 * mm
    d = Drawing(W, h)
    gap = 5 * mm
    bw = (W - 4 * gap) / 5
    steps = [("Home", "demo or saved file;\nanswer card", False), ("1  Set up", "building, money,\nmeasures, AI quotes", False),
             ("2  Recommendation", "the answer and\nwhy it wins", True), ("3  Can we trust it?", "win rate and\ntipping points", False),
             ("4  Report", "PDF, Excel,\nproject file", False)]
    for i, (t, s, hot) in enumerate(steps):
        x = i * (bw + gap)
        box(d, x, 4 * mm, bw, 26 * mm, t, s, hot=hot)
        if i < 4:
            arrow(d, x + bw + 1, 17 * mm, x + bw + gap - 1, 17 * mm)
    return d


def screen_layout() -> Drawing:
    """Schematic of one screen: sidebar on the left, page on the right."""
    h = 70 * mm
    d = Drawing(W, h)
    soft, ink = colors.HexColor(GRID), colors.HexColor(INK2)
    d.add(Rect(0, 0, W, h, rx=4, ry=4, fillColor=colors.HexColor("#F7F8F5"), strokeColor=soft))
    sw = 40 * mm
    d.add(Rect(0, 0, sw, h, fillColor=colors.HexColor("#EAF0EA"), strokeColor=soft))
    labels = [("A", "Menu: Home and steps 1-4", h - 12 * mm), ("B", "Target IGBC level  [Gold v]", h - 36 * mm),
              ("C", "Count extra-FAR value  (on)", h - 44 * mm), ("D", "Status: Gold - 74 pts", h - 60 * mm)]
    for i, t in enumerate(["Home", "1 Set up", "2 Recommendation", "3 Can we trust it?", "4 Report"]):
        d.add(String(4 * mm, h - (8 + i * 3.6) * mm, t, fontName="Helvetica-Bold" if i == 2 else "Helvetica", fontSize=6.6,
                     fillColor=colors.HexColor(DEEP) if i == 2 else ink))
    d.add(Rect(2.5 * mm, h - 40 * mm, sw - 5 * mm, 13 * mm, rx=2, ry=2, fillColor=colors.white, strokeColor=soft))
    d.add(String(4 * mm, h - 32 * mm, "Target IGBC level  [Gold v]", fontName="Helvetica", fontSize=6.4, fillColor=ink))
    d.add(String(4 * mm, h - 37.5 * mm, "Count extra-FAR value  (on)", fontName="Helvetica", fontSize=6.4, fillColor=ink))
    d.add(Rect(2.5 * mm, 4 * mm, sw - 5 * mm, 13 * mm, rx=2, ry=2, fillColor=colors.white, strokeColor=soft))
    d.add(String(4 * mm, 12 * mm, "Gold - 74 pts OK", fontName="Helvetica-Bold", fontSize=6.6, fillColor=colors.HexColor("#006300")))
    d.add(String(4 * mm, 7.5 * mm, "Lifetime / upfront cost", fontName="Helvetica", fontSize=6, fillColor=ink))
    x0, mw = sw + 5 * mm, W - sw - 9 * mm
    d.add(Rect(x0, h - 9 * mm, 24 * mm, 5 * mm, rx=2.5, ry=2.5, fillColor=colors.HexColor(MINT), strokeColor=soft))
    d.add(String(x0 + 2 * mm, h - 7.5 * mm, "STEP 2 OF 4", fontName="Helvetica-Bold", fontSize=6, fillColor=colors.HexColor(DEEP)))
    d.add(Rect(x0, h - 23 * mm, mw, 12 * mm, rx=3, ry=3, fillColor=colors.HexColor(MINT), strokeColor=colors.HexColor("#BFDCCA")))
    d.add(String(x0 + 3 * mm, h - 15.5 * mm, "THE ANSWER", fontName="Helvetica-Bold", fontSize=5.8, fillColor=colors.HexColor(DEEP)))
    d.add(String(x0 + 3 * mm, h - 20.5 * mm, "Spend more upfront, save more over 25 years", fontName="Helvetica-Bold", fontSize=8, fillColor=colors.HexColor(INK)))
    kw = (mw - 4 * 2 * mm) / 5
    for i in range(5):
        d.add(Rect(x0 + i * (kw + 2 * mm), h - 36 * mm, kw, 10 * mm, rx=2, ry=2, fillColor=colors.white, strokeColor=soft))
        d.add(String(x0 + i * (kw + 2 * mm) + 2, h - 30 * mm, ["IGBC result", "Lifetime cost (i)", "Better by", "Upfront cost (i)", "CO2 avoided"][i],
                     fontName="Helvetica", fontSize=5.6, fillColor=ink))
    d.add(Rect(x0, 14 * mm, mw, h - 53 * mm, rx=2, ry=2, fillColor=colors.white, strokeColor=soft))
    d.add(String(x0 + 3 * mm, h - 43 * mm, "Charts and tabs, each with a one-line 'What this means'", fontName="Helvetica", fontSize=6.4, fillColor=ink))
    d.add(Rect(x0 + mw - 40 * mm, 4 * mm, 40 * mm, 7 * mm, rx=2, ry=2, fillColor=colors.white, strokeColor=colors.HexColor(GREEN)))
    d.add(String(x0 + mw - 38 * mm, 6.5 * mm, "Next: Check the risk ->", fontName="Helvetica-Bold", fontSize=6.4, fillColor=colors.HexColor(DEEP)))
    # callout letters
    marks = [("A", 30 * mm, h - 9 * mm), ("B", sw - 6 * mm, h - 30 * mm), ("C", sw - 6 * mm, h - 36 * mm), ("D", sw - 6 * mm, 13 * mm),
             ("E", x0 + mw - 5 * mm, h - 15 * mm), ("F", x0 + mw - 5 * mm, h - 29 * mm), ("G", x0 + mw - 5 * mm, h - 43 * mm), ("H", x0 + mw - 45 * mm, 6 * mm)]
    for t, x, y in marks:
        d.add(Rect(x, y, 4.2 * mm, 4.2 * mm, rx=2.1, ry=2.1, fillColor=colors.HexColor("#EB6834"), strokeColor=colors.white))
        d.add(String(x + 1.25 * mm, y + 1.2 * mm, t, fontName="Helvetica-Bold", fontSize=6.6, fillColor=colors.white))
    return d


def user_guide() -> list:
    s = [P("GreenLCC India: User Guide", "title"),
         P(f"How to install, run and use the tool, screen by screen. Version 2 · {date.today():%d %b %Y}", "sub"),
         P("GreenLCC finds the cheapest way, <b>over the whole life of a building</b>, to reach an IGBC green rating (Certified, Silver, Gold or Platinum), "
           "and shows how safe that answer is if electricity prices and interest rates change. This guide is for anyone using it: the team, the professor, "
           "or a building owner. For what the tool is and the input files it reads, see the companion document <b>GreenLCC_About.pdf</b>."),
         T([["Section", "Read it when you want to"],
            ["1  Install and start", "get the app running on your computer"],
            ["2  The screen at a glance", "know what every part of the screen does"],
            ["3  Screen by screen", "know what each page shows and what to click"],
            ["4  A five-minute demo", "present the tool, step by step"],
            ["5  Using your own project", "replace the demo with a real building"],
            ["6  Reading the results", "understand the numbers and words on screen"],
            ["7  Problems and fixes", "something looks wrong"]], [.32, .68]),
         P("1  Install and start", "h2")]
    s += B(["You need <b>Python 3.10 or newer</b>. Open a terminal in the project folder (the one with app.py).",
            "Install the libraries once: <b>pip install -r requirements.txt</b>. If pip complains about pyarrow and NumPy 1.x, run <b>pip install \"pyarrow&lt;22\"</b>.",
            "Start the app: <b>python -m streamlit run app.py</b>. Your browser opens at <b>http://localhost:8501</b>. Keep the terminal open while you use it; "
            "press Ctrl+C there to stop.",
            "Optional: set an <b>ANTHROPIC_API_KEY</b> environment variable to let Claude read vendor quotes and polish the memo. Without it, a built-in reader "
            "and a template do the same jobs, so nothing breaks.",
            f"Optional check: <b>python -m pytest tests -q</b> runs the {N_TESTS} automated tests (maths, IGBC scoring, optimiser, risk, exports, every screen)."])
    s += [PageBreak(), P("2  The screen at a glance", "h2"),
          P("Every page has the same layout. The letters match the picture below."),
          screen_layout(), Spacer(1, 4),
          T([["", "Part", "What it does"],
             ["A", "Menu", "Home and the four steps. You can jump anywhere, but the steps are meant to be read in order."],
             ["B", "Target IGBC level", "The rating you are aiming for. It applies to every page and to the report."],
             ["C", "Count extra-FAR value", "Some states give extra buildable floor area for a rating. When on, its value is subtracted from lifetime cost."],
             ["D", "Status box", "Always shows the level reached, points, lifetime cost and upfront cost of the recommendation."],
             ["E", "The answer", "One sentence at the top of each page that says what the page found."],
             ["F", "Number cards", "Key figures. Hover the (i) to see the textbook term and how it is calculated."],
             ["G", "Charts and tabs", "The detail. Each chart has a short 'What this means' line under it."],
             ["H", "Next button", "Takes you to the next step, so you never need the menu during a demo."]], [.05, .25, .70])]

    # 3 screen by screen
    s += [P("3  Screen by screen", "h2"), screen_map(), Spacer(1, 4)]
    pages = [
        ("Home", "A short pitch, two ways to start, and why the tool exists.",
         ["Click <b>Try the Pune demo</b> to load a ready-made office building, or use <b>Open a saved project</b> to load a file you saved earlier.",
          "As soon as a project is loaded, the <b>answer card</b> shows the headline result. Click <b>See why</b> to go straight to the recommendation."]),
        ("1  Set up", "Three tabs holding every assumption.",
         ["<b>Building & money:</b> plot, floor and roof areas, yearly energy and water use, the electricity tariff and how fast it rises, the discount rate, "
          "solar yield, and the FAR bonus values. Change anything and press <b>Apply changes</b>. Wrong values are explained, never silently accepted.",
          "<b>Measures:</b> the menu of green options (solar sizes, air-conditioning types, glazing, lighting, water fixtures...). Edit cells in the table, "
          "then press <b>Apply measure changes</b>. Expand <b>Replacement parts</b> to edit what must be re-bought and when; "
          "<b>IGBC credit tables</b> shows how points are earned.",
          "<b>Import a vendor quote (AI):</b> pick a sample quote or upload a PDF, press <b>Extract fields</b>, check the draft (price, maintenance, parts), "
          "fill in the engineering inputs a quote doesn't state (energy saved, credit), then <b>Add to library</b>. Nothing is added without your review."]),
        ("2  Recommendation  (the main screen)", "The answer, the two routes, and the evidence.",
         ["Read the <b>answer</b> at the top: how much more you spend upfront and how much you save over the building's life.",
          "Compare the two route cards: <b>Cheapest upfront</b> (what most projects do today) and <b>Recommended</b> (lowest lifetime cost). "
          "The bar chart shows where the money goes: equipment, maintenance, replacements, leftover value and savings.",
          "Use <b>Quick what-if</b>: drag electricity price growth or the discount rate and see instantly whether the recommendation still wins.",
          "Tabs: <b>Other options</b> (the 10 best mixes), <b>Points vs cost</b>, <b>Credits earned</b>, <b>Upgrade path</b> (cost of going up a level), "
          "<b>Compare measures</b> (e.g. VRF vs chiller, with payback and carbon), and <b>How it's calculated</b>.",
          "If the target can't be reached, the page says how many points are missing and offers a <b>Switch target</b> button."]),
        ("3  Can we trust it?", "How robust the answer is.",
         ["The answer line gives the <b>win rate</b>: in how many of thousands of simulated futures the recommendation is cheaper.",
          "<b>Tipping points</b> show the discount rate, tariff growth, tariff level and equipment price at which the ranking would flip. The further from today's value, the safer.",
          "Tabs: <b>Simulated futures</b> (spread of outcomes for both routes), <b>What matters most</b> (which assumption moves the answer most), "
          "<b>Interest-rate sweep</b>. Simulation runs and the random seed are under <b>Advanced</b>."]),
        ("4  Report", "Three downloads and the owner memo.",
         ["<b>Decision report (PDF, 6 pages)</b>: the document to send. It has the answer, the two routes, the IGBC credit checklist with documents to submit, "
          "what to buy, the risk check, and the assumptions with a yearly cash flow.",
          "<b>Results workbook (Excel)</b>: every number unrounded, for whoever checks the maths.",
          "<b>Project file (.json)</b>: your whole setup in one file. Open it from Home next time to carry on where you left off.",
          "The <b>owner memo</b> is shown below with a copy box. Switch on <b>Polish the wording with Claude</b> if an API key is set; it may reword but never change numbers."]),
    ]
    for title, sub, items in pages:
        s.append(KeepTogether([P(title, "h3"), P(f"<i>{sub}</i>", "small")] + B(items)))
    s.append(PageBreak())

    # 4 demo
    s += [P("4  A five-minute demo", "h2"),
          P("A script for presenting the tool. The numbers are from the illustrative Pune demo and will change if you edit the data.")]
    s.append(T([["#", "Do this", "Say this"],
                ["1", "Home: click <b>Try the Pune demo</b>.",
                 "Developers pick green credits on upfront price. We cost them over the building's whole life instead."],
                ["2", "1 Set up: <b>Import a vendor quote</b>, choose the SunRise solar quote, <b>Extract fields</b>, review, <b>Add to library</b>.",
                 "The quote is read automatically, but a person always checks it before it is used."],
                ["3", "2 Recommendation: read the answer and the two route cards.",
                 f"Both routes reach {TARGET}. The recommended one costs {M(res['extra_capex'])} more upfront but is "
                 f"{M(res['lifetime_gain_vs_cheapest'])} better over {N} years."],
                ["4", "Drag the <b>Quick what-if</b> sliders; open <b>Compare measures</b>.",
                 "Even with slower price growth it still wins. The cheaper-to-buy air-conditioning is not the cheaper-to-own one."],
                ["5", "Switch the sidebar target to <b>Platinum</b>, then back.", "The tool shows what the next level would cost over the building's life."],
                ["6", "3 Can we trust it?: read the win rate and the tipping points.",
                 f"The recommendation wins in {mc['p_recommended_beats_cheapest']*100:.0f}% of {mc['runs']:,} simulated futures."],
                ["7", "4 Report: download the PDF and open it.", "One document the owner, the IGBC consultant and the tender team can all use."]],
               [.05, .45, .50]))

    # 5 own project
    s += [P("5  Using your own project", "h2")]
    s += B(["<b>Start from the demo</b> and overwrite it: it is quicker than starting blank, and every field already has a sensible value.",
            "<b>Building & money first.</b> Enter areas, yearly energy and water use, today's tariff and its yearly growth, and your discount rate. Percentages are typed as %, e.g. 8 for 8%.",
            "<b>Then the measures.</b> Costs are <b>extra over a code-minimum baseline</b>: a VRF row holds the VRF price minus the split ACs it replaces. "
            "Energy saved is <b>kWh per year</b>. Solar rows use kWp instead of kWh; the tool works out the energy from the solar yield.",
            "<b>Exclusive group</b> marks alternatives: measures sharing a group (e.g. HVAC, PV) are never chosen together. Leave it blank for independent measures.",
            "<b>Replacement parts</b>: list anything re-bought during the study period (inverter, compressor) with its cost and life in years.",
            "<b>IGBC tables</b> shipped with the demo are illustrative. For real use, replace data/igbc_credits.csv and data/igbc_levels.csv with values from the official IGBC guide.",
            "<b>Save your work</b>: on 4 Report, download the <b>project file</b>. Next time, open it from Home. The app does not save automatically."])

    # 6 reading results
    s += [P("6  Reading the results", "h2"),
          T([["On screen", "Textbook term", "How to read it"],
             ["Lifetime cost", "Life-cycle cost (LCC)", "Everything paid minus everything saved over the study period, in today's money. <b>Negative = it pays for itself.</b>"],
             ["Lifetime cost after FAR value", "Net LCC", "Lifetime cost minus the value of the extra floor area the rating unlocks."],
             ["Cost per year", "Equivalent annual cost (EAC)", "Lifetime cost spread evenly per year; fair for comparing options with different lives."],
             ["Upfront cost", "Capex", "Extra money spent at the start, over the code-minimum baseline."],
             ["Rs saved per Rs spent", "Savings-to-investment ratio (SIR)", "Above 1 means the measure is worth doing."],
             ["Payback", "Simple payback", "Years until savings have repaid the extra cost."],
             ["Wins in x% of futures", "Monte Carlo probability", "Above about 90% is robust; near 50% is a coin toss."],
             ["Tipping point", "Break-even value", "The value at which the two routes cost the same. Further from today = safer."],
             ["CO2 avoided", "Lifetime emissions avoided", "kWh saved x grid emission factor, over the study period."]], [.24, .27, .49]),
          P("7  Problems and fixes", "h2"),
          T([["What you see", "What to do"],
             ["'No project loaded yet'", "Go to Home and click Try the Pune demo, or open a saved project file."],
             ["A red list of errors after Apply", "Each line names the field or row and the rule it breaks. Fix it and press Apply again."],
             ["'Target is not reachable'", "Click Switch target, choose a lower level in the sidebar, or add measures that earn more points."],
             ["Results look too good or too bad", "Check that measure costs are extra over baseline and that energy is per year, not per month."],
             ["The quote reader got a field wrong", "It only drafts. Correct the field in the review form before Add to library."],
             ["'Could not open that file' on Home", "Only project files saved from the Report page can be opened."],
             ["The page is slow the first time", "It is searching every combination and simulating thousands of futures; later clicks reuse the results."],
             ["Browser didn't open", "Open http://localhost:8501 yourself while the terminal is running."]], [.36, .64])]
    return s


# ================================================================== ABOUT
FIELD_INFO = {
    "name": ("Project name", "text", "shown on screens and reports"),
    "city": ("City", "text", ""),
    "building_type": ("Building type", "text", ""),
    "plot_area_m2": ("Plot area", "m2", "> 0"),
    "fsi": ("FSI / FAR allowed on the plot", "ratio", "> 0"),
    "bua_m2": ("Built-up area", "m2", "> 0"),
    "roof_area_m2": ("Usable roof area (limits solar size)", "m2", ">= 0"),
    "baseline_energy_kwh": ("Electricity use of the code-minimum building", "kWh / yr", "> 0"),
    "baseline_water_kl": ("Water use of the code-minimum building", "kL / yr", ">= 0"),
    "study_period": ("Years the costs are counted over", "years", "5 to 60"),
    "discount_rate": ("Discount rate (nominal)", "fraction", "0 to 0.30"),
    "inflation": ("General inflation (replacement prices)", "fraction", "0 to 0.20"),
    "grid_tariff": ("Electricity tariff in year 1", "Rs / kWh", "> 0"),
    "tariff_escalation": ("Yearly tariff growth", "fraction", "-0.05 to 0.20"),
    "tariff_escalation_sd": ("Uncertainty of that growth (1 sd)", "fraction", "0 to 0.10"),
    "export_tariff": ("Credit for solar exported to the grid", "Rs / kWh", ">= 0"),
    "export_escalation": ("Yearly growth of the export credit", "fraction", "optional"),
    "water_tariff": ("Water + sewage tariff", "Rs / kL", ">= 0"),
    "water_escalation": ("Yearly water tariff growth", "fraction", "optional"),
    "pv_yield_kwh_per_kwp": ("Solar output per kWp per year", "kWh / kWp", "> 0"),
    "pv_self_consumption": ("Share of solar used on site (rest exported)", "0 to 1", ""),
    "pv_area_per_kwp_m2": ("Roof area needed per kWp", "m2 / kWp", "optional"),
    "grid_emission_factor": ("Grid CO2 per MWh", "tCO2 / MWh", ">= 0"),
    "target_level": ("Default IGBC target", "level name", "must exist in igbc_levels.csv"),
    "base_points": ("Points the base design already earns", "points", ">= 0"),
    "far_bonus_pct": ("Extra FAR per level", "% by level", "levels must exist"),
    "far_net_value_per_m2": ("Net value of each extra m2 built", "Rs / m2", ">= 0"),
    "use_far_benefit": ("Count the FAR value?", "true / false", ""),
}

MEASURE_COLS = [
    ("measure_id", "Unique short code, e.g. PV_100", "required, unique"),
    ("name", "Readable name shown on screens", "required"),
    ("exclusive_group", "Measures in the same group are alternatives (only one chosen). Blank = independent", "optional"),
    ("kind", "efficiency, renewable, water or none: decides which savings credit it feeds", "required"),
    ("credit_id", "IGBC credit it earns (must exist in igbc_credits.csv)", "optional"),
    ("points_fixed", "Points for 'fixed' credits (threshold credits are scored from savings)", ">= 0"),
    ("capex", "Upfront cost, Rs, extra over the code-minimum baseline", ">= 0"),
    ("subsidy", "Subsidy received at year 0, Rs", "<= capex"),
    ("om_annual", "Maintenance in year 1, Rs per year", ">= 0"),
    ("om_escalation", "Yearly growth of maintenance (fraction)", "-0.05 to 0.20"),
    ("energy_saving_kwh", "Electricity saved, kWh per year (efficiency measures)", ">= 0"),
    ("kwp", "Solar size in kWp (renewable measures; energy = kWp x yield)", "> 0 for solar"),
    ("water_saving_kl", "Water saved, kL per year", ">= 0"),
    ("degradation", "Yearly loss of performance (fraction), e.g. 0.006 for panels", "0 to 0.10"),
    ("source", "'library' or 'quote:<file>' (set automatically by the quote importer)", "optional"),
    ("description", "Free text", "optional"),
]


def flow_diagram() -> Drawing:
    h = 150
    d = Drawing(W, h)
    cw = (W - 2 * 12 * mm) / 3
    xs = [0, cw + 12 * mm, 2 * (cw + 12 * mm)]
    for x, t in zip(xs, ["WHAT GOES IN", "WHAT THE TOOL DOES", "WHAT COMES OUT"]):
        d.add(String(x, h - 7, t, fontName="Helvetica-Bold", fontSize=7.2, fillColor=colors.HexColor(INK2)))
    ins = [("project_demo.json", "the building and the money"), ("measures.csv", "the menu of green options"), ("components.csv", "parts re-bought over time"),
           ("igbc_credits / levels.csv", "how points and levels work"), ("Vendor quote PDFs", "optional, read by AI")]
    for i, (t, s) in enumerate(ins):
        box(d, xs[0], h - 38 - i * 27.5, cw, 24, t, s, fill="#FFFFFF")
    steps = [("1  Check every input", ""), ("2  Cost each measure over its life", ""), ("3  Score IGBC points", ""),
             ("4  Search every combination", ""), ("5  Stress-test the answer", "")]
    for i, (t, s) in enumerate(steps):
        box(d, xs[1], h - 38 - i * 27.5, cw, 24, t, s, hot=(i == 3))
    outs = [("Answer on screen", "spend X more, save Y"), ("Decision report", "PDF, 6 pages"), ("Results workbook", "Excel, every number"),
            ("Project file", "reopen the setup"), ("Owner memo", "plain-language summary")]
    for i, (t, s) in enumerate(outs):
        box(d, xs[2], h - 38 - i * 27.5, cw, 24, t, s, fill="#FFFFFF")
    arrow(d, xs[0] + cw + 2, h / 2 - 10, xs[1] - 2, h / 2 - 10)
    arrow(d, xs[1] + cw + 2, h / 2 - 10, xs[2] - 2, h / 2 - 10)
    return d


def about() -> list:
    s = [P("GreenLCC India: what it is and what it needs", "title"),
         P(f"The problem, how the tool works, every input file it reads, and what it gives back · {date.today():%d %b %Y}", "sub"),
         P("In one paragraph", "h2"),
         P("GreenLCC is a decision tool for Indian buildings that want an <b>IGBC green rating</b>. Most projects pick green measures (solar, efficient air-conditioning, "
           "better glazing, LED lighting, water fixtures) by <b>lowest upfront price</b>. GreenLCC instead costs every measure over the building's <b>whole life</b>: "
           "purchase, maintenance, parts that must be replaced, energy and water saved as tariffs rise, and leftover value at the end. It then tests every legal "
           "combination of measures to find the one that reaches the target rating for the <b>least lifetime cost</b>, and checks how safe that answer is if "
           "electricity prices and interest rates change."),
         P("The problem it solves", "h2")]
    s += B(["<b>First-cost bias.</b> Green buildings cost a few percent more upfront, and tenders reward the lowest price, so options that save far more over "
            "25 years lose to cheaper ones.",
            "<b>Rising, uncertain tariffs.</b> Commercial electricity tariffs keep changing, while credit for exported rooftop solar is low "
            "(about Rs 2.82/kWh in Maharashtra). A single payback number hides that risk.",
            "<b>Points chased blindly.</b> Ratings bring marketing value and, in some states, extra buildable floor area, but the cheapest points to buy are "
            "rarely the cheapest over the building's life.",
            "<b>Manual, unequal comparisons.</b> Equipment lasts different lengths of time, and vendor quotes arrive as PDFs that people retype into spreadsheets."])
    s += [P("Who it is for", "h3"),
          P("Building owners and developers, architects and MEP consultants justifying a specification, green-rating consultants, and procurement teams "
            "comparing bids on lifetime cost rather than price."),
          P("What it found for the demo building", "h3"),
          T([["Question", f"Answer (illustrative Pune office, {TARGET} target, {N} years)"],
             ["Which measures?", ", ".join(rec["measures"])],
             ["Rating reached", f"{rec['level']}, {rec['points']:g} points"],
             ["Versus cheapest-upfront route", f"{M(res['extra_capex'])} more upfront, {M(res['lifetime_gain_vs_cheapest'])} better over {N} years"],
             ["How safe?", f"Wins in {mc['p_recommended_beats_cheapest']*100:.0f}% of {mc['runs']:,} simulated futures"],
             ["Carbon", f"About {rec['co2_tonnes']:,.0f} tonnes of CO2 avoided"]], [.3, .7]),
          PageBreak(),
          P("How it works", "h2"), flow_diagram(), Spacer(1, 6)]
    s.append(T([["Step", "What happens, in plain words"],
                ["1  Check every input", "Each file is checked row by row (types, ranges, links between files). All problems are listed at once in plain words; nothing is silently accepted."],
                ["2  Cost each measure", "For every year of the study period: upfront cost in year 0, maintenance growing each year, parts re-bought when they wear out, "
                 "minus energy and water savings (tariffs rising, equipment slowly degrading), minus leftover value at the end. Each year is converted to today's money "
                 "and added up: that total is the <b>lifetime cost</b>."],
                ["3  Score IGBC points", "Fixed credits add their points. Energy, renewable and water credits are scored from the combined savings of the whole package "
                 "against threshold tables, so nothing is counted twice. Mandatory credits are checked."],
                ["4  Search every combination", f"One option per group (one HVAC system, one solar size...) or none; other measures on or off. For the demo that is "
                 f"{optimizer.combo_count(ds):,} combinations, all checked, so the answer is exact. Solar must fit the roof."],
                ["5  Stress-test the answer", "Tipping points (where the ranking flips), one-at-a-time sensitivity, and thousands of simulated futures with random "
                 "tariff growth, discount rate, equipment prices and solar output."]], [.22, .78]))
    s += [P("The core formula", "h3"),
          P("Lifetime cost (LCC) = sum over years t = 0 ... N of (costs in year t - savings in year t) / (1 + d)<super>t</super>, where d is the discount rate. "
            "Cost per year (EAC) = LCC x d / (1 - (1 + d)<super>-N</super>). All money is in nominal rupees; prices are year-1 prices that rise from year 2."),
          P("AI features", "h3"),
          P("Two optional helpers use Claude when an API key is set: reading a vendor quote PDF into draft fields (always reviewed by a person), and polishing "
            "the owner memo (it only sees computed numbers and may not change them). Without a key, a built-in reader and a template are used."),
          PageBreak()]

    # inputs
    s += [P("The input files", "h2"),
          P("All inputs live in the <b>data/</b> folder as plain CSV and JSON, so they can be edited in Excel or any text editor. Everything in the demo is "
            "<b>illustrative</b>: realistic in size, but not verified prices, tariffs or official IGBC tables."),
          T([["File", "What it describes", "Format", "Demo contents"],
             ["project_demo.json", "One building: areas, energy and water use, tariffs, finance, IGBC target, FAR bonus", "JSON, one object", p.name],
             ["measures.csv", "The menu of green measures and what each costs and saves", "CSV, one row per measure", f"{len(ds.measures)} measures"],
             ["components.csv", "Parts that wear out and must be re-bought", "CSV, one row per part", f"{len(ds.components)} parts"],
             ["igbc_credits.csv", "How each IGBC credit earns points", "CSV, one row per credit", f"{len(ds.credits)} credits"],
             ["igbc_levels.csv", "Points needed for each rating level", "CSV, one row per level",
              ", ".join(f"{lv.level} {lv.min_points:g}" for lv in sorted(ds.levels, key=lambda x: x.rank))],
             ["sample_quotes/*.pdf", "Vendor quotations for the AI importer (optional)", "PDF", "3 sample quotes"],
             ["Project file (.json)", "Everything above in one file, saved from the Report page", "JSON", "made by the tool"]], [.2, .4, .2, .2]),
          P("project_demo.json: the building and the money", "h3")]
    pdump = p.model_dump()
    rows = [["Field", "Meaning", "Unit", "Demo value", "Rule"]]
    for k, (meaning, unit, rule) in FIELD_INFO.items():
        v = pdump[k]
        if isinstance(v, dict):
            v = ", ".join(f"{a} {b:g}%" for a, b in v.items())
        elif isinstance(v, float):
            v = f"{v:g}"
        rows.append([k, meaning, unit, str(v), rule])
    s += [T(rows, [.25, .33, .13, .14, .15])]

    s += [P("measures.csv: the menu of green options", "h3"),
          P("One row per option. Costs are <b>extra over a code-minimum baseline</b> (doing nothing extra), so a VRF row holds the VRF price minus the split "
            "ACs it replaces."),
          T([["Column", "Meaning", "Rule"]] + [list(r) for r in MEASURE_COLS], [.2, .6, .2])]
    ex = ds.measures[0]
    s += [P(f"Example row: <i>{ex.measure_id}, {ex.name}, group {ex.exclusive_group}, {ex.kind}, credit {ex.credit_id}, capex Rs {ex.capex:,.0f}, "
            f"O&amp;M Rs {ex.om_annual:,.0f}/yr, saves {ex.energy_saving_kwh:,.0f} kWh/yr, degradation {ex.degradation:g}</i>.", "small"),
          KeepTogether([P("components.csv: parts that wear out", "h3"),
          T([["Column", "Meaning", "Rule"],
             ["measure_id", "Which measure the part belongs to", "must exist in measures.csv"],
             ["component", "Name, e.g. 'Inverter'", "required"],
             ["cost", "Price today, Rs (inflated to the year it is bought)", ">= 0"],
             ["life_years", "Re-bought every this many years; unused life at the end is credited back", "> 0"]], [.2, .6, .2])]),
          KeepTogether([P("igbc_credits.csv: how points are earned", "h3"),
          T([["Column", "Meaning", "Rule"],
             ["credit_id, category, name", "Credit code (e.g. EE-C2), category and title", "required"],
             ["max_points", "Cap on the points this credit can give", "> 0"],
             ["rule", "<b>fixed</b> (measure gives its points_fixed) or <b>threshold_pct</b> (points from % saving)", "one of the two"],
             ["basis", "For threshold credits: energy_eff, energy_re or water", "needed for threshold_pct"],
             ["thresholds", "Steps as 'percent:points' joined by |, e.g. 3:1|6:3|9:5 means 3% saving gives 1 point, 6% gives 3...", "needed for threshold_pct"],
             ["mandatory", "True if the rating is impossible without it", "True / False"]], [.22, .58, .2])]),
          KeepTogether([P("igbc_levels.csv: points needed per level", "h3"),
          T([["Column", "Meaning"], ["level", "Name, e.g. Gold"], ["min_points", "Points needed to reach it"],
             ["rank", "Order from lowest (1) to highest"]], [.25, .75])]),
          P("Vendor quote PDFs (optional)", "h3"),
          P("A text-based PDF quotation. The importer drafts: vendor, item, capacity, quoted price, annual maintenance and one replaceable part with its cost and life. "
            "You add what a quote never states (energy saved, IGBC credit, the baseline cost to deduct) before it joins the library.")]

    s += [P("Checks the tool applies to inputs", "h2")]
    s += B(["Every number is range-checked (for example the discount rate must be between 0 and 30%, lives must be above zero, a subsidy cannot exceed capex).",
            "Every link between files is checked: unknown credit IDs, parts pointing at missing measures, duplicate measure IDs, a target level that doesn't exist.",
            "Solar measures must have a kWp; threshold credits must have a basis and thresholds.",
            "All problems are reported together, in plain words with the file, row and field, so one fix-and-reload pass is enough."])
    s += [P("What comes out", "h2"),
          T([["Output", "Who it is for", "What it contains"],
             ["Answer on screen", "Everyone", "One sentence per page, number cards, charts with 'What this means' lines, Quick what-if sliders"],
             ["Decision report (PDF, 6 pages)", "Owner, professor, IGBC consultant, tender team",
              "The answer and memo; the two routes and where the cost comes from; IGBC credit checklist with documents to submit; what to buy; risk check; assumptions and yearly cash flow"],
             ["Results workbook (Excel)", "Whoever checks the maths", "Summary, checklist, shortlist, yearly cash flow, every simulated future, top 200 combinations, all inputs"],
             ["Project file (.json)", "You, next time", "The whole setup in one file; open it from Home"]], [.24, .26, .5]),
          KeepTogether([P("Inside the repository", "h2"),
          T([["Folder / file", "What is there"],
             ["app.py", "Starts the app: menu, sidebar controls, page routing"],
             ["pages/", "The five screens: 0_home, 1_setup, 2_recommendation, 3_trust, 4_report"],
             ["core/", "The engine: finance, cashflow, igbc, optimizer, risk, carbon, extract (quotes), report and exports (PDF/Excel), charts, ui, state, io, schemas"],
             ["data/", "The input files described above"],
             ["sample_quotes/", "Three illustrative vendor quotations"],
             ["tests/", f"{N_TESTS} automated tests: hand-checked maths, IGBC scoring, optimiser, risk, exports, every screen"],
             ["scripts/", "Rebuild these documents, the sample quotes and the progress-log index"],
             ["docs/", "This document, the user guide and the project log"]], [.2, .8])]),
          P("Honest limits", "h2")]
    s += B(["<b>Illustrative data.</b> Prices, tariffs, IGBC point tables and the FAR bonus are placeholders until verified against official sources.",
            "<b>Savings add up simply.</b> In reality a better envelope reduces what efficient air-conditioning saves; a full energy simulation would refine this.",
            "<b>One tariff path and a fixed grid emission factor.</b> Real projects would use state tariff schedules and a falling emission factor.",
            "<b>The AI helpers need an API key</b> and have only been tested with their offline fallbacks so far."])
    s += [Spacer(1, 4), P("Built for CM 617 (Topic 6, LCCA decision tool) by a five-member student team.", "small")]
    return s


build(OUT_DIR / "GreenLCC_User_Guide.pdf", "User guide", user_guide())
build(OUT_DIR / "GreenLCC_About.pdf", "What it is and what it needs", about())
