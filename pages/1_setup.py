from pathlib import Path

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from core import charts, extract, state, ui
from core.finance import real_rate
from core.io import MEASURE_COLUMNS, cross_check, measures_to_df, rows_to_models
from core.schemas import Dataset, Measure, Project

ui.page_header(1, "Set up the project", "The building, the money assumptions and the green measures you could build. "
               "The demo is already filled in; change anything and every result recomputes.")
ds = ui.require_ds()
p = ds.project
SAMPLES = Path(__file__).resolve().parent.parent / "sample_quotes"
credit_ids = [""] + [c.credit_id for c in ds.credits]

# suggested engineering inputs for the three demo quotes (a real user would enter their own)
HINTS = {
    "SunRise_Solar_150kWp_quote.pdf": dict(measure_id="PV_150_SUNRISE", group="PV", credit="EE-C3", pts=0, kwh=0, water=0, life=25,
                                           base=0, base_om=0, degr=0.005),
    "CoolAir_VRF_350TR_quote.pdf": dict(measure_id="HVAC_VRF_COOLAIR", group="HVAC", credit="EE-C2", pts=0, kwh=248000, water=0, life=15,
                                        base=15750000, base_om=350000, degr=0.005),
    "ClearView_LowE_Glazing_quote.pdf": dict(measure_id="GLZ_CLEARVIEW", group="GLAZING", credit="IEQ-C1", pts=2, kwh=69000, water=0,
                                             life=30, base=10500000, base_om=0, degr=0.0),
}


def commit(measures: list[Measure]) -> list[str]:
    new = ds.model_copy(update={"measures": measures})
    errs = cross_check(new)
    if not errs:
        state.set_ds(new)
    return errs


t_proj, t_meas, t_quote = st.tabs(["Building & money", "Measures", "Import a vendor quote (AI)"])

with t_proj:
    with st.form("project_form"):
        a, b, c = st.columns(3)
        with a:
            st.markdown("##### Building")
            name = st.text_input("Project name", p.name)
            city = st.text_input("City", p.city)
            roof = st.number_input("Usable roof area (m²)", 0.0, value=float(p.roof_area_m2), step=100.0, help="Caps rooftop solar at 10 m² per kWp.")
            en = st.number_input("Baseline electricity (kWh/yr)", 1.0, value=float(p.baseline_energy_kwh), step=50000.0,
                                 help="Code-minimum building; IGBC energy % are measured against it.")
            wa = st.number_input("Baseline water (kL/yr)", 0.0, value=float(p.baseline_water_kl), step=500.0)
            base = st.number_input("IGBC points already earned by the base design", 0.0, 100.0, float(p.base_points), 1.0)
        with b:
            st.markdown("##### Money")
            n = st.slider("Study period N (years)", 10, 40, int(p.study_period), help="One planning horizon for every alternative (Ch 5).")
            d = st.number_input("MARR, nominal (%)", 1.0, 25.0, p.discount_rate * 100, 0.5, help=ui.tip("marr"))
            inf = st.number_input("General inflation (%)", 0.0, 15.0, p.inflation * 100, 0.5,
                                  help="Escalates O&M and re-purchase prices.")
            st.caption(f"Real MARR (Fisher): **{real_rate(p.discount_rate, p.inflation)*100:.2f}%** = (1 + MARR) ÷ (1 + inflation) − 1. "
                       "The model works in nominal ₹, so it discounts at the nominal MARR.")
        with c:
            st.markdown("##### Tariffs & solar")
            tar = st.number_input("Grid tariff, year 1 (₹/kWh)", 0.5, value=float(p.grid_tariff), step=0.5)
            esc = st.number_input("Tariff escalation (% / yr)", -3.0, 15.0, p.tariff_escalation * 100, 0.5)
            sd = st.number_input("Escalation uncertainty, 1 sd (pp)", 0.0, 8.0, p.tariff_escalation_sd * 100, 0.5,
                                 help="Used by the Monte Carlo on the risk page.")
            exp = st.number_input("Solar export credit (₹/kWh)", 0.0, value=float(p.export_tariff), step=0.1)
            wt = st.number_input("Water + sewage tariff (₹/kL)", 0.0, value=float(p.water_tariff), step=5.0)
            wesc = st.number_input("Water tariff escalation (% / yr)", 0.0, 15.0, p.water_escalation * 100, 0.5)
            yld = st.number_input("Solar yield (kWh/kWp/yr)", 100.0, value=float(p.pv_yield_kwh_per_kwp), step=50.0)
            selfc = st.slider("Solar self-consumption share", 0.0, 1.0, float(p.pv_self_consumption), 0.05)
            ef = st.number_input("Grid emission factor (tCO₂/MWh)", 0.0, 1.5, float(p.grid_emission_factor), 0.01)
        submitted = st.form_submit_button("Apply changes", type="primary", icon=":material/check:")

    if submitted:
        try:
            newp = Project(name=name, city=city, roof_area_m2=roof, baseline_energy_kwh=en, baseline_water_kl=wa, study_period=n,
                           discount_rate=d / 100, inflation=inf / 100, grid_tariff=tar, tariff_escalation=esc / 100,
                           tariff_escalation_sd=sd / 100, export_tariff=exp, water_tariff=wt, water_escalation=wesc / 100,
                           pv_yield_kwh_per_kwp=yld, pv_self_consumption=selfc, grid_emission_factor=ef,
                           target_level=p.target_level, base_points=base)
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
        ui.kpis([("Electricity bill today", ui.inr(p.baseline_energy_kwh * p.grid_tariff), "per year: baseline kWh × tariff", "brand"),
                 ("Roof allows up to", f"{p.roof_kwp_cap:,.0f} kWp", "of rooftop solar", "")], cols=1)
        st.write("")
        ui.callout("Percent inputs are annual rates. The <b>target level</b> is set in the sidebar. "
                   "Every input, its unit and its source is also in the input workbook (download it from Home).")

with t_meas:
    df = measures_to_df(ds.measures)
    help_of = {f: f"{mean}" + (f" ({u})" if u else "") for f, _, u, mean in MEASURE_COLUMNS}
    num = lambda f, lab, fmt="%d": st.column_config.NumberColumn(lab, format=fmt, help=help_of[f])  # noqa: E731
    cfg = {
        "measure_id": st.column_config.TextColumn("ID", required=True, width="small", help=help_of["measure_id"]),
        "name": st.column_config.TextColumn("Name", required=True, width="medium"),
        "exclusive_group": st.column_config.TextColumn("Group", help=help_of["exclusive_group"]),
        "credit_id": st.column_config.SelectboxColumn("IGBC credit", options=credit_ids, help=help_of["credit_id"]),
        "points_fixed": num("points_fixed", "Fixed pts", "%g"),
        "capex": num("capex", "Capex (₹)"),
        "life_years": num("life_years", "Life (yrs)", "%g"),
        "om_annual": num("om_annual", "O&M / yr (₹)"),
        "energy_saving_kwh": num("energy_saving_kwh", "Energy saved (kWh/yr)"),
        "kwp": num("kwp", "Solar kWp", "%g"),
        "water_saving_kl": num("water_saving_kl", "Water saved (kL/yr)"),
        "degradation": num("degradation", "Degradation (fraction/yr)", "%.3f"),
        "part_name": st.column_config.TextColumn("Replaceable part", help=help_of["part_name"]),
        "part_cost": num("part_cost", "Part cost (₹)"),
        "part_life": num("part_life", "Part life (yrs)", "%g"),
        "description": st.column_config.TextColumn("Notes / basis", width="large"),
    }
    edited = st.data_editor(df, column_config=cfg, num_rows="dynamic", width="stretch", hide_index=True, key="lib_editor", height=440)
    c1, c2 = st.columns([1.3, 4])
    if c1.button("Apply measure changes", type="primary", icon=":material/check:"):
        ms, errs = rows_to_models(edited.dropna(how="all"), Measure, "Measures")
        if not errs:
            errs = commit(ms)
        if errs:
            st.error("Not applied:\n\n" + "\n".join(f"- {e}" for e in errs))
        else:
            st.success(f"Library updated: {len(ms)} measures.")
            st.rerun()
    c2.caption("Costs and savings are **incremental** to the code-minimum option: a VRF row holds *VRF price minus the split ACs it replaces*. "
               "A measure is re-bought when its life ends inside the study period; its replaceable part every part life. "
               "Unused life at the end comes back as salvage value.")
    with st.expander("IGBC credit tables (reference)"):
        ui.callout("<b>Illustrative point tables.</b> Replace the IGBC_credits and IGBC_levels sheets of the input workbook with values from "
                   "the official IGBC reference guide (see PROJECT_LOG Q-002).", "warn")
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
            pick = st.selectbox("Sample", [x.name for x in pdfs])
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
        for note in q.notes:
            st.caption("ℹ️ " + note)
        h = HINTS.get(qname, dict(measure_id="NEW_MEASURE", group="", credit="", pts=0, kwh=0, water=0, life=15, base=0, base_om=0, degr=0.0))
        with st.form("quote_form"):
            a, b = st.columns(2)
            with a:
                st.markdown("**Read from the quote**")
                vendor = st.text_input("Vendor", q.vendor)
                item = st.text_input("Item", q.item)
                cap = st.text_input("Capacity", q.capacity)
                capex = st.number_input("Quoted price (₹)", 0.0, value=float(q.capex or 0), step=100000.0)
                om = st.number_input("Annual maintenance (₹/yr)", 0.0, value=float(q.om_annual or 0), step=10000.0)
                comp_name = st.text_input("Replaceable part", q.component_name)
                comp_cost = st.number_input("Part cost (₹)", 0.0, value=float(q.component_cost or 0), step=50000.0)
                comp_life = st.number_input("Part life (years)", 0.0, value=float(q.component_life_years or 0), step=1.0)
            with b:
                st.markdown("**Your engineering inputs** (a quote doesn't state these)")
                mid = st.text_input("Measure ID", h["measure_id"])
                grp = st.text_input("Group (blank = independent)", h["group"])
                cr = st.selectbox("IGBC credit", credit_ids, index=credit_ids.index(h["credit"]) if h["credit"] in credit_ids else 0)
                pts = st.number_input("Fixed points", 0.0, value=float(h["pts"]), step=1.0)
                life = st.number_input("Service life (years)", 1.0, value=float(h["life"]), step=1.0)
                kwp = st.number_input("kWp (solar only)", 0.0, value=extract.capacity_kwp(cap), step=10.0)
                kwh = st.number_input("Energy saved (kWh/yr)", 0.0, value=float(h["kwh"]), step=5000.0)
                wtr = st.number_input("Water saved (kL/yr)", 0.0, value=float(h["water"]), step=100.0)
                base_c = st.number_input("Baseline system cost to deduct (₹)", 0.0, value=float(h["base"]), step=100000.0,
                                         help="e.g. the split ACs a VRF replaces, so capex becomes incremental")
                base_om = st.number_input("Baseline maintenance to deduct (₹/yr)", 0.0, value=float(h["base_om"]), step=10000.0)
            go = st.form_submit_button("Add to library", type="primary", icon=":material/add:")
        if go:
            q2 = q.model_copy(update=dict(vendor=vendor, item=item, capacity=cap, capex=capex, om_annual=om, component_name=comp_name,
                                          component_cost=comp_cost or None, component_life_years=comp_life or None))
            try:
                m = extract.to_measure(q2, measure_id=mid.strip(), life_years=life, exclusive_group=grp.strip() or None, credit_id=cr,
                                       points_fixed=pts, energy_saving_kwh=kwh, water_saving_kl=wtr, kwp=kwp, degradation=h["degr"],
                                       baseline_cost=base_c, baseline_om=base_om)
            except Exception as e:
                st.error(f"Invalid measure: {e}")
            else:
                if any(x.measure_id == m.measure_id for x in ds.measures):
                    st.error(f"A measure with ID {m.measure_id} already exists; change the ID.")
                else:
                    errs = commit([*ds.measures, m])
                    if errs:
                        st.error("Not added:\n\n" + "\n".join(f"- {e}" for e in errs))
                    else:
                        st.success(f"Added **{m.name}** (incremental capex {ui.inr(m.capex)}). It is now in the Measures tab and the recommendation has been recomputed.")
                        st.session_state.pop("quote", None)
                        st.rerun()

ui.next_step("rec", "Happy with the inputs? The optimizer searches every combination of measures.")
