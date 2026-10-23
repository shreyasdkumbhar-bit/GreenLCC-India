"""Shared Streamlit UI pieces: styling, KPI cards, banners, formatting."""
from __future__ import annotations

import html

import streamlit as st

from . import state

GREEN, DEEP, MINT, INK, INK2, BORDER = "#1E7B4F", "#0f4d33", "#e3f1e8", "#0b0b0b", "#52514e", "#e1e0d9"

CSS = f"""
<style>
:root {{ --green:{GREEN}; --deep:{DEEP}; --mint:{MINT}; --ink:{INK}; --ink2:{INK2}; --border:{BORDER}; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1280px; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}
[data-testid="stSidebar"] {{ border-right: 1px solid var(--border); }}
[data-testid="stSidebarNav"] a {{ border-radius: 10px; }}
.brand {{ display:flex; align-items:center; gap:.6rem; padding:.2rem 0 .8rem 0; }}
.brand .logo {{ width:34px; height:34px; border-radius:10px; background:linear-gradient(135deg,var(--green),#2fa36b);
  display:flex; align-items:center; justify-content:center; color:white; font-weight:700; }}
.brand .name {{ font-weight:700; font-size:1.05rem; line-height:1.1; }}
.brand .sub {{ font-size:.72rem; color:var(--ink2); }}
.hero {{ background: linear-gradient(120deg, var(--deep) 0%, var(--green) 55%, #38b27a 100%); color:white;
  padding: 2.2rem 2.4rem; border-radius: 20px; margin-bottom: 1.4rem; box-shadow: 0 10px 30px rgba(15,77,51,.18); }}
.hero .kicker {{ text-transform:uppercase; letter-spacing:.14em; font-size:.72rem; opacity:.85; margin-bottom:.5rem; }}
.hero h1 {{ color:white; font-size:2.3rem; margin:0 0 .6rem 0; line-height:1.15; }}
.hero p {{ font-size:1.05rem; opacity:.93; margin:0; max-width:780px; }}
.pagehead {{ margin-bottom:1.1rem; }}
.pagehead .step {{ display:inline-block; background:var(--mint); color:var(--deep); border-radius:999px; padding:.15rem .7rem;
  font-size:.74rem; font-weight:700; letter-spacing:.04em; margin-bottom:.4rem; }}
.pagehead h2 {{ margin:0; font-size:1.7rem; }}
.pagehead p {{ margin:.25rem 0 0 0; color:var(--ink2); }}
.card {{ background:white; border:1px solid var(--border); border-radius:16px; padding:1.1rem 1.3rem; height:100%;
  box-shadow: 0 1px 2px rgba(0,0,0,.03); }}
.card h4 {{ margin:0 0 .35rem 0; font-size:1rem; }}
.card p {{ margin:0; color:var(--ink2); font-size:.92rem; line-height:1.45; }}
.card .big {{ font-size:1.7rem; font-weight:700; color:var(--deep); margin-bottom:.15rem; }}
.kpi {{ background:white; border:1px solid var(--border); border-radius:16px; padding:.95rem 1.15rem;
  box-shadow: 0 1px 2px rgba(0,0,0,.03); height:100%; }}
.kpi .l {{ font-size:.72rem; text-transform:uppercase; letter-spacing:.08em; color:var(--ink2); font-weight:600; }}
.kpi .v {{ font-size:1.65rem; font-weight:700; margin-top:.15rem; line-height:1.15; }}
.kpi .s {{ font-size:.82rem; color:var(--ink2); margin-top:.2rem; }}
.kpi .q {{ cursor:help; color:var(--green); font-size:.8rem; }}
.verdict {{ background:linear-gradient(180deg,#ffffff,var(--mint)); border:1px solid #bfdcca; border-radius:18px; padding:1.1rem 1.4rem;
  margin:.2rem 0 1rem 0; }}
.verdict .t {{ font-size:.72rem; text-transform:uppercase; letter-spacing:.1em; color:var(--deep); font-weight:700; }}
.verdict .h {{ font-size:1.35rem; font-weight:700; color:var(--ink); line-height:1.3; margin:.25rem 0; }}
.verdict .s {{ color:var(--ink2); font-size:.95rem; }}
.verdict.bad {{ background:#fff6f4; border-color:#f1c6bd; }}
.kpi.good .v {{ color:#006300; }} .kpi.bad .v {{ color:#b03030; }} .kpi.brand .v {{ color:var(--deep); }}
.kpi.brand {{ background:linear-gradient(180deg,#ffffff,var(--mint)); border-color:#bfdcca; }}
.chip {{ display:inline-block; padding:.22rem .65rem; margin:.15rem .25rem .15rem 0; border-radius:999px; font-size:.82rem;
  background:var(--mint); color:var(--deep); border:1px solid #bfdcca; }}
.chip.alt {{ background:#fdeee8; color:#8a3a18; border-color:#f4cdbd; }}
.callout {{ border-left:4px solid var(--green); background:white; border-radius:10px; padding:.8rem 1.1rem; margin:.6rem 0;
  border:1px solid var(--border); border-left-width:4px; }}
.callout.warn {{ border-left-color:#eda100; }} .callout.bad {{ border-left-color:#d03b3b; }} .callout.good {{ border-left-color:#0ca30c; }}
.callout b {{ color:var(--ink); }}
.sidefoot {{ background:white; border:1px solid var(--border); border-radius:14px; padding:.7rem .9rem; font-size:.84rem; margin-top:.6rem; }}
.sidefoot .t {{ font-size:.68rem; text-transform:uppercase; letter-spacing:.08em; color:var(--ink2); font-weight:600; }}
.sidefoot .ok {{ color:#006300; font-weight:700; }} .sidefoot .no {{ color:#b03030; font-weight:700; }}
.stTabs [data-baseweb="tab-list"] {{ gap:.3rem; }}
.stTabs [data-baseweb="tab"] {{ border-radius:10px 10px 0 0; padding:.45rem .9rem; }}
div[data-testid="stDataFrame"] {{ border:1px solid var(--border); border-radius:12px; }}
.stButton > button[kind="primary"] {{ border-radius:12px; font-weight:600; padding:.55rem 1.3rem; }}
.stButton > button {{ border-radius:12px; }}
footer {{ visibility:hidden; }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def inr(x: float | None, digits: int = 2) -> str:
    """Rupees in Indian units: Cr / L / plain."""
    if x is None:
        return "–"
    s, a = ("−" if x < 0 else ""), abs(float(x))
    if a >= 1e7:
        return f"{s}₹{a/1e7:.{digits}f} Cr"
    if a >= 1e5:
        return f"{s}₹{a/1e5:.1f} L"
    return f"{s}₹{a:,.0f}"


def hero(kicker: str, title: str, text: str) -> None:
    st.markdown(f'<div class="hero"><div class="kicker">{html.escape(kicker)}</div><h1>{html.escape(title)}</h1>'
                f'<p>{html.escape(text)}</p></div>', unsafe_allow_html=True)


# Plain-language names on screen; the textbook term lives in the tooltip so the course vocabulary stays visible.
LABELS = {
    "lcc": ("Lifetime cost", "Life-cycle cost (LCC): present worth of capex + O&M + replacements − residual value − energy and water savings. Negative = pays for itself."),
    "net_lcc": ("Lifetime cost after FAR value", "Net LCC: LCC minus the value of the extra floor area the rating unlocks (counted once, at year 0)."),
    "eac": ("Cost per year", "Equivalent annual cost (EAC) = LCC × capital recovery factor, i.e. the LCC spread evenly over the study period."),
    "capex": ("Upfront cost", "Capital expenditure (capex) at year 0, net of subsidy, incremental to the code-minimum baseline."),
    "sir": ("₹ saved per ₹ spent", "Savings-to-investment ratio (SIR) = PW(savings) / PW(costs). Above 1 = worth doing."),
    "payback": ("Payback", "Simple payback: first year the cumulative (undiscounted) net cash flow turns negative."),
    "co2": ("CO₂ avoided", "Lifetime tonnes of CO₂ avoided = kWh saved × grid emission factor."),
}

PAGES = {
    "home": ("pages/0_home.py", "Home", ":material/home:"),
    "setup": ("pages/1_setup.py", "Set up the project", ":material/tune:"),
    "rec": ("pages/2_recommendation.py", "See the recommendation", ":material/workspace_premium:"),
    "trust": ("pages/3_trust.py", "Check the risk", ":material/verified:"),
    "report": ("pages/4_report.py", "Get the report", ":material/description:"),
}


def label(key: str) -> str:
    return LABELS[key][0]


def tip(key: str) -> str:
    return LABELS[key][1]


def next_step(key: str, text: str = "") -> None:
    """A clear 'Next' button at the bottom of a page, so the demo flows without the sidebar."""
    path, title, icon = PAGES[key]
    st.write("")
    st.divider()
    l, r = st.columns([3, 1.2])
    l.caption(text)
    r.page_link(path, label=f"Next: {title} →", icon=icon, width="stretch")


def page_header(step: int | None, title: str, subtitle: str = "") -> None:
    chip = f'<span class="step">STEP {step} OF 4</span><br>' if step else ""
    st.markdown(f'<div class="pagehead">{chip}<h2>{html.escape(title)}</h2><p>{html.escape(subtitle)}</p></div>', unsafe_allow_html=True)


def kpis(items: list[tuple], cols: int | None = None) -> None:
    """items: (label, value, sub, tone[, help]) with tone in {'', 'good', 'bad', 'brand'}; help shows on hover."""
    cs = st.columns(cols or len(items))
    for c, it in zip(cs, items):
        name, value, sub, tone, hlp = (list(it) + ["", "", ""])[:5]
        q = f' <span class="q" title="{html.escape(hlp)}">ⓘ</span>' if hlp else ""
        c.markdown(f'<div class="kpi {tone}"><div class="l">{html.escape(name)}{q}</div><div class="v">{html.escape(str(value))}</div>'
                   f'<div class="s">{html.escape(str(sub))}</div></div>', unsafe_allow_html=True)


def card(title: str, text: str, big: str = "") -> str:
    b = f'<div class="big">{html.escape(big)}</div>' if big else ""
    return f'<div class="card">{b}<h4>{html.escape(title)}</h4><p>{html.escape(text)}</p></div>'


def chips(items: list[str], alt: bool = False) -> None:
    cls = "chip alt" if alt else "chip"
    st.markdown("".join(f'<span class="{cls}">{html.escape(i)}</span>' for i in items) or "<i>none</i>", unsafe_allow_html=True)


def callout(text: str, kind: str = "") -> None:
    st.markdown(f'<div class="callout {kind}">{text}</div>', unsafe_allow_html=True)


def verdict(kicker: str, headline: str, sub: str = "", bad: bool = False) -> None:
    """The one-sentence answer at the top of a page."""
    st.markdown(f'<div class="verdict{" bad" if bad else ""}"><div class="t">{html.escape(kicker)}</div><div class="h">{headline}</div>'
                f'<div class="s">{sub}</div></div>', unsafe_allow_html=True)


def unreachable(ds, df, target: str) -> None:
    """Friendly stop when the target cannot be met, with a one-click fix."""
    from . import optimizer

    callout(f"<b>{target} is not reachable.</b> {optimizer.infeasible_message(df, ds, target)}", "bad")
    top = state.highest_reachable(ds, df)
    if top:
        st.button(f"Switch target to {top}", type="primary", icon=":material/swap_vert:",
                  on_click=lambda: st.session_state.update(target=top))
    st.stop()


def require_ds():
    ds = state.get_ds()
    if ds is None:
        st.info("No project loaded yet. Open **Home** and click **Try the Pune demo**, or open a saved project file.")
        st.page_link("pages/0_home.py", label="Go to Home", icon=":material/home:")
        st.stop()
    return ds


def sidebar_brand() -> None:
    st.sidebar.markdown('<div class="brand"><div class="logo">G</div><div><div class="name">GreenLCC India</div>'
                        '<div class="sub">IGBC credit optimizer · CM 617</div></div></div>', unsafe_allow_html=True)


def _far_changed() -> None:
    ds = state.get_ds()
    on = st.session_state["far_on"]
    state.set_ds(ds.model_copy(update={"project": ds.project.model_copy(update={"use_far_benefit": on})}))
    st.session_state.pop("objective", None)
    st.session_state.pop("w_objective", None)


def sidebar_controls() -> None:
    """The two choices that drive every page live in one place: target level and whether to count FAR value."""
    ds = state.get_ds()
    if ds is None:
        return
    levels = [lv.level for lv in sorted(ds.levels, key=lambda x: x.rank)]
    if st.session_state.get("target") not in levels:
        st.session_state["target"] = ds.project.target_level if ds.project.target_level in levels else levels[-1]
    st.session_state["far_on"] = ds.project.use_far_benefit
    with st.sidebar:
        st.selectbox("Target IGBC level", levels, key="target", help="Applies to every page and to the report.")
        st.toggle("Count extra-FAR value", key="far_on", on_change=_far_changed,
                  help="Some states give extra floor area (FAR) for a green rating. When on, its value is subtracted from lifetime cost.")


def sidebar_footer() -> None:
    ds = state.get_ds()
    if ds is None:
        return
    try:
        target, obj, df, rec, _ = state.recommendation(ds)
    except Exception:
        return
    if rec is None:
        body = f'<span class="no">{target} not reachable</span>'
    else:
        body = (f'<span class="ok">{rec["level"]} · {rec["points"]:g} pts ✓</span><br>'
                f'Lifetime cost {inr(rec["lcc"])}<br>Upfront {inr(rec["capex"])}')
    st.sidebar.markdown(f'<div class="sidefoot"><div class="t">{html.escape(ds.project.name)}</div>'
                        f'{body}</div>', unsafe_allow_html=True)
