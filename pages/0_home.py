import streamlit as st

from core import state, ui

ui.hero("CM 617 · Topic 6 · Life Cycle Cost Analysis",
        "Reach your IGBC target at the lowest lifetime cost",
        "Most Indian projects pick green credits by cheapest upfront price. GreenLCC costs every measure over "
        "25 years of energy, maintenance, replacement and tariff risk, then finds the mix that earns the rating for the least money overall.")

ds = state.get_ds()
left, right = st.columns([1, 1.5], gap="large")
with left:
    st.subheader("Start here")
    if st.button("Try the Pune demo", type="primary", icon=":material/rocket_launch:", width="stretch"):
        errs = state.load_demo()
        if errs:
            st.error("Could not load the demo data:\n\n" + "\n".join(f"- {e}" for e in errs))
        else:
            st.rerun()
    up = st.file_uploader("…or open a saved project (.json)", type="json",
                          help="The project file you saved from the Report page. It holds the building, measures and IGBC tables.")
    if up is not None and st.session_state.get("_opened") != up.file_id:
        errs = state.open_bundle(up.getvalue())
        if errs:
            st.error("Could not open that file:\n\n" + "\n".join(f"- {e}" for e in errs))
        else:
            st.session_state["_opened"] = up.file_id
            st.rerun()
    st.caption("All demo data is **illustrative**: dummy prices, tariffs and IGBC point tables for a prototype.")

with right:
    if ds is None:
        st.subheader("How it works")
        st.markdown("""
1. **Set up**: the building, electricity tariff, money assumptions and a library of green measures (AI can read vendor quotes).
2. **Recommendation**: the cheapest-over-its-life way to reach Silver, Gold or Platinum, next to the cheapest-upfront way.
3. **Can we trust it?**: does the answer survive higher interest rates or slower tariff growth?
4. **Report**: one PDF for the owner, one Excel for the details, and a project file to reopen later.
""")
    else:
        target, obj, df, rec, cheap = state.recommendation(ds)
        st.subheader(ds.project.name)
        if rec is None:
            ui.verdict("The answer", f"{target} is not reachable with this library",
                       "Pick a lower target in the sidebar or add measures on the Set up page.", bad=True)
        else:
            gain = cheap["lcc"] - rec["lcc"]
            if tuple(rec["selection"]) == tuple(cheap["selection"]):
                head = f"{rec['level']} with {rec['points']:g} points, and the cheapest route is also the best one"
                sub = f"Lifetime cost {ui.inr(rec['lcc'])} over {ds.project.study_period} years."
            else:
                head = f"{rec['level']} for {ui.inr(gain)} less over {ds.project.study_period} years"
                sub = (f"Spend {ui.inr(rec['capex'] - cheap['capex'])} more upfront than the cheapest {target} route; "
                       f"electricity savings pay that back many times. {rec['points']:g} points, {rec['co2_t']:,.0f} t CO₂ avoided.")
            ui.verdict("The answer", head, sub)
        st.page_link(ui.PAGES["rec"][0], label="See why →", icon=":material/workspace_premium:")

st.write("")
st.markdown("##### Why this tool exists")
c1, c2, c3 = st.columns(3)
c1.markdown(ui.card("First-cost bias", "Green buildings cost 2–17% more upfront, yet lifetime savings often exceed 20% of construction cost. L1 tendering hides this.", "L1"), unsafe_allow_html=True)
c2.markdown(ui.card("Tariff & policy risk", "Commercial tariffs keep rising while net-metering export credit sits near ₹2.82/kWh in Maharashtra. One payback number hides that risk.", "₹ risk"), unsafe_allow_html=True)
c3.markdown(ui.card("Credits chased blindly", "IGBC levels earn marketing value and FAR bonuses, but the cheapest points are rarely the cheapest over the building's life.", "IGBC"), unsafe_allow_html=True)

if ds is not None:
    ui.next_step("setup", "Check or change the assumptions first, or skip straight to the recommendation from the sidebar.")
