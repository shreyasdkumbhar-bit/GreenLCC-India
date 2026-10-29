"""Generate the three dummy vendor quotation PDFs used to demo AI quote extraction.

Run:  python scripts/make_dummy_data.py
All vendors, prices and terms are fictional and illustrative.
"""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parent.parent / "sample_quotes"

QUOTES = {
    "SunRise_Solar_150kWp_quote.pdf": {
        "title": "QUOTATION - Rooftop Solar PV",
        "lines": [
            "Vendor: SunRise Solar Pvt Ltd, Pune",
            "Quote ref: SRS/2026/0412   Date: 12-Oct-2026",
            "Item: Grid-tied rooftop solar PV system (net metering ready)",
            "Capacity: 150 kWp",
            "Scope: modules, inverters, mounting structure, cabling, net-meter liaison",
            "",
            "Total price (incl. GST): Rs. 67,50,000",
            "Annual maintenance contract (AMC): Rs. 90,000 per year",
            "Product warranty: 10 years",
            "Performance warranty: 25 years (linear, 0.5% per year degradation)",
            "Inverter replacement: Rs. 7,50,000 at 12 years",
            "Payment terms: 30% advance, 60% on delivery, 10% on commissioning",
        ],
    },
    "CoolAir_VRF_350TR_quote.pdf": {
        "title": "QUOTATION - VRF Air Conditioning",
        "lines": [
            "Vendor: CoolAir Systems India Pvt Ltd, Mumbai",
            "Quote ref: CAS/VRF/7781   Date: 14-Oct-2026",
            "Item: VRF air conditioning system, inverter outdoor units",
            "Capacity: 350 TR",
            "Scope: outdoor and indoor units, refrigerant piping, controls, commissioning",
            "Rated ISEER: 5.8 (code-minimum split baseline: 3.8)",
            "",
            "Total price (incl. GST): Rs. 3,15,00,000",
            "Annual maintenance contract (AMC): Rs. 5,25,000 per year",
            "Product warranty: 5 years (compressor 10 years)",
            "Payment terms: 40% advance, 50% on delivery, 10% on commissioning",
        ],
    },
    "ClearView_LowE_Glazing_quote.pdf": {
        "title": "QUOTATION - Low-e Double Glazed Facade",
        "lines": [
            "Vendor: ClearView Facades Ltd, Bengaluru",
            "Quote ref: CVF-2026-218   Date: 15-Oct-2026",
            "Item: Low-e double glazed unit curtain wall",
            "Capacity: 3,000 sq m",
            "Scope: glass units, aluminium framing, installation",
            "Glass: SHGC 0.25, VLT 55%, U-value 1.6 W/sq m K",
            "",
            "Total price (incl. GST): Rs. 2,40,00,000",
            "Annual maintenance contract (AMC): Rs. 0 per year",
            "Product warranty: 10 years",
            "Payment terms: 50% advance, 50% on completion",
        ],
    },
}


def make(name: str, spec: dict) -> None:
    c = canvas.Canvas(str(OUT / name), pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, h - 25 * mm, spec["title"])
    c.setFont("Helvetica", 11)
    y = h - 40 * mm
    for line in spec["lines"]:
        c.drawString(20 * mm, y, line)
        y -= 7 * mm
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(20 * mm, 15 * mm, "ILLUSTRATIVE DUMMY QUOTATION - fictional vendor and prices, created for the CM 617 demo.")
    c.save()


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.pdf"):
        old.unlink()
    for n, s in QUOTES.items():
        make(n, s)
        print("wrote", OUT / n)
