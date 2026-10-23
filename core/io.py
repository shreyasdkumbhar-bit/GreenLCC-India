"""Load and validate input files. Problems are collected as readable messages, never raised."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from .schemas import Component, Credit, Dataset, Level, Measure, Project

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _fmt(err: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, e['loc'])) or 'row'}: {e['msg']}" for e in err.errors())


def rows_to_models(df: pd.DataFrame, model, label: str) -> tuple[list, list[str]]:
    """Validate every row of a DataFrame; return (good models, error strings)."""
    out, errors = [], []
    df = df.astype(object).where(pd.notna(df), None)
    for i, rec in enumerate(df.to_dict("records"), start=1):
        rec = {k: v for k, v in rec.items() if v is not None or k == "exclusive_group"}
        try:
            out.append(model(**rec))
        except ValidationError as e:
            errors.append(f"{label} row {i}: {_fmt(e)}")
    return out, errors


def cross_check(ds: Dataset) -> list[str]:
    errors: list[str] = []
    ids = [m.measure_id for m in ds.measures]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        errors.append(f"Duplicate measure_id: {sorted(dup)}")
    credit_ids = {c.credit_id for c in ds.credits}
    for m in ds.measures:
        if m.credit_id and m.credit_id not in credit_ids:
            errors.append(f"Measure {m.measure_id}: unknown credit_id '{m.credit_id}'")
        if m.kind == "renewable" and m.kwp <= 0:
            errors.append(f"Measure {m.measure_id}: renewable measure needs kwp > 0")
    for c in ds.components:
        if c.measure_id not in ids:
            errors.append(f"Component '{c.component}' refers to unknown measure '{c.measure_id}'")
    if ds.project.target_level not in {lv.level for lv in ds.levels}:
        errors.append(f"target_level '{ds.project.target_level}' is not in igbc_levels.csv")
    for lv in ds.project.far_bonus_pct:
        if lv not in {l.level for l in ds.levels}:
            errors.append(f"far_bonus_pct has unknown level '{lv}'")
    return errors


def load_dataset(data_dir: Path | str = DATA_DIR, project_file: str = "project_demo.json") -> tuple[Dataset | None, list[str]]:
    data_dir = Path(data_dir)
    errors: list[str] = []
    try:
        raw = json.loads((data_dir / project_file).read_text(encoding="utf-8"))
        raw = {k: v for k, v in raw.items() if not k.startswith("_")}
        project = Project(**raw)
    except (OSError, json.JSONDecodeError) as e:
        return None, [f"{project_file}: {e}"]
    except ValidationError as e:
        return None, [f"{project_file}: {_fmt(e)}"]

    parts = {}
    for fname, model in [("measures.csv", Measure), ("components.csv", Component),
                         ("igbc_credits.csv", Credit), ("igbc_levels.csv", Level)]:
        try:
            df = pd.read_csv(data_dir / fname)
        except OSError as e:
            errors.append(f"{fname}: {e}")
            parts[fname] = []
            continue
        items, errs = rows_to_models(df, model, fname)
        parts[fname] = items
        errors += errs
    # cross-check the rows that did parse, so the user sees every problem in one pass
    ds = Dataset(project=project, measures=parts["measures.csv"], components=parts["components.csv"],
                 credits=parts["igbc_credits.csv"], levels=parts["igbc_levels.csv"])
    errors += cross_check(ds)
    return (None, errors) if errors else (ds, [])


def measures_to_df(ms: list[Measure]) -> pd.DataFrame:
    return pd.DataFrame([m.model_dump() for m in ms])


BUNDLE_FORMAT = "greenlcc-project"


def dump_bundle(ds: Dataset, target: str | None = None) -> bytes:
    """One self-contained project file: building, measures, components and IGBC tables."""
    if target:
        ds = ds.model_copy(update={"project": ds.project.model_copy(update={"target_level": target})})
    return json.dumps({"format": BUNDLE_FORMAT, "version": 1, **ds.model_dump()}, indent=2, default=float).encode("utf-8")


def load_bundle(data: bytes | str) -> tuple[Dataset | None, list[str]]:
    """Read a file written by dump_bundle; problems come back as readable messages."""
    try:
        raw = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return None, [f"Not a valid project file: {e}"]
    if not isinstance(raw, dict) or raw.get("format") != BUNDLE_FORMAT:
        return None, ["This is not a GreenLCC project file (save one from the Report page)."]
    try:
        ds = Dataset(**{k: v for k, v in raw.items() if k not in ("format", "version")})
    except ValidationError as e:
        return None, [_fmt(e)]
    errs = cross_check(ds)
    return (None, errs) if errs else (ds, [])
