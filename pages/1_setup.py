from pathlib import Path

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from core import charts, extract, state, ui
from core.io import cross_check, measures_to_df, rows_to_models
from core.schemas import Component, Dataset, Measure, Project

ui.page_header(1, "Set up the project", "The building, the money assumptions and the green measures you could build. "
               "The demo is already filled in; change anything and every result recomputes.")
ds = ui.require_ds()
p = ds.project
levels = [lv.level for lv in sorted(ds.levels, key=lambda x: x.rank)]
SAMPLES = Path(__file__).resolve().parent.parent / "sample_quotes"
credit_ids = [""] + [c.credit_id for c in ds.credits]

# suggested engineering inputs for the three demo quotes (a real user would enter their own)
HINTS = {
    "SunRise_Solar_100kWp_quote.pdf": dict(measure_id="PV_100_SUNRISE", kind="renewable", group="PV", credit="EE-C3", pts=0, kwh=0, water=0, base=0, base_om=0, degr=0.006),
    "CoolAir_VRF_120TR_quote.pdf": dict(measure_id="HVAC_VRF_COOLAIR", kind="efficiency", group="HVAC", credit="EE-C2", pts=0, kwh=72000, water=0, base=13200000, base_om=220000, degr=0.005),
    "ClearView_DGU_Glazing_quote.pdf": dict(measure_id="GLZ_CLEARVIEW", kind="efficiency", group="GLAZING", credit="IEQ-C1", pts=2, kwh=54000, water=0, base=7700000, base_om=0, degr=0.0),
}


def commit(measures: list[Measure], comps: list[Component]) -> list[str]:
    try:
        new = Dataset(project=ds.project, measures=measures, components=comps, credits=ds.credits, levels=ds.levels)
    except Exception as e:  # pydantic cross-field error
        return [str(e)]
    errs = cross_check(new)
    if not errs:
        state.set_ds(new)
    return errs


t_proj, t_meas, t_quote = st.tabs(["Building & money", "Measures", "Import a vendor quote (AI)"])

with t_proj:
    with st.form("project_form"):
        a, b, c = st.columns(3)
        with a:
            st.markdown("##### Building & site")
            name = st.text_input("Project name", p.name)
            city = st.text_input("City", p.city)
            btype = st.text_input("Building type", p.building_type)
            plot = st.number_input("Plot area (m²)", 1.0, value=float(p.plot_area_m2), step=100.0)
            fsi = st.number_input("FSI / FAR", 0.1, value=float(p.fsi), step=0.1)
            bua = st.number_input("Built-up area (m²)", 1.0, value=float(p.bua_m2), step=500.0)
            roof = st.number_input("Usable roof area (m²)", 0.0, value=float(p.roof_area_m2), step=100.0)
            en = st.number_input("Baseline energy (kWh/yr)", 1.0, value=float(p.baseline_energy_kwh), step=50000.0)
            wa = st.number_input("Baseline water (kL/yr)", 0.0, value=float(p.baseline_water_kl), step=500.0)
        with b:
            st.markdown("##### Finance & tariffs")
            n = st.slider("Study period (years)", 10, 40, int(p.study_period))
            d = st.number_input("Discount rate (%)", 1.0, 25.0, p.discount_rate * 100, 0.5)
            inf = st.number_input("General inflation (%)", 0.0, 15.0, p.inflation * 100, 0.5)
            tar = st.number_input("Grid tariff (₹/kWh)", 0.5, value=float(p.grid_tariff), step=0.5)
            esc = st.number_input("Tariff escalation (% / yr)", -3.0, 15.0, p.tariff_escalation * 100, 0.5)
            sd = st.number_input("Escalation uncertainty, 1 sd (pp)", 0.0, 8.0, p.tariff_escalation_sd * 100, 0.5)
            exp = st.number_input("Solar export credit (₹/kWh)", 0.0, value=float(p.export_tariff), step=0.1)
            wt = st.number_input("Water + sewage tariff (₹/kL)", 0.0, value=float(p.water_tariff), step=5.0)
            wesc = st.number_input("Water tariff escalation (% / yr)", 0.0, 15.0, p.water_escalation * 100, 0.5)
        with c:
            st.markdown("##### IGBC & solar")
            base = st.number_input("Points already earned by base design", 0.0, 100.0, float(p.base_points), 1.0)
            far_v = st.number_input("Net value of extra built-up area (₹/m²)", 0.0, value=float(p.far_net_value_per_m2), step=1000.0)
            far = {lv: st.number_input(f"FAR bonus for {lv} (%)", 0.0, 25.0, float(p.far_bonus_pct.get(lv, 0.0)), 0.5)
                   for lv in levels if lv != levels[0]}
            yld = st.number_input("Solar yield (kWh/kWp/yr)", 100.0, value=float(p.pv_yield_kwh_per_kwp), step=50.0)
            selfc = st.slider("Solar self-consumption share", 0.0, 1.0, float(p.pv_self_consumption), 0.05)
            ef = st.number_input("Grid emission factor (tCO₂/MWh)", 0.0, 1.5, float(p.grid_emission_factor), 0.01)
        submitted = st.form_submit_button("Apply changes", type="primary", icon=":material/check:")

    if submitted:
        try:
            newp = Project(name=name, city=city, building_type=btype, plot_area_m2=plot, fsi=fsi, bua_m2=bua, roof_area_m2=roof,
                           baseline_energy_kwh=en, baseline_water_kl=wa, study_period=n, discount_rate=d / 100, inflation=inf / 100,
                           grid_tariff=tar, tariff_escalation=esc / 100, tariff_escalation_sd=sd / 100, export_tariff=exp,
                           export_escalation=p.export_escalation, water_tariff=wt, water_escalation=wesc / 100,
                           pv_yield_kwh_per_kwp=yld, pv_self_consumption=selfc, pv_area_per_kwp_m2=p.pv_area_per_kwp_m2,
                           grid_emission_factor=ef, target_level=p.target_level, base_points=base, far_bonus_pct=far,
                           far_net_value_per_m2=far_v, use_far_benefit=p.use_far_benefit)
            state.set_ds(Dataset(**{**ds.model_dump(), "project": newp.model_dump()}))
            st.success("Project updated. All downstream results will recompute.")
            st.rerun()
        except ValidationError as e:
            st.error("Please fix:\n\n" + "\n".join(f"- **{'.'.join(map(str, x['loc']))}**: {x['msg']}" for x in e.errors()))

    st.write("")
    left, right = st.columns([1.3, 1])
    with left:
        st.plotly_chart(charts.tariff_preview(p.grid_tariff, p.tariff_escalation, p.tariff_escalation_sd, p.study_period),
                        width="stretch", config={"displayModeBar": False})
    with right:
        ui.kpis([("Permissible built-up", f"{p.permissible_bua_m2:,.0f} m²", f"plot × FSI {p.fsi}", ""),
                 ("Electricity bill today", ui.inr(p.baseline_energy_kwh * p.grid_tariff), "per year: baseline kWh × tariff", "brand")], cols=1)
        st.write("")
        ui.callout("Percent inputs are annual rates. The <b>target level</b> and whether to <b>count FAR value</b> are set in the sidebar. "
                   "FAR value is the <i>net</i> gain per extra m² after construction cost, counted once at year 0.")

with t_meas:
    df = measures_to_df(ds.measures)
    cfg = {
        "measure_id": st.column_config.TextColumn("ID", required=True, width="small"),
        "name": st.column_config.TextColumn("Name", required=True, width="medium"),
        "exclusive_group": st.column_config.TextColumn("Exclusive group", help="Only one option per group is ever chosen. Blank = independent."),
        "kind": st.column_config.SelectboxColumn("Kind", options=["efficiency", "renewable", "water", "none"], required=True),
        "credit_id": st.column_config.SelectboxColumn("IGBC credit", options=credit_ids),
        "points_fixed": st.column_config.NumberColumn("Fixed pts", help="Points for 'fixed' credits; threshold credits are scored from savings."),
        "capex": st.column_config.NumberColumn("Capex (₹)", format="%d"),
        "subsidy": st.column_config.NumberColumn("Subsidy (₹)", format="%d"),
        "om_annual": st.column_config.NumberColumn("O&M / yr (₹)", format="%d"),
        "om_escalation": st.column_config.NumberColumn("O&M esc.", format="%.3f"),
        "energy_saving_kwh": st.column_config.NumberColumn("Energy saved (kWh/yr)", format="%d"),
        "kwp": st.column_config.NumberColumn("kWp"),
        "water_saving_kl": st.column_config.NumberColumn("Water saved (kL/yr)", format="%d"),
        "degradation": st.column_config.NumberColumn("Degradation /yr", format="%.3f"),
    }
    edited = st.data_editor(df, column_config=cfg, num_rows="dynamic", width="stretch", hide_index=True, key="lib_editor", height=400)
    c1, c2 = st.columns([1.3, 4])
    if c1.button("Apply measure changes", type="primary", icon=":material/check:"):
        ms, errs = rows_to_models(edited.dropna(how="all"), Measure, "Measures")
        if not errs:
            errs = commit(ms, ds.components)
        if errs:
            st.error("Not applied:\n\n" + "\n".join(f"- {e}" for e in errs))
        else:
            st.success(f"Library updated: {len(ms)} measures.")
            st.rerun()
    c2.caption("Tip: costs are **incremental** to the code-minimum baseline, so a VRF row holds *VRF cost minus the split ACs it replaces*.")
    with st.expander("Replacement parts and their lives"):
        cdf = pd.DataFrame([c.model_dump() for c in ds.components])
        ce = st.data_editor(cdf, num_rows="dynamic", width="stretch", hide_index=True, key="comp_editor", column_config={
            "measure_id": st.column_config.SelectboxColumn("Measure", options=[m.measure_id for m in ds.measures], required=True),
            "cost": st.column_config.NumberColumn("Cost today (₹)", format="%d"),
            "life_years": st.column_config.NumberColumn("Life (years)")})
        if st.button("Apply parts", icon=":material/check:"):
            cs, errs = rows_to_models(ce.dropna(how="all"), Component, "Components")
            if not errs:
                errs = commit(ds.measures, cs)
            if errs:
                st.error("Not applied:\n\n" + "\n".join(f"- {e}" for e in errs))
            else:
                st.success("Parts updated.")
                st.rerun()
        st.caption("Each component is re-bought at its life interval (inflated), and its unused life at the end of the study period is credited back as residual value.")
    with st.expander("IGBC credit tables (reference)"):
        ui.callout("<b>Illustrative point tables.</b> Replace data/igbc_credits.csv and data/igbc_levels.csv with values from the official IGBC reference guide (see PROJECT_LOG Q-002).", "warn")
        st.dataframe(pd.DataFrame([{**c.model_dump(), "thresholds": " | ".join(f"≥{a:g}% → {b:g}" for a, b in c.thresholds)} for c in ds.credits]),
                     width="stretch", hide_index=True)
        st.dataframe(pd.DataFrame([lv.model_dump() for lv in ds.levels]), width="stretch", hide_index=True)

with t_quote:
    st.markdown("Upload a vendor quotation PDF. **Claude** reads it when `ANTHROPIC_API_KEY` is set; otherwise a built-in offline parser is used. "
                "You always review the draft before anything is added.")
    src = st.radio("Source", ["Sample quotes", "Upload my own"], horizontal=True)
    file, fname = None, ""
    if src == "Sample quotes":
        pdfs = sorted(SAMPLES.glob("*.pdf"))
        if not pdfs:
            st.warning("No sample PDFs found. Run `python scripts/make_dummy_data.py`.")
        else:
            pick = st.selectbox("Sample", [p.name for p in pdfs])
            file, fname = str(SAMPLES / pick), pick
    else:
        up = st.file_uploader("Quotation PDF", type="pdf")
        if up:
            file, fname = up, up.name
    if file and st.button("Extract fields", type="primary", icon=":material/auto_awesome:"):
        with st.spinner("Reading quotation…"):
            try:
                st.session_state["quote"] = (extract.extract(file), fname)
            except Exception as e:
                st.session_state.pop("quote", None)
                st.error(f"Could not read that PDF: {e}")

    if "quote" in st.session_state:
        q, qname = st.session_state["quote"]
        st.markdown(f"##### Draft from `{qname}` · parsed by **{q.method}**")
        for n in q.notes:
            st.caption("ℹ️ " + n)
        h = HINTS.get(qname, dict(measure_id="NEW_MEASURE", kind="efficiency", group="", credit="", pts=0, kwh=0, water=0, base=0, base_om=0, degr=0.0))
        with st.form("quote_form"):
            a, b = st.columns(2)
            with a:
                st.markdown("**Read from the quote**")
                vendor = st.text_input("Vendor", q.vendor)
                item = st.text_input("Item", q.item)
                cap = st.text_input("Capacity", q.capacity)
                capex = st.number_input("Quoted price (₹)", 0.0, value=float(q.capex or 0), step=100000.0)
                om = st.number_input("Annual maintenance (₹/yr)", 0.0, value=float(q.om_annual or 0), step=10000.0)
                comp_name = st.text_input("Replaceable component", q.component_name)
                comp_cost = st.number_input("Component cost (₹)", 0.0, value=float(q.component_cost or 0), step=50000.0)
                comp_life = st.number_input("Component life (years)", 0.0, value=float(q.component_life_years or 0), step=1.0)
            with b:
                st.markdown("**Your engineering inputs** (a quote doesn't state these)")
                mid = st.text_input("Measure ID", h["measure_id"])
                kinds = ["efficiency", "renewable", "water", "none"]
                kind = st.selectbox("Kind", kinds, index=kinds.index(h["kind"]))
                grp = st.text_input("Exclusive group (blank = independent)", h["group"])
                cr = st.selectbox("IGBC credit", credit_ids, index=credit_ids.index(h["credit"]) if h["credit"] in credit_ids else 0)
                pts = st.number_input("Fixed points", 0.0, value=float(h["pts"]), step=1.0)
                kwp = st.number_input("kWp (solar only)", 0.0, value=extract.capacity_kwp(cap) if kind == "renewable" else 0.0, step=10.0)
                kwh = st.number_input("Energy saved (kWh/yr)", 0.0, value=float(h["kwh"]), step=5000.0)
                wtr = st.number_input("Water saved (kL/yr)", 0.0, value=float(h["water"]), step=100.0)
                base = st.number_input("Baseline system cost to deduct (₹)", 0.0, value=float(h["base"]), step=100000.0,
                                       help="e.g. the split ACs a VRF replaces, so capex becomes incremental")
                base_om = st.number_input("Baseline maintenance to deduct (₹/yr)", 0.0, value=float(h["base_om"]), step=10000.0)
            go = st.form_submit_button("Add to library", type="primary", icon=":material/add:")
        if go:
            q2 = q.model_copy(update=dict(vendor=vendor, item=item, capacity=cap, capex=capex, om_annual=om, component_name=comp_name,
                                          component_cost=comp_cost or None, component_life_years=comp_life or None))
            try:
                m, comps = extract.to_measure(q2, measure_id=mid.strip(), kind=kind, exclusive_group=grp.strip() or None, credit_id=cr,
                                              points_fixed=pts, energy_saving_kwh=kwh, water_saving_kl=wtr, kwp=kwp, degradation=h["degr"],
                                              source=f"quote:{qname}", baseline_cost=base, baseline_om=base_om)
            except Exception as e:
                st.error(f"Invalid measure: {e}")
            else:
                if any(x.measure_id == m.measure_id for x in ds.measures):
                    st.error(f"A measure with ID {m.measure_id} already exists; change the ID.")
                else:
                    errs = commit([*ds.measures, m], [*ds.components, *comps])
                    if errs:
                        st.error("Not added:\n\n" + "\n".join(f"- {e}" for e in errs))
                    else:
                        st.success(f"Added **{m.name}** (incremental capex {ui.inr(m.capex)}). It is now in the Measures tab and the recommendation has been recomputed.")
                        st.session_state.pop("quote", None)
                        st.rerun()

ui.next_step("rec", "Happy with the inputs? The optimizer searches every combination of measures.")
