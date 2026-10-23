"""Regenerate the entry index at the top of PROJECT_LOG.md.

Every table row that starts with an ID (D-001, W-003, X-004, Q-002 ...) is listed with a one-line title and a
link to its section. Run after editing the log:   python scripts/update_log_index.py
"""
import re
import sys
from datetime import date
from pathlib import Path

_REPO_LOG = Path(__file__).resolve().parents[1] / "docs" / "PROJECT_LOG.md"  # standalone repo layout
LOG = Path(sys.argv[1]) if len(sys.argv) > 1 else (_REPO_LOG if _REPO_LOG.exists() else Path(__file__).resolve().parents[2] / "PROJECT_LOG.md")
START, END = "<!-- ENTRY-INDEX:START -->", "<!-- ENTRY-INDEX:END -->"
SECTIONS = {"D": ("Decisions", "#2-decisions"), "W": ("What worked", "#3-what-worked"),
            "X": ("What didn't / dropped", "#4-what-didnt--dropped"), "Q": ("Open questions", "#5-open-questions")}


def clean(cell: str) -> str:
    cell = re.sub(r"\*\*|`", "", cell)
    return cell if len(cell) <= 95 else cell[:92].rstrip() + "..."


text = LOG.read_text(encoding="utf-8")
body = text.split(END, 1)[1] if END in text else text
entries = {k: [] for k in SECTIONS}
for line in body.splitlines():
    m = re.match(r"^\|\s*([DWXQ])-(\d+)\s*\|\s*(.+?)\s*\|", line)
    if m:
        entries[m.group(1)].append((f"{m.group(1)}-{m.group(2)}", clean(m.group(3))))

out = [START, f"*Entry index, auto-generated {date.today():%Y-%m-%d} by `greenlcc/scripts/update_log_index.py`. "
       f"{sum(len(v) for v in entries.values())} entries.*", ""]
for k, (name, anchor) in SECTIONS.items():
    out.append(f"**[{name}]({anchor})** ({len(entries[k])})")
    out += [f"- `{i}` {t}" for i, t in sorted(entries[k])]
    out.append("")
out.append(END)
block = "\n".join(out)

if START in text:
    text = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S)
else:  # first run: insert right after the section index
    text = text.replace("\n---\n\n## 1. Problem", f"\n### Entry index\n\n{block}\n\n---\n\n## 1. Problem", 1)
LOG.write_text(text, encoding="utf-8")
print(f"index updated: {sum(len(v) for v in entries.values())} entries -> {LOG}")
