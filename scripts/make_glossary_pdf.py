"""Build docs/GreenLCC_Glossary.pdf: every term the tool uses, what it means, where it comes from in CE 725,
and why it matters for the decision. Content lives in core/glossary.py.

Run:  python scripts/make_glossary_pdf.py  [output_dir]
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4, landscape  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer  # noqa: E402

from core import finance  # noqa: E402
from core.exports import DEEP, INK2, grid_table, safe, styles  # noqa: E402
from core.glossary import SECTIONS, TERMS  # noqa: E402
from core.io import load_dataset  # noqa: E402

OUT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs"
PAGE = landscape(A4)
W = PAGE[0] - 30 * mm
st = styles()


def P(text: str, style: str = "body") -> Paragraph:
    return Paragraph(safe(text).replace("CO₂", "CO<sub>2</sub>").replace("CO2", "CO<sub>2</sub>"), st[style])


def pdf_text(t: str) -> str:
    """Symbols the base-14 PDF fonts lack: spell them out before safe() would turn them into '?'."""
    return t.replace("CO₂", "CO2").replace("Σ", "sum of")


def frame(canvas, doc):
    canvas.saveState()
    w, h = PAGE
    canvas.setFillColor(colors.HexColor(DEEP))
    canvas.rect(0, h - 8 * mm, w, 8 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(15 * mm, h - 5.4 * mm, "GreenLCC India  ·  Glossary of terms")
    canvas.setFillColor(colors.HexColor(INK2))
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(15 * mm, 8 * mm, "CM 617 · Topic 6 · course references are CE 725 chapters (Ch) and syllabus modules.")
    canvas.drawRightString(w - 15 * mm, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build(path: Path) -> None:
    ds, errs = load_dataset()
    assert not errs, errs
    p = ds.project
    story = [
        Paragraph("Glossary: every term, what it means, why it matters", st["title"]),
        P(f"{len(TERMS)} terms in {len(SECTIONS)} groups · demo values: MARR {p.discount_rate:.0%}, inflation {p.inflation:.0%} "
          f"(real MARR {finance.real_rate(p.discount_rate, p.inflation):.2%}), N = {p.study_period} years · {date.today():%d %b %Y}", "sub"),
        P("How to read it: <b>Meaning</b> gives the plain definition and formula; <b>Course link</b> is where it is taught in CE 725; "
          "<b>In GreenLCC</b> says where the term appears in the tool and how it changes the decision."),
    ]
    for sec in SECTIONS:
        rows = [["Term", "Meaning (and formula)", "Course link", "In GreenLCC / why it matters"]]
        rows += [[f"<b>{pdf_text(t)}</b>", pdf_text(m), c, pdf_text(w)] for s, t, m, c, w, _ in TERMS if s == sec]
        story += [Paragraph(safe(sec), st["h2"]), grid_table(rows, [W * .17, W * .38, W * .11, W * .34], st), Spacer(1, 4)]
    doc = SimpleDocTemplate(str(path), pagesize=PAGE, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=15 * mm,
                            title="GreenLCC India - Glossary", author="GreenLCC India")
    doc.build(story, onFirstPage=frame, onLaterPages=frame)


if __name__ == "__main__":
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / "GreenLCC_Glossary.pdf"
    build(out)
    print("wrote", out)
