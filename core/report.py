"""Results collection, narrative (LLM with template fallback) and Excel export."""
from __future__ import annotations

import io
import json
import os

import pandas as pd

from . import cashflow, optimizer, risk
from .schemas import Dataset

MODEL = "claude-sonnet-5-5"


def pct(v: float) -> str:
    """Percent with no negative zero (-0.0%)."""
    x = v * 100
    return f"{0.0 if abs(x) < 0.05 else x:.1f}%"


def money(x: float) -> str:
    s, a = ("-" if x < 0 else ""), abs(x)
    if a >= 1e7:
        return f"{s}Rs {a/1e7:.2f} Cr"
    if a >= 1e5:
        return f"{s}Rs {a/1e5:.1f} L"
    return f"{s}Rs {a:,.0f}"


def names(ds: Dataset, sel) -> list[str]:
    return [ds.measure(i).name for i in sel]


def collect_results(ds: Dataset, df: pd.DataFrame, target: str, objective: str, runs: int = 3000, seed: int = 42) -> dict:
    """Everything the report needs, as plain numbers (so the LLM can never invent any)."""
    p = ds.project
    rec = optimizer.best(df, ds, target, objective)
    cheap = optimizer.best(df, ds, target, "capex")
    if rec is None:
        return {"feasible": False, "target": target, "message": optimizer.infeasible_message(df, ds, target)}
    out = {
        "feasible": True, "project": p.name, "city": p.city, "target": target, "study_period_years": p.study_period,
        "discount_rate_pct": p.discount_rate * 100, "tariff_escalation_pct": p.tariff_escalation * 100,
        "recommended": {"measures": names(ds, rec["selection"]), "points": rec["points"], "level": rec["level"],
                        "capex": rec["capex"], "net_lcc": rec["lcc"], "eac": rec["eac"], "co2_tonnes": rec["co2_t"],
                        "far_benefit": rec["far_benefit"]},
        "cheapest_upfront": {"measures": names(ds, cheap["selection"]), "points": cheap["points"], "level": cheap["level"],
                             "capex": cheap["capex"], "net_lcc": cheap["lcc"], "co2_tonnes": cheap["co2_t"]},
        "extra_capex": rec["capex"] - cheap["capex"],
        "lifetime_gain_vs_cheapest": cheap["lcc"] - rec["lcc"],
        "same_portfolio": tuple(rec["selection"]) == tuple(cheap["selection"]),
    }
    a, b = cheap["selection"], rec["selection"]
    out["break_even"] = {k: risk.break_even(ds, a, b, k) for k in risk.BREAK_EVEN_RANGES}
    mc = risk.monte_carlo(ds, a, b, runs=runs, seed=seed)
    out["monte_carlo"] = {"runs": runs, "p_recommended_beats_cheapest": mc.p_b_better,
                          "recommended_p10": mc.pct_b["P10"], "recommended_p50": mc.pct_b["P50"], "recommended_p90": mc.pct_b["P90"],
                          "cheapest_p10": mc.pct_a["P10"], "cheapest_p50": mc.pct_a["P50"], "cheapest_p90": mc.pct_a["P90"],
                          "p_recommended_saves_money": mc.p_b_saves}
    return out


def template_narrative(r: dict) -> str:
    if not r.get("feasible"):
        return f"## Result\n\nThe {r['target']} target cannot be met with the current measure library.\n\n{r['message']}\n"
    rec, ch = r["recommended"], r["cheapest_upfront"]
    be = r["break_even"]
    lines = [
        f"# {r['project']}: IGBC {r['target']} at the lowest life-cycle cost\n",
        "## Recommendation",
        f"Build **{', '.join(rec['measures']) or 'no additional measures'}**. This reaches **{rec['points']:g} points "
        f"({rec['level']})** for an upfront investment of {money(rec['capex'])}, and its net life-cycle cost over "
        f"{r['study_period_years']} years is **{money(rec['net_lcc'])}** (negative means it saves money overall).",
        "",
        "## Versus the cheapest-upfront route",
    ]
    if r["same_portfolio"]:
        lines.append("The cheapest-upfront Gold-eligible portfolio and the lowest-lifetime-cost portfolio are the same here, "
                     "so there is no trade-off between first cost and lifetime value.")
    else:
        lines += [
            f"Choosing credits purely on first cost gives {ch['level']} ({ch['points']:g} pts) for {money(ch['capex'])} upfront, "
            f"but a net life-cycle cost of {money(ch['net_lcc'])}.",
            f"The recommended portfolio costs {money(r['extra_capex'])} more upfront and is **{money(r['lifetime_gain_vs_cheapest'])} better** "
            "over the study period.",
        ]
    if rec["far_benefit"]:
        lines.append(f"\nThe {rec['level']} rating may also unlock extra floor area worth about {money(rec['far_benefit'])} "
                     "(an assumed value; verify the local incentive).")
    lines += ["", "## Risk"]
    mc = r["monte_carlo"]
    lines.append(f"In {mc['runs']:,} simulated futures (uncertain tariff escalation, discount rate, capex and solar yield) the "
                 f"recommended portfolio beats the cheapest-upfront one in **{mc['p_recommended_beats_cheapest']*100:.0f}%** of runs. "
                 f"Its net LCC ranges from {money(mc['recommended_p10'])} (P10) to {money(mc['recommended_p90'])} (P90).")
    if be.get("discount") is not None:
        lines.append(f"The ranking only flips if the discount rate exceeds **{pct(be['discount'])}**.")
    if be.get("tariff_escalation") is not None:
        lines.append(f"It also flips if tariff escalation falls below **{pct(be['tariff_escalation'])}** a year.")
    lines += ["", f"## Carbon\nThe recommended portfolio avoids about **{rec['co2_tonnes']:,.0f} tCO2** over its life.",
              "", "*All point tables, tariffs and prices in this prototype are illustrative; verify against IGBC reference guides and local tariff orders.*"]
    return "\n".join(lines)


def llm_narrative(r: dict) -> str | None:
    if not os.environ.get("ANTHROPIC_API_KEY") or not r.get("feasible"):
        return None
    try:
        import anthropic

        prompt = ("Write a concise owner-facing decision memo (under 350 words, markdown headings: Recommendation, Why, Risk, "
                  "IGBC notes) using ONLY the numbers in this JSON. Never invent or change a number. Mention that data is illustrative.\n\n"
                  + json.dumps(r, default=float))
        msg = anthropic.Anthropic().messages.create(model=MODEL, max_tokens=900, messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text") or None
    except Exception:
        return None


def narrative(r: dict) -> tuple[str, str]:
    """(markdown, method)"""
    t = llm_narrative(r)
    return (t, "Claude") if t else (template_narrative(r), "template")


def _summary_rows(ds: Dataset, results: dict) -> list[tuple[str, str]]:
    p = ds.project
    if not results.get("feasible"):
        return [("Project", p.name), ("Target", results.get("target", "")), ("Result", results.get("message", ""))]
    rec, ch, mc = results["recommended"], results["cheapest_upfront"], results["monte_carlo"]
    be = results["break_even"]
    f = lambda v, as_pct=False: "never flips in tested range" if v is None else (pct(v) if as_pct else f"{v:.2f}")  # noqa: E731
    return [
        ("Project", p.name), ("Target IGBC level", results["target"]), ("Study period (years)", str(p.study_period)),
        ("Discount rate", f"{p.discount_rate*100:.1f}%"), ("Tariff escalation", f"{p.tariff_escalation*100:.1f}% / yr"), ("", ""),
        ("RECOMMENDED PORTFOLIO", ", ".join(rec["measures"])), ("Points / level", f"{rec['points']:g} / {rec['level']}"),
        ("Upfront capex", money(rec["capex"])), ("Net life-cycle cost", money(rec["net_lcc"])),
        ("Equivalent annual cost", money(rec["eac"])), ("CO2 avoided (tonnes)", f"{rec['co2_tonnes']:,.0f}"), ("", ""),
        ("CHEAPEST-UPFRONT PORTFOLIO", ", ".join(ch["measures"])), ("Points / level", f"{ch['points']:g} / {ch['level']}"),
        ("Upfront capex", money(ch["capex"])), ("Net life-cycle cost", money(ch["net_lcc"])), ("", ""),
        ("Lifetime gain of recommended", money(results["lifetime_gain_vs_cheapest"])),
        ("Extra upfront for recommended", money(results["extra_capex"])), ("", ""),
        ("Monte Carlo: recommended wins", f"{mc['p_recommended_beats_cheapest']*100:.0f}% of {mc['runs']:,} runs"),
        ("Ranking flips if discount rate above", f(be.get("discount"), True)),
        ("Ranking flips if tariff escalation below", f(be.get("tariff_escalation"), True)), ("", ""),
        ("NOTE", "Illustrative prototype data; verify IGBC point tables, tariffs and prices before real decisions."),
    ]


def _style(wb) -> None:
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    head = PatternFill("solid", fgColor="1E7B4F")
    for ws in wb.worksheets:
        ws.sheet_view.showGridLines = False
        for c in ws[1]:
            c.fill, c.font = head, Font(bold=True, color="FFFFFF")
            c.alignment = Alignment(vertical="center", wrap_text=True)
        ws.freeze_panes = "A2"
        for col in ws.columns:
            width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(width + 2, 10), 70)
            for c in col[1:]:
                if isinstance(c.value, (int, float)) and not isinstance(c.value, bool):
                    c.number_format = "#,##0.00" if abs(c.value) < 10 and c.value != int(c.value) else "#,##0"
                if isinstance(c.value, str) and len(c.value) > 70:
                    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws = wb["Summary"]
    ws.column_dimensions["A"].width = 42
    ws.column_dimensions["B"].width = 90
    for row in ws.iter_rows(min_row=2):
        if row[0].value and str(row[0].value).isupper():
            row[0].font = Font(bold=True, color="0F4D33")
            row[1].font = Font(bold=True)


def to_excel(ds: Dataset, df: pd.DataFrame, rec_sel, results: dict, cheap_sel=()) -> bytes:
    """Formatted, multi-sheet workbook: summary, IGBC checklist, shortlist, cash flow, Monte Carlo, inputs, all portfolios."""
    from . import tables

    p = ds.project
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame(_summary_rows(ds, results), columns=["Item", "Value"]).to_excel(xw, sheet_name="Summary", index=False)
        tables.checklist(ds, rec_sel).to_excel(xw, sheet_name="IGBC checklist", index=False)
        tables.shortlist(ds, rec_sel).to_excel(xw, sheet_name="Procurement shortlist", index=False)
        tables.cashflow_table(ds, rec_sel).to_excel(xw, sheet_name="Recommended cash flow")
        if results.get("feasible"):
            tables.mc_runs(ds, cheap_sel, rec_sel, results["monte_carlo"]["runs"]).to_excel(xw, sheet_name="Monte Carlo runs", index=False)
        top = df.sort_values("lcc").head(200).copy()
        top["selection"] = top["selection"].map(", ".join)
        top.to_excel(xw, sheet_name="Portfolios (top 200)", index=False)
        pd.DataFrame(p.model_dump().items(), columns=["parameter", "value"]).astype(str).to_excel(xw, sheet_name="Project", index=False)
        pd.DataFrame([m.model_dump() for m in ds.measures]).to_excel(xw, sheet_name="Measures", index=False)
        pd.DataFrame([c.model_dump() for c in ds.components]).to_excel(xw, sheet_name="Components", index=False)
        pd.DataFrame([(k, json.dumps(v, default=float)) for k, v in results.items()], columns=["key", "value"]).to_excel(xw, sheet_name="Results", index=False)
        _style(xw.book)
    return buf.getvalue()
