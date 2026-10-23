"""Streamlit session state and cached analysis (single source of truth: session_state['ds'])."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from . import optimizer
from .io import load_bundle, load_dataset
from .schemas import Dataset


def get_ds() -> Dataset | None:
    return st.session_state.get("ds")


def set_ds(ds: Dataset) -> None:
    st.session_state["ds"] = ds


def load_demo() -> list[str]:
    ds, errs = load_dataset()
    if ds:
        set_ds(ds)
        reset_choices()
        st.session_state.pop("quote", None)
    return errs


def reset_choices() -> None:
    """Forget the sidebar target / objective so they follow the (new) project defaults."""
    for k in ("target", "objective", "w_objective"):
        st.session_state.pop(k, None)


def open_bundle(data: bytes) -> list[str]:
    ds, errs = load_bundle(data)
    if ds:
        set_ds(ds)
        reset_choices()
        st.session_state.pop("quote", None)
    return errs


@st.cache_data(show_spinner="Searching every portfolio of measures…")
def _portfolios(ds_json: str) -> pd.DataFrame:
    return optimizer.enumerate_portfolios(Dataset.model_validate_json(ds_json))


def portfolios(ds: Dataset) -> pd.DataFrame:
    return _portfolios(ds.model_dump_json())


def objective_for(ds: Dataset) -> str:
    """Objective used for the headline recommendation."""
    return st.session_state.get("objective") or ("net_lcc" if ds.project.use_far_benefit else "lcc")


def recommendation(ds: Dataset):
    """(target, objective, all-portfolios table, recommended row or None, cheapest-capex row or None)"""
    target = st.session_state.get("target") or ds.project.target_level
    obj = objective_for(ds)
    df = portfolios(ds)
    return target, obj, df, optimizer.best(df, ds, target, obj), optimizer.best(df, ds, target, "capex")


def highest_reachable(ds: Dataset, df: pd.DataFrame) -> str | None:
    """Highest IGBC level some portfolio in the library can reach (None if none)."""
    for lv in sorted(ds.levels, key=lambda x: x.rank, reverse=True):
        if optimizer.best(df, ds, lv.level, "lcc") is not None:
            return lv.level
    return None
