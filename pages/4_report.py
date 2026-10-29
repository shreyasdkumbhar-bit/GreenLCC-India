import json

import streamlit as st

from core import exports, report, state, ui
from core.io import write_workbook
from core.schemas import Dataset

ui.page_header(4, "Take it away", "Three files cover everyone: a PDF for the owner and the prof, an Excel workbook for whoever checks "
               "the numbers, and the input workbook to reopen or edit this exact setup later.")
ds = ui.require_ds()
target, df, rec, cheap = state.recommendation(ds)
if rec is None:
    ui.unreachable(ds, df, target)


@st.cache_data(show_spinner="Writing the report and workbook…")
def _files(ds_json: str, target: str) -> dict:
    return exports.build_files(Dataset.model_validate_json(ds_json), target)


F = _files(ds.model_dump_json(), target)
res = F["res"]
slug = "".join(c if c.isalnum() else "_" for c in ds.project.name).strip("_").lower()[:40] or "project"

FILES = [
    ("Decision report", "PDF · 6 pages", ":material/picture_as_pdf:",
     "The answer, the two routes compared with the incremental rate of return, the IGBC credit checklist, what to buy "
     "(PW, EUAC, BCR, IRR/MIRR), the risk check, assumptions and the yearly cash flow.",
     "Owner, consultant, prof", F["pdf"], f"greenlcc_report_{slug}.pdf", "application/pdf"),
    ("Results workbook", "Excel · 10 sheets", ":material/table:",
     "Every number unrounded: summary, checklist, shopping list, yearly cash flow, all simulated futures, "
     "the top 200 mixes and every input.",
     "Whoever checks the maths", F["xlsx"], f"greenlcc_results_{slug}.xlsx",
     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ("Input workbook", "Excel · edit and reopen", ":material/save:",
     "This building, its measures and the IGBC tables, with units and meanings. Edit it in Excel and open it from Home.",
     "You, next time", write_workbook(ds.model_copy(update={"project": ds.project.model_copy(update={"target_level": target})})),
     f"{slug}_input.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
]
cols = st.columns(3)
for i, (title, kind, icon, desc, who, data, fname, mime) in enumerate(FILES):
    with cols[i]:
        with st.container(border=True, height="stretch"):
            st.markdown(f"#### {title}")
            st.caption(f"{kind} · for: **{who}**")
            st.write(desc)
            st.download_button("Download", data, file_name=fname, mime=mime, icon=icon, key=f"dl_{i}",
                               type="primary" if i == 0 else "secondary", width="stretch")

st.write("")
st.markdown("#### Owner memo")
use_ai = st.toggle("Polish the wording with Claude (needs ANTHROPIC_API_KEY)", value=False,
                   help="The AI only sees the computed numbers and is told never to change them. Off = the built-in template.")
text, method = report.narrative(res) if use_ai else (F["memo"], "template")
with st.container(border=True):
    st.markdown(text)
st.caption(f"Written by: **{method}**. " + ("The PDF report opens with this summary." if method == "template" else "The PDF keeps the template wording."))
with st.expander("Copy the memo text"):
    st.code(text, language="markdown")
with st.expander("Numbers behind the memo (for checking)"):
    st.json(json.loads(json.dumps(res, default=float)))
