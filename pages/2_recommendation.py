import pandas as pd
import streamlit as st

from core import carbon, cashflow, charts, igbc, optimizer, risk, state, ui
from core.finance import crf

ui.page_header(2, "The recommendation", "Which combination of measures earns your IGBC target for the least money over the building's life, "
               "and what picking on upfront price would cost you instead.")
ds = ui.require_ds()
p = ds.project
target, obj, df, rec, cheap = state.recommendation(ds)
need = next(lv.min_points for lv in ds.levels if lv.level == target)
if rec is None:
    ui.unreachable(ds, df, target)

gain = cheap["lcc"] - rec["lcc"]
same = tuple(rec["selection"]) == tuple(cheap["selection"])
extra = rec["capex"] - cheap["capex"]
if same:
    ui.verdict(f"IGBC {target} · the answer", "The cheapest way to reach the target is also the cheapest over its life",
               f"No first-cost trap here: build the measures below for {ui.inr(rec['capex'])} upfront.")
else:
    ui.verdict(f"IGBC {target} · the answer", f"Spend {ui.inr(extra)} more upfront, save {ui.inr(gain)} over {p.study_period} years",
               "Picking credits on cheapest price looks thrifty on day one but loses on electricity, maintenance and replacements.")

ui.kpis([
    ("IGBC result", f"{rec['level']} · {rec['points']:g} pts", f"{target} needs {need:g} ✓", "brand"),
    (ui.label("lcc"), ui.inr(rec["lcc"]), f"over {p.study_period} yrs (− = pays for itself)", "good" if rec["lcc"] < 0 else "", ui.tip("lcc")),
    ("Better than cheapest-upfront by", "same mix" if same else ui.inr(gain), "no trade-off" if same else f"for {ui.inr(extra)} more upfront",
     "good" if gain > 0 else ""),
    (ui.label("capex"), ui.inr(rec["capex"]), f"cheapest route: {ui.inr(cheap['capex'])}", "", ui.tip("capex")),
    (ui.label("co2"), f"{rec['co2_t']:,.0f} t", "over the study period", "", ui.tip("co2")),
])
st.write("")

colA, colB = st.columns(2)
with colA:
    st.markdown("##### Cheapest upfront (today's habit)")
    ui.chips([ds.measure(i).name for i in cheap["selection"]], alt=True)
    st.caption(f"{cheap['level']} · {cheap['points']:g} pts · upfront {ui.inr(cheap['capex'])} · lifetime {ui.inr(cheap['lcc'])}")
with colB:
    st.markdown("##### Recommended (lowest lifetime cost)")
    ui.chips([ds.measure(i).name for i in rec["selection"]])
    st.caption(f"{rec['level']} · {rec['points']:g} pts · upfront {ui.inr(rec['capex'])} · lifetime {ui.inr(rec['lcc'])}")

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
    d = w2.slider("Discount rate (%)", 2.0, 20.0, round(p.discount_rate * 100, 1), 0.5) / 100
    la, lb = risk.lcc(ds, cheap["selection"], d=d, g=g), risk.lcc(ds, rec["selection"], d=d, g=g)
    with w3:
        if same:
            st.metric("Lifetime cost of the mix", ui.inr(lb))
        elif lb < la:
            st.metric("Recommended still wins by", ui.inr(la - lb), help="Lifetime cost before FAR value, both routes at these settings.")
        else:
            st.metric("Cheapest-upfront wins by", ui.inr(lb - la), help="At these settings the ranking flips.")
    st.caption("Moves only these two assumptions and re-costs both routes instantly. The **Check the risk** page tests thousands of combinations at once.")

st.write("")
tabs = st.tabs(["Other options", "Points vs cost", "Credits earned", "Upgrade path", "Compare measures", "How it's calculated"])

with tabs[0]:
    f = optimizer.feasible(df, ds, target).sort_values([obj, "capex"]).head(10)
    t = pd.DataFrame({
        "Rank": range(1, len(f) + 1),
        "Measures": f["selection"].map(lambda s: ", ".join(ds.measure(i).name for i in s)),
        "Points": f["points"], "Level": f["level"], ui.label("capex"): f["capex"].map(ui.inr), ui.label("lcc"): f["lcc"].map(ui.inr),
        ui.label("net_lcc"): f["net_lcc"].map(ui.inr), "CO₂ (t)": f["co2_t"].map(lambda v: f"{v:,.0f}")})
    st.dataframe(t, width="stretch", hide_index=True)
    st.caption(f"The 10 best of {len(df):,} combinations searched ({len(optimizer.feasible(df, ds, target)):,} reach {target}). "
               "Every combination is checked, so rank 1 is the true optimum, not a guess.")

with tabs[1]:
    front = optimizer.pareto(df)
    marks = {"Cheapest upfront": (cheap["points"], cheap["lcc"], charts.ORANGE), "Recommended": (rec["points"], rec["lcc"], charts.AQUA)}
    st.plotly_chart(charts.pareto_scatter(df[df["mandatory_ok"]], front, marks, {lv.level: lv.min_points for lv in ds.levels}),
                    width="stretch", config={"displayModeBar": False})
    st.caption("**What this means:** each grey dot is one possible mix. The blue line is the cheapest lifetime cost at each points level; "
               "anything above it is paying more than necessary for the same rating.")

with tabs[2]:
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
    st.caption("The full credit-by-credit checklist with documents to submit is in the PDF report.")

with tabs[3]:
    path = optimizer.upgrade_path(df, ds, "lcc")
    if path.empty:
        st.info("No level is reachable with this library.")
    else:
        show = pd.DataFrame({
            "Level": path["Level"], "Points": path["Points"], ui.label("capex"): path["Capex"].map(ui.inr), ui.label("lcc"): path["LCC"].map(ui.inr),
            "Extra lifetime cost vs previous level": path["Incremental LCC vs previous level"].map(lambda v: "–" if pd.isna(v) else ui.inr(v)),
            "Measures": path["selection"].map(lambda s: ", ".join(ds.measure(i).name for i in s))})
        st.dataframe(show, width="stretch", hide_index=True)
        st.plotly_chart(charts.upgrade_chart(path), width="stretch", config={"displayModeBar": False})
        st.caption("**What this means:** when several levels show the same measures, the cheapest-lifetime mix already clears the higher "
                   "level, so going up is free over the building's life.")

with tabs[4]:
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
            rows.append({"Measure": names[mid], "capex": s["capex"], "lcc": s["lcc"], "eac": s["eac"], "sir": s["sir"],
                         "payback": s["payback"], "co2": carbon.lifetime_co2_t(p, S)})
        res = pd.DataFrame(rows)
        best, cheapest = res.loc[res["lcc"].idxmin()], res.loc[res["capex"].idxmin()]
        if best["Measure"] != cheapest["Measure"]:
            ui.callout(f"<b>First cost misleads here:</b> {cheapest['Measure']} is cheapest to buy, but {best['Measure']} costs "
                       f"<b>{ui.inr(cheapest['lcc'] - best['lcc'])}</b> less over {p.study_period} years.", "good")
        c1, c2 = st.columns(2)
        c1.plotly_chart(charts.alt_bars(list(res["Measure"]), list(res["lcc"]), list(res["eac"])), width="stretch", config={"displayModeBar": False})
        c2.plotly_chart(charts.cumulative_lines(series), width="stretch", config={"displayModeBar": False})
        st.dataframe(pd.DataFrame({
            "Measure": res["Measure"], ui.label("capex"): res["capex"].map(ui.inr), ui.label("lcc"): res["lcc"].map(ui.inr),
            ui.label("eac"): res["eac"].map(ui.inr), ui.label("sir"): res["sir"].map(lambda v: "–" if v is None else f"{v:.2f}"),
            "Payback (yrs)": res["payback"].map(lambda v: "never" if v is None or pd.isna(v) else f"{v:.1f}"),
            "CO₂ avoided (t)": res["co2"].map(lambda v: f"{v:,.0f}")}), width="stretch", hide_index=True)
        with st.expander("Year-by-year cash flow of one measure"):
            one = st.selectbox("Measure", pick, format_func=names.get, key="cf_pick")
            disp = cashflow.yearly_table(risk.portfolio_streams(ds, [one]), p)
            for col in disp.columns:
                disp[col] = disp[col].map(("{:.4f}" if col == "Discount factor" else "{:,.0f}").format)
            st.dataframe(disp, width="stretch", height=380)
            st.caption("Costs positive, savings negative. Present worth = net cash flow × discount factor; its sum is the lifetime cost.")
        with st.expander("Carbon cost curve: cheapest tonnes of CO₂ first"):
            mev = optimizer.evaluate_measures(ds)
            macc = pd.DataFrame([{"name": e.measure.name, "co2_t": e.co2_t, "per_t": carbon.cost_per_tonne(e.lcc, e.co2_t)}
                                 for e in mev.values() if e.co2_t > 0])
            st.plotly_chart(charts.macc_chart(macc), width="stretch", config={"displayModeBar": False})
            st.caption("Green bars save money while cutting carbon; red bars cost money. Width = lifetime tonnes avoided.")
    else:
        st.info("Pick at least one measure.")

with tabs[5]:
    st.latex(r"\text{Lifetime cost (LCC)}=\sum_{t=0}^{N}\frac{C_t-S_t}{(1+d)^t}\qquad \text{Cost per year (EAC)}=\mathrm{LCC}\cdot\frac{d}{1-(1+d)^{-N}}")
    st.markdown(f"""
- **C_t** = upfront cost (year 0) + maintenance (rising each year) + parts replaced at the end of their life (inflated) − leftover value at year N.
- **S_t** = electricity saved × tariff (tariff rising, equipment slowly degrading) + water saved × water tariff. Solar splits into
  self-used kWh at the retail tariff and exported kWh at the export credit.
- **d** = {p.discount_rate*100:.1f}% (nominal), **N** = {p.study_period} years, capital recovery factor = {crf(p.discount_rate, p.study_period):.4f}.
- **Search.** One option per group (one HVAC system, one solar size…) or none; other measures on/off. That is
  **{optimizer.combo_count(ds):,}** combinations, all checked, so the answer is exact.
- **Feasible** = points ≥ {need:g} for {target}, every mandatory credit met, and solar fits the roof ({p.roof_area_m2:,.0f} m²).
- **Points.** Fixed credits add their points; energy, renewable and water credits are scored from the combined savings, so nothing is double counted.
- **Limits.** Savings are additive (no interaction between measures); point tables and prices are illustrative.
""")

with st.expander("Advanced: what to optimise for"):
    OBJ = {"net_lcc": "Lowest lifetime cost after FAR value", "lcc": "Lowest lifetime cost (ignore FAR value)"}
    st.session_state.setdefault("w_objective", obj if obj in OBJ else "lcc")
    st.radio("Objective", list(OBJ), key="w_objective", format_func=OBJ.get, horizontal=True,
             on_change=lambda: st.session_state.update(objective=st.session_state["w_objective"]))
    st.caption(f"Extra-FAR value at {target}: {ui.inr(optimizer.far_benefit(ds, target))} "
               f"({'counted' if p.use_far_benefit else 'not counted; switch it on in the sidebar'}).")

ui.next_step("trust", "Next, see whether this answer survives different interest rates and electricity prices.")
