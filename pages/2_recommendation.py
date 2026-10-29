import pandas as pd
import streamlit as st

from core import carbon, cashflow, charts, finance, igbc, optimizer, risk, state, ui

ui.page_header(2, "The recommendation", "Which combination of measures earns your IGBC target for the least money over the building's life, "
               "and what picking on upfront price would cost you instead.")
ds = ui.require_ds()
p = ds.project
target, df, rec, cheap = state.recommendation(ds)
need = next(lv.min_points for lv in ds.levels if lv.level == target)
if rec is None:
    ui.unreachable(ds, df, target)

gain = cheap["lcc"] - rec["lcc"]
same = tuple(rec["selection"]) == tuple(cheap["selection"])
extra = rec["capex"] - cheap["capex"]
inc = None if same else risk.incremental(ds, cheap["selection"], rec["selection"])
if same:
    ui.verdict(f"IGBC {target} · the answer", "The cheapest way to reach the target is also the cheapest over its life",
               f"No first-cost trap here: build the measures below for {ui.inr(rec['capex'])} upfront.")
else:
    rate_txt = ("" if inc["rate"] is None else
                f" The extra money earns <b>{ui.pct(inc['rate'])} a year</b> ({'IRR' if inc['method'] == 'IRR' else 'MIRR'}), "
                f"{'above' if inc['rate'] >= p.discount_rate else 'below'} the {ui.pct(p.discount_rate)} MARR.")
    ui.verdict(f"IGBC {target} · the answer", f"Spend {ui.inr(extra)} more upfront, save {ui.inr(gain)} in present worth over {p.study_period} years",
               "Picking credits on cheapest price looks thrifty on day one but loses on electricity, maintenance and replacements." + rate_txt)

ui.kpis([
    ("IGBC result", f"{rec['level']} · {rec['points']:g} pts", f"{target} needs {need:g} ✓", "brand"),
    (ui.label("lcc"), ui.inr(rec["lcc"]), f"over {p.study_period} yrs at {ui.pct(p.discount_rate)} MARR", "good" if rec["lcc"] < 0 else "", ui.tip("lcc")),
    (ui.label("inc"), "same mix" if same else ("n/a" if inc["rate"] is None else ui.pct(inc["rate"])),
     "no extra spend" if same else f"{inc['method']} vs MARR {ui.pct(p.discount_rate)}",
     "" if same or inc["rate"] is None else ("good" if inc["rate"] >= p.discount_rate else "bad"), ui.tip("inc")),
    (ui.label("capex"), ui.inr(rec["capex"]), f"cheapest route: {ui.inr(cheap['capex'])}", "", ui.tip("capex")),
    (ui.label("co2"), f"{rec['co2_t']:,.0f} t", "over the study period", "", ui.tip("co2")),
])
st.write("")

colA, colB = st.columns(2)
with colA:
    st.markdown("##### Cheapest upfront (today's habit)")
    ui.chips([ds.measure(i).name for i in cheap["selection"]], alt=True)
    st.caption(f"{cheap['level']} · {cheap['points']:g} pts · upfront {ui.inr(cheap['capex'])} · LCC {ui.inr(cheap['lcc'])} · EUAC {ui.inr(cheap['eac'])}/yr")
with colB:
    st.markdown("##### Recommended (lowest life-cycle cost)")
    ui.chips([ds.measure(i).name for i in rec["selection"]])
    st.caption(f"{rec['level']} · {rec['points']:g} pts · upfront {ui.inr(rec['capex'])} · LCC {ui.inr(rec['lcc'])} · EUAC {ui.inr(rec['eac'])}/yr")

bd_c, bd_r = optimizer.breakdown(cheap), optimizer.breakdown(rec)
st.plotly_chart(charts.stacked_compare({"Cheapest upfront": bd_c, "Recommended": bd_r}), width="stretch", config={"displayModeBar": False})
diff = {k: bd_r[k] - bd_c[k] for k in bd_c}
big = min(diff, key=diff.get)
if not same and diff[big] < 0:
    st.caption(f"**What this means:** the recommended mix costs {ui.inr(diff['Capex'])} more in equipment, but **{big.lower()}** "
               f"move {ui.inr(-diff[big])} in its favour. Bars below zero are money saved.")

# --- quick what-if: the most demo-friendly 'smart' feature
with st.container(border=True):
    st.markdown("##### Quick what-if")
    w1, w2, w3 = st.columns([1, 1, 1.3])
    g = w1.slider("Electricity price growth (% / yr)", -2.0, 12.0, round(p.tariff_escalation * 100, 1), 0.5) / 100
    d = w2.slider("MARR (%)", 2.0, 25.0, round(p.discount_rate * 100, 1), 0.5) / 100
    la, lb = risk.lcc(ds, cheap["selection"], d=d, g=g), risk.lcc(ds, rec["selection"], d=d, g=g)
    with w3:
        if same:
            st.metric("Life-cycle cost of the mix", ui.inr(lb))
        elif lb < la:
            st.metric("Recommended still wins by", ui.inr(la - lb), help="Present worth, both routes at these settings.")
        else:
            st.metric("Cheapest-upfront wins by", ui.inr(lb - la), help="At these settings the ranking flips.")
    st.caption("Moves only these two assumptions and re-costs both routes instantly. The **Check the risk** page tests thousands of combinations at once.")

st.write("")
tabs = st.tabs(["Other options", "Credits earned", "Upgrade path", "Compare measures", "How it's calculated"])

with tabs[0]:
    f = optimizer.feasible(df, ds, target).sort_values(["lcc", "capex"]).head(10)
    t = pd.DataFrame({
        "Rank": range(1, len(f) + 1),
        "Measures": f["selection"].map(lambda s: ", ".join(ds.measure(i).name for i in s)),
        "Points": f["points"], "Level": f["level"], ui.label("capex"): f["capex"].map(ui.inr), ui.label("lcc"): f["lcc"].map(ui.inr),
        ui.label("eac"): f["eac"].map(ui.inr), "CO₂ (t)": f["co2_t"].map(lambda v: f"{v:,.0f}")})
    st.dataframe(t, width="stretch", hide_index=True)
    st.caption(f"The 10 best of {len(df):,} combinations searched ({len(optimizer.feasible(df, ds, target)):,} reach {target}). "
               "Every combination is checked, so rank 1 is the true optimum, not a guess.")

with tabs[1]:
    which = st.radio("Show credits for", ["Recommended", "Cheapest upfront"], horizontal=True)
    sel = rec["selection"] if which == "Recommended" else cheap["selection"]
    sc = igbc.score(ds, [ds.measure(i) for i in sel])
    k1, k2 = st.columns([1.6, 1])
    k1.plotly_chart(charts.credit_bars(sc.breakdown), width="stretch", config={"displayModeBar": False})
    with k2:
        m = sc.metrics
        st.metric("Energy saving (efficiency)", f"{m['energy_eff_pct']:.1f}%")
        st.metric("On-site renewable share", f"{m['energy_re_pct']:.1f}%")
        st.metric("Water saving", f"{m['water_pct']:.0f}%")
        st.markdown("**Mandatory credits:** " + ("✅ all met" if sc.mandatory_ok else f"❌ missing {', '.join(sc.missing_mandatory)}"))
    st.caption("IGBC points are the non-monetary benefit weighed alongside present worth (Ch 5). "
               "The full credit-by-credit checklist with documents to submit is in the PDF report.")

with tabs[2]:
    path = optimizer.upgrade_path(df, ds, "lcc")
    if path.empty:
        st.info("No level is reachable with this library.")
    else:
        steps = [None] + [risk.incremental(ds, a, b) if tuple(a) != tuple(b) else None
                          for a, b in zip(path["selection"], path["selection"].iloc[1:])]
        show = pd.DataFrame({
            "Level": path["Level"], "Points": path["Points"], ui.label("capex"): path["Capex"].map(ui.inr), ui.label("lcc"): path["LCC"].map(ui.inr),
            "Extra LCC vs previous level": path["Incremental LCC vs previous level"].map(lambda v: "–" if pd.isna(v) else ui.inr(v)),
            "Return on the step-up capex": [("–" if s is None else
                                             ("n/a" if s["rate"] is None else f"{ui.pct(s['rate'])} ({s['method']})")) for s in steps],
            "Measures": path["selection"].map(lambda s: ", ".join(ds.measure(i).name for i in s))})
        st.dataframe(show, width="stretch", hide_index=True)
        st.plotly_chart(charts.upgrade_chart(path), width="stretch", config={"displayModeBar": False})
        st.caption("**What this means:** each step up is a pairwise challenger-vs-defender comparison (Ch 7). When several levels show the same "
                   "measures, the lowest-LCC mix already clears the higher level, so going up costs nothing extra over the building's life.")

with tabs[3]:
    by_group = optimizer.groups(ds)
    alts_default = next((ids for ids in by_group.values() if len(ids) > 1), [m.measure_id for m in ds.measures[:2]])
    names = {m.measure_id: m.name for m in ds.measures}
    pick = st.multiselect("Measures to compare side by side", list(names), default=alts_default, format_func=names.get, max_selections=5,
                          help="Each one is costed on its own against the code-minimum baseline (doing nothing extra).")
    if pick:
        rows, series = [], {}
        for mid in pick:
            S = risk.portfolio_streams(ds, [mid])
            s = cashflow.summarize(S, p)
            series[names[mid]] = cashflow.yearly_table(S, p)["Cumulative PW"]
            rows.append({"Measure": names[mid], **s, "life": ds.measure(mid).life_years, "co2": carbon.lifetime_co2_t(p, S)})
        res = pd.DataFrame(rows)
        best, cheapest = res.loc[res["lcc"].idxmin()], res.loc[res["capex"].idxmin()]
        if best["Measure"] != cheapest["Measure"]:
            ui.callout(f"<b>First cost misleads here:</b> {cheapest['Measure']} is cheapest to buy, but {best['Measure']} costs "
                       f"<b>{ui.inr(cheapest['lcc'] - best['lcc'])}</b> less in present worth over {p.study_period} years.", "good")
        c1, c2 = st.columns(2)
        c1.plotly_chart(charts.alt_bars(list(res["Measure"]), list(res["lcc"]), list(res["eac"])), width="stretch", config={"displayModeBar": False})
        c2.plotly_chart(charts.cumulative_lines(series), width="stretch", config={"displayModeBar": False})
        st.dataframe(pd.DataFrame({
            "Measure": res["Measure"], ui.label("capex"): res["capex"].map(ui.inr), "Life (yrs)": res["life"].map(lambda v: f"{v:g}"),
            ui.label("lcc"): res["lcc"].map(ui.inr), ui.label("eac"): res["eac"].map(ui.inr),
            ui.label("bcr"): res["bcr"].map(lambda v: "–" if v is None or pd.isna(v) else f"{v:.2f}"),
            ui.label("ror"): [("n/a" if r is None or pd.isna(r) else f"{ui.pct(r)} ({mth})") for r, mth in zip(res["ror"], res["ror_method"])],
            ui.label("payback"): res["disc_payback"].map(lambda v: "never" if v is None or pd.isna(v) else f"{v:.1f} yrs"),
            "CO₂ avoided (t)": res["co2"].map(lambda v: f"{v:,.0f}")}), width="stretch", hide_index=True,
            column_config={ui.label(k): st.column_config.TextColumn(help=ui.tip(k)) for k in ("lcc", "eac", "bcr", "ror", "payback")})
        st.caption(f"Accept a measure when its PW of cost is negative, i.e. BCR > 1 and rate of return > MARR ({ui.pct(p.discount_rate)}). "
                   "Rank alternatives on PW or EUAC, not on the rate of return (the Ch 8 ranking paradox).")
        with st.expander("Cash flow diagram and year-by-year table of one measure"):
            one = st.selectbox("Measure", pick, format_func=names.get, key="cf_pick")
            disp = cashflow.yearly_table(risk.portfolio_streams(ds, [one]), p)
            st.plotly_chart(charts.cash_flow_diagram(disp), width="stretch", config={"displayModeBar": False})
            show = disp.copy()
            for col in show.columns:
                show[col] = show[col].map(("{:.4f}" if col == "Discount factor" else "{:,.0f}").format)
            st.dataframe(show, width="stretch", height=380)
            st.caption("Costs positive, savings negative. Present worth = net cash flow × (P/F, MARR, t); its sum is the life-cycle cost.")
    else:
        st.info("Pick at least one measure.")

with tabs[4]:
    n, i, f_ = p.study_period, p.discount_rate, p.inflation
    st.latex(r"\mathrm{LCC}=\sum_{t=0}^{N}\frac{C_t-S_t}{(1+i)^t}\qquad \mathrm{EUAC}=\mathrm{LCC}\times(A/P,i,N)\qquad"
             r"(1+i)=(1+i_{real})(1+f)")
    st.markdown(f"""
- **C_t** = upfront cost (year 0) + O&M (rising with inflation) + re-purchases when a measure or its part wears out (inflated) − salvage at year N.
- **S_t** = electricity saved × tariff (tariff rising, equipment slowly degrading) + water saved × water tariff. Solar splits into
  self-used kWh at the retail tariff and exported kWh at the export credit.
- **i** = MARR {ui.pct(i)} (nominal), **f** = inflation {ui.pct(f_)}, so the real MARR is {finance.real_rate(i, f_)*100:.2f}%.
  **N** = {n} years (one planning horizon for every alternative, with salvage at the end: Ch 5). (A/P, i, N) = {finance.ap(i, n):.4f}.
- **Accept / rank.** A measure is worth it when its LCC is negative, its BCR > 1, and its IRR (or MIRR if the cash flow changes sign
  more than once) beats the MARR. Between two mixes, the extra capex must earn at least the MARR (incremental analysis, Ch 7).
- **Search.** One option per group (one HVAC system, one solar size…) or none; other measures on/off. That is
  **{optimizer.combo_count(ds):,}** combinations, all checked, so the answer is exact.
- **Feasible** = points ≥ {need:g} for {target}, every mandatory credit met, and solar fits the roof ({p.roof_kwp_cap:,.0f} kWp).
- **Limits.** Savings are additive (no interaction between measures); IGBC point tables are illustrative; taxes, depreciation and
  financing are outside the model (pre-tax owner view).
""")
    with st.expander("Hand-check one measure with interest factors (Ch 3)"):
        names = {m.measure_id: m.name for m in ds.measures}
        mid = st.selectbox("Measure", list(names), format_func=names.get, key="hand_pick")
        m = ds.measure(mid)
        if m.kwp > 0:
            st.info("Solar output splits between self-use and export, so its hand-check needs two series; pick an efficiency or water measure.")
        else:
            a1 = m.energy_saving_kwh * p.grid_tariff + m.water_saving_kl * p.water_tariff
            g_s = p.tariff_escalation if m.energy_saving_kwh else p.water_escalation
            g_eff = (1 + g_s) * (1 - m.degradation) - 1
            pw_sav = a1 * finance.pa_geo(g_eff, i, n)
            pw_om = m.om_annual * finance.pa_geo(f_, i, n)
            ev = cashflow.evaluate(risk.portfolio_streams(ds, [mid]), p)
            pw_rest = ev.scalar("repl") - ev.scalar("resid")
            hand, engine = m.capex + pw_om - pw_sav + pw_rest, ev.scalar("lcc")
            st.markdown(f"""
| Item | Factor form | Present worth |
|---|---|---|
| Capex at year 0 | P | {ui.inr(m.capex)} |
| O&M, year 1 = {ui.inr(m.om_annual)}, growing {ui.pct(f_)} | A₁ × (P/A₁, g={ui.pct(f_)}, i={ui.pct(i)}, {n}) = × {finance.pa_geo(f_, i, n):.3f} | {ui.inr(pw_om)} |
| Savings, year 1 = {ui.inr(a1)}, growing {ui.pct(g_eff)} net of degradation | − A₁ × (P/A₁, g, i, {n}) = × {finance.pa_geo(g_eff, i, n):.3f} | −{ui.inr(pw_sav)} |
| Re-purchases − salvage | Σ cost × (F/P, f, t) × (P/F, i, t) − salvage × (P/F, i, {n}) | {ui.inr(pw_rest)} |
| **Life-cycle cost** | sum of the lines | **{ui.inr(hand)}** |
""")
            ok = abs(hand - engine) <= max(1.0, 1e-6 * abs(engine))
            st.caption(f"Engine (year-by-year sum): {ui.inr(engine)} · {'✅ matches' if ok else '⚠️ differs'} the factor hand-check.")

ui.next_step("trust", "Next, see whether this answer survives a different MARR and electricity prices.")
