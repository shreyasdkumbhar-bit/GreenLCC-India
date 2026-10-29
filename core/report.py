"""Results collection, narrative (LLM with template fallback) and Excel export."""
from __future__ import annotations

import io
import json
import os

import pandas as pd

from . import finance, optimizer, risk
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


def ror_text(rate: float | None, method: str) -> str:
    return "n/a" if rate is None else f"{pct(rate)} ({method})"


def collect_results(ds: Dataset, df: pd.DataFrame, target: str, runs: int = 3000, seed: int = 42) -> dict:
    """Everything the report needs, as plain numbers (so the LLM can never invent any)."""
    p = ds.project
    rec = optimizer.best(df, ds, target, "lcc")
    cheap = optimizer.best(df, ds, target, "capex")
    if rec is None:
        return {"feasible": False, "target": target, "message": optimizer.infeasible_message(df, ds, target)}
    a, b = cheap["selection"], rec["selection"]
    out = {
        "feasible": True, "project": p.name, "city": p.city, "target": target, "study_period_years": p.study_period,
        "marr_pct": p.discount_rate * 100, "inflation_pct": p.inflation * 100, "tariff_escalation_pct": p.tariff_escalation * 100,
        "recommended": {"measures": names(ds, b), "points": rec["points"], "level": rec["level"],
                        "capex": rec["capex"], "lcc": rec["lcc"], "eac": rec["eac"], "co2_tonnes": rec["co2_t"]},
        "cheapest_upfront": {"measures": names(ds, a), "points": cheap["points"], "level": cheap["level"],
                             "capex": cheap["capex"], "lcc": cheap["lcc"], "eac": cheap["eac"], "co2_tonnes": cheap["co2_t"]},
        "extra_capex": rec["capex"] - cheap["capex"],
        "lifetime_gain_vs_cheapest": cheap["lcc"] - rec["lcc"],
        "same_portfolio": tuple(b) == tuple(a),
    }
    out["incremental"] = None if out["same_portfolio"] else risk.incremental(ds, a, b)
    out["break_even"] = {k: risk.break_even(ds, a, b, k) for k in risk.BREAK_EVEN_RANGES}
    mc = risk.monte_carlo(ds, a, b, runs=runs, seed=seed)
    out["monte_carlo"] = {"runs": runs, "p_recommended_beats_cheapest": mc.p_b_better,
                          "recommended_p10": mc.pct_b["P10"], "recommended_p50": mc.pct_b["P50"], "recommended_p90": mc.pct_b["P90"],
                          "cheapest_p10": mc.pct_a["P10"], "cheapest_p50": mc.pct_a["P50"], "cheapest_p90": mc.pct_a["P90"],
                          "p_recommended_saves_money": mc.p_b_saves}
    return out


def incremental_sentence(r: dict) -> str:
    """Ch 7 rule in one line: does the extra upfront money earn at least the MARR?"""
    inc = r.get("incremental")
    if not inc:
        return ""
    rate, marr = inc["rate"], inc["marr"]
    if rate is None:
        return (f"The extra {money(inc['extra_capex'])} has no single rate of return; "
                f"decide on present worth (gain {money(inc['pw_gain'])}).")
    kind = "incremental IRR" if inc["method"] == "IRR" else "incremental MIRR"
    ok = rate >= marr
    return (f"The extra {money(inc['extra_capex'])} upfront earns **{pct(rate)} a year** ({kind}), "
            f"{'above' if ok else 'below'} the {pct(marr)} MARR, so the costlier mix is {'worth it' if ok else 'not worth it'}.")


def template_narrative(r: dict) -> str:
    if not r.get("feasible"):
        return f"## Result\n\nThe {r['target']} target cannot be met with the current measure library.\n\n{r['message']}\n"
    rec, ch = r["recommended"], r["cheapest_upfront"]
    be = r["break_even"]
    lines = [
        f"# {r['project']}: IGBC {r['target']} at the lowest life-cycle cost\n",
        "## Recommendation",
        f"Build **{', '.join(rec['measures']) or 'no additional measures'}**. This reaches **{rec['points']:g} points "
        f"({rec['level']})** for an upfront investment of {money(rec['capex'])}. Its present worth of net cost over "
        f"{r['study_period_years']} years at a {r['marr_pct']:.1f}% MARR is **{money(rec['lcc'])}** "
        f"(EUAC {money(rec['eac'])} a year; negative means it saves money overall).",
        "",
        "## Versus the cheapest-upfront route",
    ]
    if r["same_portfolio"]:
        lines.append(f"The cheapest-upfront {r['target']} portfolio and the lowest-life-cycle-cost portfolio are the same here, "
                     "so there is no trade-off between first cost and lifetime value.")
    else:
        lines += [
            f"Choosing credits purely on first cost gives {ch['level']} ({ch['points']:g} pts) for {money(ch['capex'])} upfront, "
            f"but a life-cycle cost of {money(ch['lcc'])}.",
            f"The recommended portfolio costs {money(r['extra_capex'])} more upfront and is **{money(r['lifetime_gain_vs_cheapest'])} better** "
            "in present worth over the study period.",
            incremental_sentence(r),
        ]
    lines += ["", "## Risk"]
    mc = r["monte_carlo"]
    lines.append(f"In {mc['runs']:,} simulated futures (uncertain tariff escalation, MARR, capex and solar yield) the "
                 f"recommended portfolio beats the cheapest-upfront one in **{mc['p_recommended_beats_cheapest']*100:.0f}%** of runs. "
                 f"Its life-cycle cost ranges from {money(mc['recommended_p10'])} (P10) to {money(mc['recommended_p90'])} (P90).")
    if be.get("discount") is not None:
        lines.append(f"The ranking only flips if the MARR exceeds **{pct(be['discount'])}**.")
    if be.get("tariff_escalation") is not None:
        lines.append(f"It also flips if tariff escalation falls below **{pct(be['tariff_escalation'])}** a year.")
    lines += ["", f"## Carbon\nThe recommended portfolio avoids about **{rec['co2_tonnes']:,.0f} tCO2** over its life.",
              "", "*Prices and tariffs are sourced estimates and the IGBC point tables are illustrative; verify before real decisions.*"]
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
    be, inc = results["break_even"], results.get("incremental") or {}
    f = lambda v, as_pct=False: "never flips in tested range" if v is None else (pct(v) if as_pct else f"{v:.2f}")  # noqa: E731
    return [
        ("Project", p.name), ("Target IGBC level", results["target"]), ("Study period (years)", str(p.study_period)),
        ("MARR (nominal)", f"{p.discount_rate*100:.1f}%"), ("Real MARR (Fisher)", pct(finance.real_rate(p.discount_rate, p.inflation))),
        ("Tariff escalation", f"{p.tariff_escalation*100:.1f}% / yr"), ("", ""),
        ("RECOMMENDED PORTFOLIO", ", ".join(rec["measures"])), ("Points / level", f"{rec['points']:g} / {rec['level']}"),
        ("Upfront capex", money(rec["capex"])), ("PW of net cost (LCC)", money(rec["lcc"])),
        ("EUAC", money(rec["eac"])), ("CO2 avoided (tonnes)", f"{rec['co2_tonnes']:,.0f}"), ("", ""),
        ("CHEAPEST-UPFRONT PORTFOLIO", ", ".join(ch["measures"])), ("Points / level", f"{ch['points']:g} / {ch['level']}"),
        ("Upfront capex", money(ch["capex"])), ("PW of net cost (LCC)", money(ch["lcc"])), ("", ""),
        ("INCREMENTAL ANALYSIS (RECOMMENDED OVER CHEAPEST)", ""),
        ("Extra upfront", money(results["extra_capex"])), ("PW gain", money(results["lifetime_gain_vs_cheapest"])),
        ("Incremental rate of return", ror_text(inc.get("rate"), inc.get("method", "")) if inc else "same portfolio"),
        ("Decision rule", "accept the costlier mix if the incremental rate >= MARR (Ch 7)"), ("", ""),
        ("Monte Carlo: recommended wins", f"{mc['p_recommended_beats_cheapest']*100:.0f}% of {mc['runs']:,} runs"),
        ("Ranking flips if MARR above", f(be.get("discount"), True)),
        ("Ranking flips if tariff escalation below", f(be.get("tariff_escalation"), True)),
        ("Ranking flips if all capex scaled above", f(be.get("capex_mult"))), ("", ""),
        ("NOTE", "Prices and tariffs are sourced estimates; IGBC point tables are illustrative. Verify before real decisions."),
    ]


def to_excel(ds: Dataset, df: pd.DataFrame, rec_sel, results: dict, cheap_sel=()) -> bytes:
    """Results workbook: summary, checklist, shortlist, cash flow, Monte Carlo, portfolios, plus the input sheets
    (so this file can also be reopened from Home)."""
    from openpyxl.styles import Font

    from . import io as gio
    from . import tables

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
        for name, sheet in gio.input_sheets(ds).items():
            if name != "README":
                sheet.to_excel(xw, sheet_name=name, index=False)
        pd.DataFrame([(k, json.dumps(v, default=float)) for k, v in results.items()],
                     columns=["key", "value"]).to_excel(xw, sheet_name="Results", index=False)
        gio.style_sheets(xw.book, {"Summary": {"A": 50, "B": 90}, **gio.INPUT_WIDTHS})
        ws = xw.book["Summary"]
        for row in ws.iter_rows(min_row=2):
            if row[0].value and str(row[0].value).isupper():
                row[0].font = Font(bold=True, color="0F4D33")
                row[1].font = Font(bold=True)
    return buf.getvalue()
