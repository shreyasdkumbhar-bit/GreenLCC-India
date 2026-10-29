"""Headless UI tests: every page must render without exceptions on the demo project."""
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PAGES = ["pages/1_setup.py", "pages/2_recommendation.py", "pages/3_trust.py", "pages/4_report.py"]


def new_app() -> AppTest:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.run()
    return at


def loaded_app() -> AppTest:
    at = new_app()
    next(b for b in at.button if "Pune demo" in b.label).click().run()
    return at


def test_home_renders_without_project():
    at = new_app()
    assert not at.exception
    assert any("Pune demo" in b.label for b in at.button)


def test_load_demo_succeeds():
    at = loaded_app()
    assert not at.exception
    assert at.session_state["ds"].project.name.startswith("Pune")


@pytest.mark.parametrize("page", PAGES)
def test_each_page_renders_with_demo(page):
    at = loaded_app()
    at.switch_page(page).run()
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.parametrize("page", PAGES)
def test_pages_guard_when_no_project(page):
    at = new_app()
    at.switch_page(page).run()
    assert not at.exception
    assert any("No project loaded" in i.value for i in at.info)


def test_home_shows_answer_after_loading():
    at = loaded_app()
    assert any("The answer" in m.value for m in at.markdown)


def test_recommendation_and_infeasible_target_with_switch_button():
    at = loaded_app()
    at.switch_page("pages/2_recommendation.py").run()
    assert not at.exception
    assert any("Recommended" in m.value for m in at.markdown)
    # an unreachable target gives a friendly message and a one-click fix, not a crash
    ds = at.session_state["ds"]
    small = ds.model_copy(update={"measures": [ds.measure("LIGHT_LED"), ds.measure("WTR_FIX")]})
    at.session_state["ds"] = small
    at.session_state["target"] = "Platinum"
    at.run()
    assert not at.exception
    assert any("not reachable" in m.value for m in at.markdown)
    fix = next(b for b in at.button if b.label.startswith("Switch target to"))
    fix.click().run()
    assert not at.exception
    assert at.session_state["target"] != "Platinum"
    assert not any("not reachable" in m.value for m in at.markdown)


def test_target_drives_every_page():
    at = loaded_app()
    at.switch_page("pages/2_recommendation.py").run()
    at.session_state["target"] = "Silver"
    at.run()
    assert not at.exception
    assert any("IGBC Silver" in m.value for m in at.markdown)


def _sidebar_app():
    # AppTest re-runs only the page after st.navigation, so the sidebar controls are tested on their own here
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path.cwd()))
    import streamlit as st

    from core import state, ui

    if state.get_ds() is None:
        state.load_demo()
    ui.sidebar_controls()
    st.write(f"target={st.session_state['target']}")


def test_sidebar_target_control(monkeypatch):
    monkeypatch.chdir(ROOT)
    at = AppTest.from_function(_sidebar_app, default_timeout=60).run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["target"] == at.session_state["ds"].project.target_level
    at.selectbox(key="target").set_value("Platinum").run()
    assert not at.exception
    assert at.session_state["target"] == "Platinum"


def test_recommendation_shows_incremental_return():
    at = loaded_app()
    at.switch_page("pages/2_recommendation.py").run()
    assert not at.exception
    assert any("MARR" in m.value for m in at.markdown)


def test_report_page_offers_three_downloads():
    at = loaded_app()
    at.switch_page("pages/4_report.py").run()
    assert not at.exception, [e.value for e in at.exception]
    labels = [getattr(el, "proto", el).label for el in at.get("download_button")]
    assert len(labels) == 3, labels
