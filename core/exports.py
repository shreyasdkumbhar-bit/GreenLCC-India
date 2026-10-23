"""The comprehensive decision report (PDF) and the cached download set."""
from __future__ import annotations

import io
import re
from datetime import date
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import igbc, report, tables
from .schemas import Dataset

GREEN, DEEP, MINT, INK, INK2, GRID = "#1E7B4F", "#0F4D33", "#E3F1E8", "#0B0B0B", "#52514E", "#E1E0D9"
BLUE, AQUA = "#2A78D6", "#1BAF7A"


def safe(text: str) -> str:
    """Base-14 PDF fonts only cover Latin-1: map the few symbols we use, drop the rest."""
    t = (text.replace("₹", "Rs ").replace("−", "-").replace("–", "-").replace("—", "-").replace("≥", ">=").replace("≈", "~")
         .replace("→", "->").replace("✓", "").replace("✅", "").replace("❌", "").replace("’", "'").replace("“", '"').replace("”", '"'))
    return t.encode("cp1252", "replace").decode("cp1252")


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontName="Helvetica-Bold", fontSize=22, textColor=colors.HexColor(DEEP), alignment=TA_LEFT, spaceAfter=4, leading=26),
        "sub": ParagraphStyle("s", parent=base["Normal"], fontSize=10.5, textColor=colors.HexColor(INK2), spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=13.5, textColor=colors.HexColor(DEEP), spaceBefore=12, spaceAfter=5),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=11, textColor=colors.HexColor(INK), spaceBefore=8, spaceAfter=3),
        "body": ParagraphStyle("b", parent=base["Normal"], fontSize=10, leading=14.2, textColor=colors.HexColor(INK), spaceAfter=5),
        "small": ParagraphStyle("sm", parent=base["Normal"], fontSize=8.3, leading=11, textColor=colors.HexColor(INK2)),
        "cell": ParagraphStyle("c", parent=base["Normal"], fontSize=8.6, leading=10.8),
        "cellb": ParagraphStyle("cb", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8.6, leading=10.8, textColor=colors.white),
    }


def md_to_flow(md: str, st: dict) -> list:
    """Tiny markdown subset (#, ##, **bold**, *italic*, blank lines) -> reportlab flowables."""
    out = []
    for line in md.splitlines():
        line = line.rstrip()
        if not line:
            continue
        t = escape(safe(line))
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*", r"<i>\1</i>", t)
        t = re.sub(r"\bCO2\b", "CO<sub>2</sub>", t)
        if line.startswith("## "):
            out.append(Paragraph(t[3:], st["h2"]))
        elif line.startswith("# "):
            continue  # the document title is drawn separately
        else:
            out.append(Paragraph(t, st["body"]))
    return out


def grid_table(data: list[list], widths: list[float], st: dict, header: bool = True) -> Table:
    def cell(c):
        s = escape(safe(str(c)))
        for a, b in (("&lt;b&gt;", "<b>"), ("&lt;/b&gt;", "</b>"), ("&lt;i&gt;", "<i>"), ("&lt;/i&gt;", "</i>")):
            s = s.replace(a, b)  # allow simple emphasis in cells
        return s.replace("CO2", "CO<sub>2</sub>")

    rows = [[Paragraph(cell(c), st["cellb"] if (header and i == 0) else st["cell"]) for c in r] for i, r in enumerate(data)]
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor(GRID)),
             ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(GREEN)))
    t.setStyle(TableStyle(style))
    return t


def compare_chart(res: dict) -> Drawing:
    rec, ch = res["recommended"], res["cheapest_upfront"]
    d = Drawing(170 * mm, 62 * mm)
    c = VerticalBarChart()
    c.x, c.y, c.width, c.height = 40, 22, 360, 105
    c.data = [[ch["capex"] / 1e7, rec["capex"] / 1e7], [ch["net_lcc"] / 1e7, rec["net_lcc"] / 1e7]]
    c.categoryAxis.categoryNames = ["Cheapest upfront", "Recommended"]
    c.categoryAxis.labels.fontName = c.valueAxis.labels.fontName = "Helvetica"
    c.categoryAxis.labels.fontSize = c.valueAxis.labels.fontSize = 8.5
    c.categoryAxis.labelAxisMode = "low"
    c.categoryAxis.visibleGrid = 0
    c.valueAxis.gridStrokeColor = colors.HexColor(GRID)
    c.valueAxis.visibleGrid = 1
    c.bars[0].fillColor, c.bars[1].fillColor = colors.HexColor(BLUE), colors.HexColor(AQUA)
    c.bars.strokeColor = colors.white
    c.bars.strokeWidth = 1.5
    c.barLabelFormat = "%.2f"
    c.barLabels.fontSize = 8
    c.barLabels.nudge = 6
    c.groupSpacing = 30
    d.add(c)
    d.add(String(40, 148, "Upfront capex (blue) vs net life-cycle cost (green), Rs crore - lower is better", fontName="Helvetica-Bold", fontSize=9, fillColor=colors.HexColor(INK2)))
    return d


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor(INK2))
    canvas.drawString(18 * mm, 10 * mm, "GreenLCC India - illustrative prototype data; verify IGBC tables, tariffs and prices before real decisions.")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _rs(x) -> str:
    return "-" if x is None or pd.isna(x) else report.money(float(x))


def verdict(res: dict) -> str:
    """One plain sentence: what to do and why (used on screen and on page 1 of the PDF)."""
    rec = res["recommended"]
    if res["same_portfolio"]:
        return (f"Build the {len(rec['measures'])} recommended measures: the cheapest way to reach {res['target']} is also the cheapest "
                f"over {res['study_period_years']} years, so there is no first-cost trap here.")
    return (f"Spend {report.money(res['extra_capex'])} more upfront than the cheapest {res['target']} route and save "
            f"{report.money(res['lifetime_gain_vs_cheapest'])} over {res['study_period_years']} years.")


def risk_verdict(res: dict) -> str:
    mc, be = res["monte_carlo"], res["break_even"]
    flips = []
    if be.get("discount") is not None:
        flips.append(f"the discount rate rises above {report.pct(be['discount'])}")
    if be.get("tariff_escalation") is not None:
        g = be["tariff_escalation"]
        flips.append("electricity prices stop rising altogether" if abs(g) < 0.0005 else f"electricity prices grow slower than {report.pct(g)} a year")
    s = f"The recommendation wins in {mc['p_recommended_beats_cheapest']*100:.0f}% of {mc['runs']:,} simulated futures."
    return s + (f" It only loses if {' or '.join(flips)}." if flips else " It does not flip anywhere in the tested ranges.")


def decision_pdf(ds: Dataset, df: pd.DataFrame, res: dict, rec_sel, cheap_sel) -> bytes:
    """The one comprehensive report: summary, routes, IGBC checklist, shopping list, risk, assumptions + cash flow."""
    from . import optimizer, risk

    st = styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                            title=f"GreenLCC decision report - {ds.project.name}", author="GreenLCC India")
    W = A4[0] - 36 * mm
    p = ds.project

    def P(text: str, style: str = "body") -> Paragraph:
        return Paragraph(escape(safe(text)).replace("CO2", "CO<sub>2</sub>"), st[style])

    story = [Paragraph("IGBC decision report", st["title"]),
             P(f"{p.name} · {p.city} · target {res.get('target', p.target_level)} · {date.today():%d %b %Y}", "sub")]
    if not res.get("feasible"):
        story += [Paragraph("Target not reachable", st["h2"]), P(res.get("message", ""))]
        doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
        return buf.getvalue()

    rec, ch, mc, be = res["recommended"], res["cheapest_upfront"], res["monte_carlo"], res["break_even"]
    target = res["target"]
    rec_row = optimizer.best(df, ds, target, res.get("objective", "lcc"))
    ch_row = optimizer.best(df, ds, target, "capex")

    # 1 - summary
    kp = [["IGBC result", "Lifetime cost", "Upfront cost", "CO2 avoided"],
          [f"{rec['level']} · {rec['points']:g} pts", report.money(rec["net_lcc"]), report.money(rec["capex"]), f"{rec['co2_tonnes']:,.0f} t"]]
    story += [P("Contents: 1 Summary · 2 The two routes · 3 IGBC credit checklist · 4 What to buy · 5 Risk · "
                "6 Assumptions and yearly cash flow", "small"), Spacer(1, 6), grid_table(kp, [W * .25] * 4, st), Spacer(1, 4),
              Paragraph("1  The answer", st["h2"]), Paragraph("<b>" + escape(safe(verdict(res))) + "</b>", st["body"]), P(risk_verdict(res))]
    story += md_to_flow(report.template_narrative(res).split("## Risk")[0], st)
    story += [KeepTogether([compare_chart(res)]),
              P("Lifetime cost = everything paid minus everything saved over the study period, in today's money (present worth). "
                "A negative number means the measures pay for themselves.", "small"), PageBreak()]

    # 2 - routes
    def names(r) -> str:
        return ", ".join(ds.measure(i).name for i in r["selection"])

    rows = [["", "Cheapest upfront (today's habit)", "Recommended"],
            ["Measures", names(ch_row), names(rec_row)],
            ["IGBC level / points", f"{ch['level']} / {ch['points']:g}", f"{rec['level']} / {rec['points']:g}"],
            ["Upfront cost", _rs(ch["capex"]), _rs(rec["capex"])],
            ["Lifetime cost", _rs(ch["net_lcc"]), _rs(rec["net_lcc"])],
            ["Cost per year (EAC)", _rs(ch_row["eac"]), _rs(rec_row["eac"])],
            ["Extra-FAR value at this level", _rs(ch_row["far_benefit"]), _rs(rec_row["far_benefit"])],
            ["CO2 avoided over life", f"{ch['co2_tonnes']:,.0f} t", f"{rec['co2_tonnes']:,.0f} t"]]
    story += [Paragraph("2  The two routes to the same rating", st["h2"]), grid_table(rows, [W * .26, W * .37, W * .37], st), Spacer(1, 8)]
    bd_c, bd_r = optimizer.breakdown(ch_row), optimizer.breakdown(rec_row)
    rows = [["Where the lifetime cost comes from (present worth)", "Cheapest upfront", "Recommended"]] + [
        [k, _rs(bd_c[k]), _rs(bd_r[k])] for k in bd_c] + [
        ["<b>Total lifetime cost</b>", f"<b>{_rs(ch_row['lcc'])}</b>", f"<b>{_rs(rec_row['lcc'])}</b>"]]
    story += [grid_table(rows, [W * .46, W * .27, W * .27], st),
              P("Costs are positive; savings and leftover equipment value are negative.", "small"), Spacer(1, 8)]
    path = optimizer.upgrade_path(df, ds, "lcc")
    if not path.empty:
        rows = [["Level", "Points", "Upfront cost", "Lifetime cost", "Step-up vs previous level"]] + [
            [r["Level"], f"{r['Points']:g}", _rs(r["Capex"]), _rs(r["LCC"]), _rs(r["Incremental LCC vs previous level"])]
            for _, r in path.iterrows()]
        story.append(KeepTogether([Paragraph("Cheapest lifetime route to each IGBC level", st["h3"]),
                                   grid_table(rows, [W * .18, W * .12, W * .22, W * .22, W * .26], st)]))
    story.append(PageBreak())

    # 3 - checklist
    cl = tables.checklist(ds, rec_sel)
    data = [["Credit", "Name", "Pts", "Max", "Earned by", "Documents to submit (indicative)"]] + [
        [r["Credit"], r["Credit name"], f"{r['Points earned']:g}", f"{r['Maximum']:g}" if r["Maximum"] else "", r["Earned by"],
         r["Documents to submit (indicative)"]] for _, r in cl.iterrows()]
    story += [Paragraph("3  IGBC credit checklist (recommended portfolio)", st["h2"]),
              P("Hand this to the IGBC consultant: which credit each measure earns and the evidence usually asked for."),
              grid_table(data, [W * .1, W * .19, W * .06, W * .06, W * .23, W * .36], st),
              P("Point tables and document lists are illustrative; confirm against the current IGBC reference guide.", "small"), PageBreak()]

    # 4 - shopping list
    sl = tables.shortlist(ds, rec_sel)
    lcc_col = next(c for c in sl.columns if c.startswith("LCC over"))
    data = [["Measure", "Upfront", "O&M / yr", "Parts to replace", "Lifetime cost", "Payback"]] + [
        [r["Measure"], _rs(r["Upfront capex (Rs)"]), _rs(r["Annual O&M, year 1 (Rs)"]), r["Replaceable components"] or "-",
         _rs(r[lcc_col]), "never" if r["Simple payback (yrs)"] is None or pd.isna(r["Simple payback (yrs)"]) else f"{r['Simple payback (yrs)']:.1f} yrs"]
        for _, r in sl.iterrows()]
    story += [Paragraph("4  What to buy (procurement shortlist)", st["h2"]),
              P("For the tender team: ask vendors to quote lifetime cost, not just price. Each line is costed on its own against "
                "the code-minimum baseline."),
              grid_table(data, [W * .22, W * .12, W * .11, W * .31, W * .13, W * .11], st), PageBreak()]

    # 5 - risk
    def fmt(v, is_pct: bool) -> str:
        return "never flips in tested range" if v is None else (report.pct(v) if is_pct else f"x{v:.2f}")

    rk = [["Question", "Answer"],
          ["How often does the recommendation win?", f"{mc['p_recommended_beats_cheapest']*100:.0f}% of {mc['runs']:,} simulated futures"],
          ["Chance the recommended route saves money overall", f"{mc.get('p_recommended_saves_money', 0)*100:.0f}%"],
          ["Recommended lifetime cost, P10 / P50 / P90", f"{_rs(mc['recommended_p10'])} / {_rs(mc['recommended_p50'])} / {_rs(mc['recommended_p90'])}"],
          ["Cheapest-upfront lifetime cost, P10 / P50 / P90", f"{_rs(mc.get('cheapest_p10'))} / {_rs(mc.get('cheapest_p50'))} / {_rs(mc.get('cheapest_p90'))}"],
          ["Ranking flips if the discount rate is above", fmt(be.get("discount"), True)],
          ["Ranking flips if tariff growth is below", fmt(be.get("tariff_escalation"), True) + (" (flat prices)" if be.get("tariff_escalation") is not None and abs(be["tariff_escalation"]) < 0.0005 else "")],
          ["Ranking flips if today's tariff is scaled below", fmt(be.get("tariff_mult"), False)],
          ["Ranking flips if all capex is scaled above", fmt(be.get("capex_mult"), False)]]
    story += [Paragraph("5  Can we trust it? (risk)", st["h2"]), Paragraph("<b>" + escape(safe(risk_verdict(res))) + "</b>", st["body"]),
              grid_table(rk, [W * .55, W * .45], st), Spacer(1, 8)]
    tor = risk.tornado(ds, rec_sel).sort_values("swing", ascending=False)
    rows = [["Assumption changed (one at a time)", "Worse case", "Better case"]] + [
        [r["parameter"].replace("±", "+/-"), _rs(r["worse"]), _rs(r["better"])] for _, r in tor.iterrows()]
    story += [Paragraph("What moves the answer most (change in recommended lifetime cost)", st["h3"]),
              grid_table(rows, [W * .5, W * .25, W * .25], st),
              P("Verify the top two lines with real data first: they decide the result. Simulation draws: tariff growth ~ Normal, "
                "discount rate ~ triangular (-2/+3 pp), capex ~ triangular (-10%/+20%), solar yield ~ Normal(1, 7%).", "small"), PageBreak()]

    # 6 - assumptions + cash flow
    asm = [["Parameter", "Value"], ["Study period", f"{p.study_period} years"], ["Discount rate (nominal)", f"{p.discount_rate*100:.1f}%"],
           ["General inflation", f"{p.inflation*100:.1f}%"],
           ["Grid tariff (year 1)", f"Rs {p.grid_tariff:g}/kWh, growing {p.tariff_escalation*100:.1f}% a year"],
           ["Solar export credit", f"Rs {p.export_tariff:g}/kWh"], ["Grid emission factor", f"{p.grid_emission_factor} tCO2/MWh"],
           ["Extra FAR value counted", "Yes" if p.use_far_benefit else "No"]]
    story += [Paragraph("6  Assumptions", st["h2"]), grid_table(asm, [W * .4, W * .6], st), Spacer(1, 6)]
    cf = tables.cashflow_table(ds, rec_sel)
    cols = ["Capex", "O&M", "Replacement", "Residual value", "Energy savings", "Water savings", "Net cash flow", "Present worth", "Cumulative PW"]
    rows = [["Year", "Capex", "O&M", "Replace", "Residual", "Energy", "Water", "Net", "PW", "Cum. PW"]] + [
        [str(y)] + [f"{round(r[c] / 1e5, 1) + 0.0:,.1f}" for c in cols] for y, r in cf.iterrows()]
    story += [Paragraph("Yearly cash flow, recommended portfolio (Rs lakh; costs +, savings -)", st["h3"]),
              grid_table(rows, [W * .07] + [W * .93 / 9] * 9, st),
              P(f"The PW column sums to the lifetime cost before FAR value ({_rs(cf['Present worth'].sum())}). "
                "The Excel workbook has every number unrounded.", "small")]
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def build_files(ds: Dataset, target: str, objective: str, runs: int = 3000) -> dict:
    """Compute the downloads once (the UI caches this): the decision report PDF and the results workbook."""
    from . import optimizer

    df = optimizer.enumerate_portfolios(ds)
    res = report.collect_results(ds, df, target, objective, runs=runs)
    res["objective"] = objective
    if not res.get("feasible"):
        return {"res": res, "feasible": False}
    rs = optimizer.best(df, ds, target, objective)["selection"]
    cs = optimizer.best(df, ds, target, "capex")["selection"]
    return {
        "feasible": True, "res": res, "memo": report.template_narrative(res), "rec_sel": rs, "cheap_sel": cs,
        "pdf": decision_pdf(ds, df, res, rs, cs),
        "xlsx": report.to_excel(ds, df, rs, res, cs),
    }
