"""Write data/demo_input.xlsx: the Pune office demo, sized from one consistent basis, with a source per value.

Run:  python scripts/make_demo_input.py

Sizing basis (all measures are INCREMENTAL over the code-minimum option they replace)
- 12,000 m² office, ~1,000 occupants, Pune. Baseline 1.8 GWh/yr = 150 kWh/m²·yr.
- End uses: HVAC 55% (990 MWh), lighting 20% (360 MWh), plug and other 25%.
- Cooling load ~350 TR (≈ 34 m² per TR of conditioned office). Facade glazing ~3,000 m². Roof 2,500 m².
- Water 14,000 kL/yr ≈ 1,000 people × 45 L/day × 300 days (NBC 2016 office norm).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.io import DEMO_INPUT, write_workbook  # noqa: E402
from core.schemas import Credit, Dataset, Level, Measure, Project  # noqa: E402

HVAC_KWH, LIGHT_KWH, TR, GLAZ_M2, ROOF_M2, BUA_M2 = 990_000, 360_000, 350, 3_000, 2_500, 12_000

PROJECT = dict(
    name="Pune Tech Office (demo)", city="Pune", roof_area_m2=ROOF_M2, baseline_energy_kwh=1_800_000, baseline_water_kl=14_000,
    study_period=25, discount_rate=0.10, inflation=0.05, grid_tariff=13.0, tariff_escalation=0.05, tariff_escalation_sd=0.02,
    export_tariff=2.82, water_tariff=60.0, water_escalation=0.06, pv_yield_kwh_per_kwp=1450, pv_self_consumption=0.95,
    grid_emission_factor=0.727, target_level="Gold", base_points=52,
)
NOTES = {
    "name": "Illustrative building, not a real project",
    "roof_area_m2": "Assumption: ~40% of a 6,000 m² roof plate free of plant and shading",
    "baseline_energy_kwh": "Assumption: 150 kWh/m²·yr × 12,000 m²; typical of a code-minimum Indian office (BEE star-label range)",
    "baseline_water_kl": "Assumption: 1,000 occupants × 45 L/day × 300 days (NBC 2016 office norm)",
    "study_period": "Choice: 25 years = PV module life, a common LCCA horizon",
    "discount_rate": "Assumption: private developer MARR ≈ 10-yr G-sec (~6.5%) + 3–4 pp risk premium",
    "inflation": "Assumption: RBI CPI target 4% ± 2 pp; long-run average ~5%",
    "grid_tariff": "Estimate (verify, Q-003): MSEDCL commercial >50 kW energy charge ~₹12–15/kVAh plus wheeling and FAC; MERC 2025 MYT order under review",
    "tariff_escalation": "Assumption: Maharashtra commercial tariffs have risen ~4–6% a year",
    "tariff_escalation_sd": "Assumption: ±2 pp covers regulatory swings like the 2025 MERC order and its review",
    "export_tariff": "Source: MERC rooftop-solar export credit ₹2.82/kWh, FY 2025-26 (SolarQuarter, Apr 2025)",
    "water_tariff": "Assumption: Pune commercial water + sewerage, ~₹50–70/kL (higher if tankers are used)",
    "water_escalation": "Assumption",
    "pv_yield_kwh_per_kwp": "Assumption: Pune ~1,400–1,500 kWh/kWp/yr (typical PVGIS/NREL estimates)",
    "pv_self_consumption": "Assumption: office daytime load (>200 kW) absorbs almost all output; export mainly on holidays",
    "grid_emission_factor": "Source: CEA CO₂ Baseline Database v20 (FY 2023-24), weighted average 0.727 tCO₂/MWh",
    "target_level": "Choice",
    "base_points": "Illustrative: points the base design earns without the measures below",
}


def M(**kw) -> Measure:
    return Measure(**kw)


def pv(kwp: int) -> Measure:
    return M(measure_id=f"PV_{kwp}", name=f"Rooftop solar {kwp} kWp", exclusive_group="PV", credit_id="EE-C3",
             capex=45_000 * kwp, life_years=25, om_annual=600 * kwp, kwp=kwp, degradation=0.005,
             part_name="Inverters", part_cost=5_000 * kwp, part_life=12,
             description="₹45,000/kWp (MSEDCL 2026 rooftop benchmark ₹45,450/kW; market ₹38–50k); O&M ₹600/kWp/yr; "
                         "inverters ₹5,000/kWp every 12 yrs; 0.5%/yr module degradation")


MEASURES = [
    M(measure_id="HVAC_VRF", name="VRF air conditioning (350 TR)", exclusive_group="HVAC", credit_id="EE-C2",
      capex=(90_000 - 45_000) * TR, life_years=15, om_annual=(1_500 - 1_000) * TR, energy_saving_kwh=round(0.25 * HVAC_KWH, -3),
      degradation=0.005,
      description="Installed ~₹90k/TR vs split/packaged baseline ~₹45k/TR; ISEER ~5.8 vs 3.8 ≈ 25% of HVAC kWh; AMC +₹500/TR/yr"),
    M(measure_id="HVAC_CHILLER", name="Water-cooled chiller plant (350 TR)", exclusive_group="HVAC", credit_id="EE-C2",
      capex=(1_15_000 - 45_000) * TR, life_years=25, om_annual=900_000, energy_saving_kwh=round(0.35 * HVAC_KWH, -3),
      degradation=0.005, part_name="Cooling tower and pump overhaul", part_cost=3_500_000, part_life=12,
      description="Installed ~₹1.15 L/TR incl. towers, pumps, AHUs; plant ~0.85 kW/TR vs ~1.3 ≈ 35% of HVAC kWh; operators + water treatment ₹9 L/yr"),
    M(measure_id="GLZ_DGU", name="Double-glazed units (3,000 m²)", exclusive_group="GLAZING", credit_id="EE-C2",
      capex=2_500 * GLAZ_M2, life_years=30, energy_saving_kwh=round(0.03 * HVAC_KWH, -3),
      description="+₹2,500/m² over single glazing; lower U-value ≈ 3% of HVAC kWh"),
    M(measure_id="GLZ_LOWE", name="Low-e double-glazed units (3,000 m²)", exclusive_group="GLAZING", credit_id="IEQ-C1", points_fixed=2,
      capex=4_500 * GLAZ_M2, life_years=30, energy_saving_kwh=round(0.07 * HVAC_KWH, -3),
      description="+₹4,500/m² over single glazing; SHGC 0.25 cuts solar gain ≈ 7% of HVAC kWh; better daylight earns IEQ points"),
    M(measure_id="LIGHT_LED", name="LED lighting + occupancy/daylight sensors", credit_id="EE-C4", points_fixed=3,
      capex=450 * BUA_M2, life_years=12, energy_saving_kwh=round(0.30 * LIGHT_KWH, -3), degradation=0.01,
      description="+₹450/m² over code-minimum fixtures; LPD and controls ≈ 30% of lighting kWh; drivers ~12 yrs"),
    M(measure_id="BMS", name="Energy sub-metering + BMS", credit_id="EE-C5", points_fixed=1,
      capex=400 * BUA_M2, life_years=15, om_annual=250_000, energy_saving_kwh=round(0.06 * HVAC_KWH, -3),
      description="~₹400/m²; scheduling and set-point control ≈ 6% of HVAC kWh; software/AMC ₹2.5 L/yr"),
    M(measure_id="COOLROOF", name="Cool roof coating (2,500 m²)", credit_id="SS-C3", points_fixed=2,
      capex=300 * ROOF_M2, life_years=10, om_annual=15_000, energy_saving_kwh=15_000, degradation=0.02,
      description="High-SRI coating ~₹300/m², recoat every 10 yrs; ~6 kWh/m² of roof saved on top-floor cooling; soiling 2%/yr"),
    pv(100), pv(150), pv(200),
    M(measure_id="WTR_FIX", name="Low-flow fixtures (taps, dual-flush WCs)", credit_id="WE-C1",
      capex=1_200_000, life_years=12, om_annual=10_000, water_saving_kl=3_500,
      description="~200 fixtures × ₹6,000 extra; ≈ 25% of baseline water"),
    M(measure_id="WTR_STP", name="STP with treated-water reuse (50 KLD)", credit_id="WE-C2", points_fixed=2,
      capex=4_000_000, life_years=20, om_annual=450_000, water_saving_kl=4_900,
      part_name="Blowers, pumps and membranes", part_cost=800_000, part_life=7,
      description="50 KLD plant ~₹40 L; operator, power, chemicals ₹4.5 L/yr; reuse for flushing and landscape ≈ 35% of water"),
]

CREDITS = [  # ILLUSTRATIVE point tables (real IGBC v4.0 tables: Q-002)
    Credit(credit_id="EE-C2", category="Energy Efficiency", name="Enhanced energy performance", max_points=11, rule="threshold_pct",
           basis="energy_eff", thresholds="5:1|10:3|15:5|20:7|25:9|30:11"),
    Credit(credit_id="EE-C3", category="Energy Efficiency", name="On-site renewable energy", max_points=8, rule="threshold_pct",
           basis="energy_re", thresholds="2:2|5:4|10:6|15:8"),
    Credit(credit_id="EE-C4", category="Energy Efficiency", name="Efficient lighting and controls", max_points=3, rule="fixed"),
    Credit(credit_id="EE-C5", category="Energy Efficiency", name="Energy metering and BMS", max_points=1, rule="fixed"),
    Credit(credit_id="WE-C1", category="Water Efficiency", name="Water-efficient fixtures and reuse", max_points=4, rule="threshold_pct",
           basis="water", thresholds="15:1|30:2|45:3|60:4", mandatory=True),
    Credit(credit_id="WE-C2", category="Water Efficiency", name="Wastewater treatment and reuse", max_points=2, rule="fixed"),
    Credit(credit_id="SS-C3", category="Site and Planning", name="Heat island reduction (cool roof)", max_points=2, rule="fixed"),
    Credit(credit_id="IEQ-C1", category="Indoor Environment", name="Daylight and glazing performance", max_points=2, rule="fixed"),
]
LEVELS = [Level(level=lv, min_points=pts, rank=r) for r, (lv, pts) in enumerate(
    [("Certified", 50), ("Silver", 60), ("Gold", 70), ("Platinum", 80)], start=1)]


def demo_dataset() -> Dataset:
    return Dataset(project=Project(**PROJECT), measures=MEASURES, credits=CREDITS, levels=LEVELS)


if __name__ == "__main__":
    DEMO_INPUT.write_bytes(write_workbook(demo_dataset(), NOTES))
    print("wrote", DEMO_INPUT)
