"""Typed data models. Every input file is validated through these."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Kind = Literal["efficiency", "renewable", "water", "none"]


class Project(BaseModel):
    name: str
    city: str = ""
    building_type: str = ""
    plot_area_m2: float = Field(gt=0)
    fsi: float = Field(gt=0)
    bua_m2: float = Field(gt=0)
    roof_area_m2: float = Field(ge=0)
    baseline_energy_kwh: float = Field(gt=0)
    baseline_water_kl: float = Field(ge=0)
    study_period: int = Field(ge=5, le=60)
    discount_rate: float = Field(gt=0, lt=0.30)
    inflation: float = Field(ge=0, lt=0.20)
    grid_tariff: float = Field(gt=0)
    tariff_escalation: float = Field(ge=-0.05, le=0.20)
    tariff_escalation_sd: float = Field(ge=0, le=0.10)
    export_tariff: float = Field(ge=0)
    export_escalation: float = Field(default=0.0, ge=-0.05, le=0.20)
    water_tariff: float = Field(ge=0)
    water_escalation: float = Field(default=0.06, ge=-0.05, le=0.20)
    pv_yield_kwh_per_kwp: float = Field(gt=0)
    pv_self_consumption: float = Field(ge=0, le=1)
    pv_area_per_kwp_m2: float = Field(default=10, gt=0)
    grid_emission_factor: float = Field(ge=0)  # tCO2 per MWh
    target_level: str
    base_points: float = Field(ge=0)
    far_bonus_pct: dict[str, float] = Field(default_factory=dict)
    far_net_value_per_m2: float = Field(ge=0)
    use_far_benefit: bool = True

    @property
    def permissible_bua_m2(self) -> float:
        return self.plot_area_m2 * self.fsi


class Measure(BaseModel):
    measure_id: str = Field(min_length=1)
    name: str
    exclusive_group: str | None = None
    kind: Kind = "efficiency"
    credit_id: str = ""
    points_fixed: float = Field(default=0, ge=0)
    capex: float = Field(ge=0)
    subsidy: float = Field(default=0, ge=0)
    om_annual: float = Field(default=0, ge=0)
    om_escalation: float = Field(default=0.05, ge=-0.05, le=0.20)
    energy_saving_kwh: float = Field(default=0, ge=0)
    kwp: float = Field(default=0, ge=0)
    water_saving_kl: float = Field(default=0, ge=0)
    degradation: float = Field(default=0, ge=0, le=0.10)
    source: str = "library"
    description: str = ""

    @field_validator("exclusive_group", mode="before")
    @classmethod
    def _blank_group(cls, v):
        if v is None or (isinstance(v, float) and v != v) or str(v).strip() == "":
            return None
        return str(v).strip()

    @model_validator(mode="after")
    def _subsidy_le_capex(self):
        if self.subsidy > self.capex:
            raise ValueError("subsidy cannot exceed capex")
        return self

    @property
    def group(self) -> str:
        return self.exclusive_group or self.measure_id


class Component(BaseModel):
    measure_id: str
    component: str
    cost: float = Field(ge=0)
    life_years: float = Field(gt=0)


class Credit(BaseModel):
    credit_id: str
    category: str
    name: str
    max_points: float = Field(gt=0)
    rule: Literal["fixed", "threshold_pct"]
    basis: Literal["", "energy_eff", "energy_re", "water"] = ""
    thresholds: list[tuple[float, float]] = Field(default_factory=list)
    mandatory: bool = False

    @field_validator("thresholds", mode="before")
    @classmethod
    def _parse_thresholds(cls, v):
        # CSV form "5:1|10:3" -> [(5,1),(10,3)]
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
    components: list[Component]
    credits: list[Credit]
    levels: list[Level]

    def level_rank(self, level: str) -> int:
        for lv in self.levels:
            if lv.level == level:
                return lv.rank
        return 0

    def comps_for(self, measure_id: str) -> list[Component]:
        return [c for c in self.components if c.measure_id == measure_id]

    def measure(self, measure_id: str) -> Measure:
        for m in self.measures:
            if m.measure_id == measure_id:
                return m
        raise KeyError(measure_id)
