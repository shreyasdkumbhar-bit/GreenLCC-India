"""Typed data models. Every input sheet is validated through these."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Fixed modelling constants (documented in the README sheet of the input workbook)
PV_AREA_PER_KWP_M2 = 10.0   # roof area one kWp of rooftop PV needs
EXPORT_ESCALATION = 0.0     # MERC export credit is a fixed rate; assume it stays flat


class Project(BaseModel):
    name: str
    city: str = ""
    roof_area_m2: float = Field(ge=0)
    baseline_energy_kwh: float = Field(gt=0)
    baseline_water_kl: float = Field(ge=0)
    study_period: int = Field(ge=5, le=60)
    discount_rate: float = Field(gt=0, lt=0.30)       # MARR, nominal
    inflation: float = Field(ge=0, lt=0.20)           # escalates O&M and replacement prices
    grid_tariff: float = Field(gt=0)
    tariff_escalation: float = Field(ge=-0.05, le=0.20)
    tariff_escalation_sd: float = Field(ge=0, le=0.10)
    export_tariff: float = Field(ge=0)
    water_tariff: float = Field(ge=0)
    water_escalation: float = Field(default=0.06, ge=-0.05, le=0.20)
    pv_yield_kwh_per_kwp: float = Field(gt=0)
    pv_self_consumption: float = Field(ge=0, le=1)
    grid_emission_factor: float = Field(ge=0)  # tCO2 per MWh
    target_level: str
    base_points: float = Field(ge=0)

    @property
    def roof_kwp_cap(self) -> float:
        return self.roof_area_m2 / PV_AREA_PER_KWP_M2


class Measure(BaseModel):
    """One green option, costed INCREMENTALLY over the code-minimum baseline."""

    measure_id: str = Field(min_length=1)
    name: str
    exclusive_group: str | None = None
    credit_id: str = ""
    points_fixed: float = Field(default=0, ge=0)
    capex: float = Field(ge=0)
    life_years: float = Field(gt=0)
    om_annual: float = Field(default=0, ge=0)
    energy_saving_kwh: float = Field(default=0, ge=0)
    kwp: float = Field(default=0, ge=0)
    water_saving_kl: float = Field(default=0, ge=0)
    degradation: float = Field(default=0, ge=0, le=0.10)
    part_name: str = ""
    part_cost: float = Field(default=0, ge=0)
    part_life: float = Field(default=0, ge=0)
    description: str = ""

    @field_validator("exclusive_group", mode="before")
    @classmethod
    def _blank_group(cls, v):
        if v is None or (isinstance(v, float) and v != v) or str(v).strip() == "":
            return None
        return str(v).strip()

    @field_validator("credit_id", "part_name", "description", mode="before")
    @classmethod
    def _blank_text(cls, v):
        return "" if v is None or (isinstance(v, float) and v != v) else str(v).strip()

    @model_validator(mode="after")
    def _part_needs_life(self):
        if self.part_cost > 0 and self.part_life <= 0:
            raise ValueError("part_cost needs a part_life above 0")
        return self

    @property
    def group(self) -> str:
        return self.exclusive_group or self.measure_id

    @property
    def is_solar(self) -> bool:
        return self.kwp > 0


class Credit(BaseModel):
    credit_id: str
    category: str
    name: str
    max_points: float = Field(gt=0)
    rule: Literal["fixed", "threshold_pct"]
    basis: Literal["", "energy_eff", "energy_re", "water"] = ""
    thresholds: list[tuple[float, float]] = Field(default_factory=list)
    mandatory: bool = False

    @field_validator("basis", mode="before")
    @classmethod
    def _blank_basis(cls, v):
        return "" if v is None or (isinstance(v, float) and v != v) else v

    @field_validator("thresholds", mode="before")
    @classmethod
    def _parse_thresholds(cls, v):
        # sheet form "5:1|10:3" -> [(5,1),(10,3)]
        if v is None or (isinstance(v, float) and v != v):
            return []
        if isinstance(v, str):
            out = []
            for part in filter(None, (s.strip() for s in v.split("|"))):
                pct, pts = part.split(":")
                out.append((float(pct), float(pts)))
            return out
        return v

    @model_validator(mode="after")
    def _rule_needs_data(self):
        if self.rule == "threshold_pct" and (not self.basis or not self.thresholds):
            raise ValueError("threshold_pct credits need a basis and thresholds")
        return self


class Level(BaseModel):
    level: str
    min_points: float = Field(ge=0)
    rank: int


class Dataset(BaseModel):
    project: Project
    measures: list[Measure]
    credits: list[Credit]
    levels: list[Level]

    def level_rank(self, level: str) -> int:
        for lv in self.levels:
            if lv.level == level:
                return lv.rank
        return 0

    def measure(self, measure_id: str) -> Measure:
        for m in self.measures:
            if m.measure_id == measure_id:
                return m
        raise KeyError(measure_id)
