"""Vendor quotation PDF -> structured measure fields.

Uses Claude when ANTHROPIC_API_KEY is set, and a deterministic regex parser otherwise (or if the
LLM call fails), so the demo always works offline. The result is only a DRAFT: the UI shows it for
human review before anything enters the measure library.
"""
from __future__ import annotations

import json
import os
import re
from typing import IO

from pydantic import BaseModel, Field

from .schemas import Measure

MODEL = "claude-sonnet-5-5"


class ExtractedQuote(BaseModel):
    vendor: str = ""
    item: str = ""
    capacity: str = ""
    capex: float | None = Field(default=None, ge=0)
    om_annual: float | None = Field(default=None, ge=0)
    warranty_years: float | None = Field(default=None, ge=0)
    component_name: str = ""
    component_cost: float | None = Field(default=None, ge=0)
    component_life_years: float | None = Field(default=None, gt=0)
    method: str = "regex"
    notes: list[str] = Field(default_factory=list)

    def missing(self) -> list[str]:
        return [f for f in ("vendor", "item", "capex") if not getattr(self, f)]


def pdf_text(file: str | IO[bytes]) -> str:
    import pdfplumber

    with pdfplumber.open(file) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages)


_MONEY = r"(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d+)?)"


def _money(s: str) -> float:
    return float(s.replace(",", ""))


def _field(text: str, label: str) -> str:
    m = re.search(rf"^{label}\s*:\s*(.+)$", text, re.I | re.M)
    return m.group(1).strip() if m else ""


def parse_regex(text: str) -> ExtractedQuote:
    q = ExtractedQuote(method="regex")
    q.vendor, q.item, q.capacity = _field(text, "Vendor"), _field(text, "Item"), _field(text, "Capacity")
    if m := re.search(rf"^Total price[^:\n]*:\s*{_MONEY}", text, re.I | re.M):
        q.capex = _money(m.group(1))
    if m := re.search(rf"^Annual maintenance[^:\n]*:\s*{_MONEY}", text, re.I | re.M):
        q.om_annual = _money(m.group(1))
    if m := re.search(r"^Product warranty\s*:\s*(\d+(?:\.\d+)?)\s*year", text, re.I | re.M):
        q.warranty_years = float(m.group(1))
    if m := re.search(rf"^([A-Za-z ]+?) replacement\s*:\s*{_MONEY}\s*at\s*(\d+(?:\.\d+)?)\s*year", text, re.I | re.M):
        q.component_name = f"{m.group(1).strip()} replacement"
        q.component_cost, q.component_life_years = _money(m.group(2)), float(m.group(3))
    if q.component_cost is None:
        q.notes.append("No replaceable component found; assuming none.")
    return q


_PROMPT = """Extract fields from this vendor quotation. Reply with ONLY a JSON object with keys:
vendor, item, capacity (string), capex (total price in rupees, number), om_annual (annual maintenance in rupees, number),
warranty_years (number), component_name, component_cost (rupees), component_life_years.
Use null for anything not stated. Do not infer or invent numbers.

QUOTATION TEXT:
"""


def parse_llm(text: str) -> ExtractedQuote | None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic

        msg = anthropic.Anthropic().messages.create(
            model=MODEL, max_tokens=600, messages=[{"role": "user", "content": _PROMPT + text[:8000]}])
        raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        data = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
        q = ExtractedQuote(**{k: v for k, v in data.items() if k in ExtractedQuote.model_fields and v is not None})
        q.method = "Claude"
        return q
    except Exception as e:  # network, auth, bad JSON: fall back rather than fail the demo
        q = parse_regex(text)
        q.notes.append(f"LLM extraction failed ({type(e).__name__}); used the offline parser.")
        return q


def extract(file: str | IO[bytes]) -> ExtractedQuote:
    text = pdf_text(file)
    return parse_llm(text) or parse_regex(text)


def to_measure(q: ExtractedQuote, *, measure_id: str, life_years: float, exclusive_group: str | None = None,
               credit_id: str = "", points_fixed: float = 0, energy_saving_kwh: float = 0,
               water_saving_kl: float = 0, kwp: float = 0, degradation: float = 0,
               baseline_cost: float = 0, baseline_om: float = 0) -> Measure:
    """Combine the reviewed quote with the user-supplied engineering fields.

    Costs in the library are INCREMENTAL to the code-minimum baseline, so the baseline system's
    cost (e.g. the split ACs a VRF replaces) is deducted from the quoted price.
    """
    return Measure(measure_id=measure_id, name=f"{q.item or measure_id} ({q.vendor})".strip(), exclusive_group=exclusive_group,
                   credit_id=credit_id, points_fixed=points_fixed, capex=max((q.capex or 0) - baseline_cost, 0),
                   life_years=life_years, om_annual=max((q.om_annual or 0) - baseline_om, 0),
                   energy_saving_kwh=energy_saving_kwh, kwp=kwp, water_saving_kl=water_saving_kl, degradation=degradation,
                   part_name=q.component_name if q.component_cost and q.component_life_years else "",
                   part_cost=(q.component_cost or 0) if q.component_life_years else 0, part_life=q.component_life_years or 0,
                   description=f"From quote: {q.vendor}, {q.capacity}".strip(", "))


def capacity_kwp(capacity: str) -> float:
    m = re.search(r"([\d,.]+)\s*kWp", capacity, re.I)
    return float(m.group(1).replace(",", "")) if m else 0.0
