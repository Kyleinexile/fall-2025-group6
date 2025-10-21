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
