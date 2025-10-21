# --- repo path bootstrap (so imports work when run via streamlit) ---
import sys, pathlib
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]  # .../demo/Streamlit/pages/ -> repo root
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# -------------------------------------------------------------------

import streamlit as st
from pypdf import PdfReader

APP_TITLE = "AFSC Docs Viewer (copy-friendly)"

st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")
st.title(APP_TITLE)
st.caption("Pick a PDF from the repo → select page range → copy extracted text.")

# Where your PDFs live in the repo
DOCS_DIR = SRC / "docs"

# List PDFs
pdf_paths = sorted([p for p in DOCS_DIR.glob("**/*.pdf") if p.is_file()])

with st.expander("Location", expanded=False):
    st.code(f"Docs folder: {DOCS_DIR}", language="bash")

if not pdf_paths:
    st.error("No PDFs found under src/docs/. Make sure you committed + pushed your files.")
    st.stop()

# Picker
pick = st.selectbox(
    "Choose a PDF",
    options=pdf_paths,
    index=0,
    format_func=lambda p: str(p.relative_to(REPO_ROOT))
)

# Load
try:
    reader = PdfReader(str(pick))
    n_pages = len(reader.pages)
except Exception as e:
    st.error(f"Failed to open PDF: {e}")
    st.stop()

# Page range
st.markdown(f"**Pages:** total = {n_pages}")
start, end = st.slider(
    "Select a page range to extract (inclusive)",
    min_value=1, max_value=n_pages,
    value=(1, min(5, n_pages))
)

# Extract
if st.button("Extract text", type="primary"):
    chunks = []
    for i in range(start-1, end):
        try:
            txt = reader.pages[i].extract_text() or ""
        except Exception as e:
            txt = f"[Error reading page {i+1}: {e}]"
        chunks.append(f"--- Page {i+1} ---\n{txt}")
    output = "\n\n".join(chunks)
    st.text_area("Extracted text (copy from here)", output, height=500)
    st.download_button(
        "⬇️ Download as .txt",
        output.encode("utf-8"),
        file_name=f"{pick.stem}_p{start}-{end}.txt",
        mime="text/plain"
    )
# --- AFSC Docs quick-search (paste into your AFSC Docs Viewer page) ---
import os, pathlib, re
import pandas as pd
import streamlit as st

DOCS_ROOT = pathlib.Path("/workspaces/docs_text")  # adjust if different
CANDIDATES = [
    ("AFECD", DOCS_ROOT / "AFECD"),  # enlisted
    ("AFOCD", DOCS_ROOT / "AFOCD"),  # officer
]

@st.cache_data(show_spinner=False)
def build_afsc_index() -> pd.DataFrame:
    rows = []
    for src, folder in CANDIDATES:
        if not folder.exists():
            continue
        for p in folder.glob("*.md"):
            code = p.stem
            rows.append({"afsc": code, "source": src, "path": str(p)})
    df = pd.DataFrame(rows).sort_values(["source", "afsc"]).reset_index(drop=True)
    return df

st.header("AFSC Docs Viewer")
df = build_afsc_index()
if df.empty:
    st.warning("No docs found under /workspaces/docs_text/{AFECD,AFOCD}.")
    st.stop()

# --- Search UI ---
q = st.text_input("Find your AFSC", placeholder="e.g., 1N1X1, 11F, ‘cable’, or regex like (?i)^1D7")
mode = st.radio("Match mode", ["Code/contains", "Regex"], horizontal=True)
filtered = df

if q.strip():
    if mode == "Regex":
        try:
            pat = re.compile(q)
            mask = df["afsc"].str.contains(pat) | df["source"].str.contains(pat)
            filtered = df[mask]
        except re.error:
            st.error("Invalid regex pattern.")
    else:
        s = q.strip().lower()
        mask = df["afsc"].str.lower().str.contains(s) | df["source"].str.lower().str.contains(s)
        filtered = df[mask]

st.caption(f"Found {len(filtered)} / {len(df)}")
colA, colB = st.columns([1,3], gap="large")

with colA:
    pick = st.selectbox(
        "Select AFSC",
        [f"{r.afsc} ({r.source})" for r in filtered.itertuples()],
        index=0 if len(filtered) else None
    )
    chosen = None
    if pick:
        code = pick.split(" ", 1)[0]
        chosen = filtered[filtered["afsc"] == code].iloc[0]

with colB:
    if chosen is not None:
        path = chosen["path"]
        st.subheader(f"{chosen['afsc']} — {chosen['source']}")
        try:
            text = pathlib.Path(path).read_text(encoding="utf-8")
            st.markdown(text)
            st.download_button(
                "⬇️ Download .md",
                data=text.encode("utf-8"),
                file_name=f"{chosen['afsc']}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Could not read file: {e}")
    else:
        st.info("Type above to filter, then pick an AFSC on the left.")
