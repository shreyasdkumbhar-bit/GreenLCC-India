"""GreenLCC India - IGBC credit optimizer with life-cycle costing. Run: streamlit run app.py"""
import streamlit as st

from core import ui

st.set_page_config(page_title="GreenLCC India", page_icon=":material/eco:", layout="wide", initial_sidebar_state="expanded")
ui.inject_css()
ui.sidebar_brand()

pg = st.navigation([
    st.Page("pages/0_home.py", title="Home", icon=":material/home:", default=True),
    st.Page("pages/1_setup.py", title="1 · Set up", icon=":material/tune:"),
    st.Page("pages/2_recommendation.py", title="2 · Recommendation", icon=":material/workspace_premium:"),
    st.Page("pages/3_trust.py", title="3 · Can we trust it?", icon=":material/verified:"),
    st.Page("pages/4_report.py", title="4 · Report", icon=":material/description:"),
])
ui.sidebar_controls()  # target level + FAR switch: one place, every page
pg.run()
ui.sidebar_footer()  # after the page runs, so it reflects any edits made on it
