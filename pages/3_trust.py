import streamlit as st

from core import charts, optimizer, risk, state, ui
from core.schemas import Dataset

ui.page_header(3, "Can we trust it?", "Interest rates and electricity prices will not follow our assumptions. "
               "Does the recommendation still win when they change, and where exactly would it stop winning?")
ds = ui.require_ds()
p = ds.project
target, obj, df, rec, cheap = state.recommendation(ds)
if rec is None:
    ui.unreachable(ds, df, target)

A, B = tuple(cheap["selection"]), tuple(rec["selection"])
if A == B:
    ui.callout("The cheapest-upfront and lowest-lifetime-cost mixes are identical, so there is nothing to flip. "
               "Pick another mix to test the recommendation against.", "good")
    pool = optimizer.feasible(df, ds, target).sort_values("capex")
    alt = st.selectbox("Compare against", pool.index,
                       format_func=lambda i: f"{', '.join(pool.loc[i, 'selection']) or 'nothing'} ({ui.inr(pool.loc[i, 'capex'])} upfront)")
    A = tuple(pool.loc[alt, "selection"])
    if A == B:
        st.stop()

runs = st.session_state.get("mc_runs", 3000)
seed = int(st.session_state.get("mc_seed", 42))


@st.cache_data(show_spinner="Simulating thousands of possible futures…")
def _mc(ds_json: str, a, b, runs, seed):
    return risk.monte_carlo(Dataset.model_validate_json(ds_json), a, b, runs, seed)


@st.cache_data(show_spinner=False)
def _be(ds_json: str, a, b):
    d = Dataset.model_validate_json(ds_json)
    return {k: risk.break_even(d, a, b, k) for k in risk.BREAK_EVEN_RANGES}


mc = _mc(ds.model_dump_json(), A, B, runs, seed)
be = _be(ds.model_dump_json(), A, B)

flips = []
if be["discount"] is not None:
    flips.append(f"the discount rate rises above <b>{be['discount']*100:.1f}%</b> (now {p.discount_rate*100:.1f}%)")
if be["tariff_escalation"] is not None:
    g = be["tariff_escalation"]
    flips.append("electricity prices <b>stop rising altogether</b>" if abs(g) < 0.0005 else
                 f"electricity prices grow slower than <b>{g*100:.1f}% a year</b> (now {p.tariff_escalation*100:.1f}%)")
win = mc.p_b_better
ui.verdict("Risk check · the answer",
           f"The recommendation wins in {win*100:.0f}% of {runs:,} simulated futures",
           ("It only loses if " + " or ".join(flips) + "." if flips else "It does not lose anywhere in the tested ranges.") +
           " Each future draws a different electricity price growth, discount rate, equipment price and solar output.",
           bad=win < 0.5)


def be_card(key: str, fmt, now) -> tuple:
    v = be[key]
    name = risk.BREAK_EVEN_RANGES[key][2]
    if v is None:
        return (name, "never flips", "across the tested range", "good")
    return (name, fmt(v), f"today: {now}", "")


st.markdown("##### Tipping points: where the recommendation stops beating the cheapest-upfront route")
ui.kpis([
    be_card("discount", lambda v: f"{v*100:.1f}%", f"{p.discount_rate*100:.1f}%"),
    be_card("tariff_escalation", lambda v: f"{v*100:.1f}% / yr", f"{p.tariff_escalation*100:.1f}%"),
    be_card("tariff_mult", lambda v: f"×{v:.2f} of ₹{p.grid_tariff:g}", "×1.00"),
    be_card("capex_mult", lambda v: f"×{v:.2f}", "×1.00"),
])
st.caption("The further a tipping point is from today's value, the safer the recommendation.")
st.write("")

nm = lambda sel: ", ".join(ds.measure(i).name for i in sel) or "nothing"  # noqa: E731
t1, t2, t3 = st.tabs(["Simulated futures", "What matters most", "Interest-rate sweep"])
with t1:
    ui.kpis([
        ("Recommended wins in", f"{win*100:.0f}% of runs", f"{runs:,} simulated futures", "brand" if win > 0.5 else "bad"),
        ("Recommended, typical lifetime cost", ui.inr(mc.pct_b["P50"]), f"range {ui.inr(mc.pct_b['P10'])} to {ui.inr(mc.pct_b['P90'])}", "",
         "Median (P50); the range is P10 to P90, i.e. 8 in 10 futures fall inside it."),
        ("Cheapest-upfront, typical lifetime cost", ui.inr(mc.pct_a["P50"]), f"range {ui.inr(mc.pct_a['P10'])} to {ui.inr(mc.pct_a['P90'])}", ""),
        ("Chance the recommended mix pays for itself", f"{mc.p_b_saves*100:.0f}%", f"cheapest-upfront: {mc.p_a_saves*100:.0f}%", ""),
    ])
    st.plotly_chart(charts.mc_histogram(mc.lcc_a, mc.lcc_b, "Cheapest upfront", "Recommended"), width="stretch", config={"displayModeBar": False})
    st.caption("**What this means:** the further left a hill sits, the cheaper that route is over its life. Where the hills barely overlap, "
               "the choice is robust.")
with t2:
    which = st.radio("Mix", ["Recommended", "Cheapest upfront"], horizontal=True)
    tor = risk.tornado(ds, B if which == "Recommended" else A)
    st.plotly_chart(charts.tornado_chart(tor), width="stretch", config={"displayModeBar": False})
    top = tor.sort_values("swing", ascending=False)["parameter"].head(2).tolist()
    st.caption(f"**What this means:** {top[0]} and {top[1]} move the answer most, so they are the inputs to verify with real data first. "
               "Each bar changes one assumption at a time.")
with t3:
    sw = risk.discount_sweep(ds, A, B)
    st.plotly_chart(charts.discount_sweep_chart(sw, "Cheapest upfront: " + nm(A)[:40], "Recommended: " + nm(B)[:40], be["discount"]),
                    width="stretch", config={"displayModeBar": False})
    st.caption("**What this means:** a higher discount rate makes future savings worth less today. Where the lines cross, the cheaper-upfront "
               "route would start to win.")

with st.expander("Advanced: simulation settings"):
    m1, m2 = st.columns(2)
    m1.select_slider("Simulation runs", [1000, 3000, 5000, 10000], value=runs, key="mc_runs")
    m2.number_input("Random seed (same seed = same numbers)", 0, 10**6, seed, key="mc_seed")
    st.caption(f"Draws: electricity price growth ~ Normal({p.tariff_escalation*100:.1f}%, {p.tariff_escalation_sd*100:.1f} pp); discount rate ~ "
               "triangular (−2 / +3 pp); equipment prices ~ triangular (−10% / +20%); solar output ~ Normal(100%, 7%).")

ui.next_step("report", "Convinced? Download the decision report for the owner.")
