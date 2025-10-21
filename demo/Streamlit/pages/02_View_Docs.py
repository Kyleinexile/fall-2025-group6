# --- repo path bootstrap ---
import sys, pathlib
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))
# ---------------------------

import streamlit as st
from PyPDF2 import PdfReader  # pip install pypdf (modern PyPDF2)

st.set_page_config(page_title="AFSC Docs Viewer", page_icon="📄", layout="wide")
st.title("AFSC Docs Viewer (Copy-Friendly)")

# Option 1: Use a hosted PDF (GitHub Pages or Drive preview)
pdf_url = st.text_input("PDF URL", placeholder="https://.../AFOCD_2025-04-30.pdf")
if pdf_url:
    st.components.v1.iframe(pdf_url, height=700)

st.markdown("---")

# Option 2: Upload and extract text (guaranteed copyable)
uploaded = st.file_uploader("Or upload a PDF to extract text", type=["pdf"])
if uploaded:
    try:
        reader = PdfReader(uploaded)
        parts = []
        for i, page in enumerate(reader.pages, 1):
            parts.append(f"\n\n--- Page {i} ---\n")
            parts.append(page.extract_text() or "")
        text = "".join(parts).strip()
        if not text:
            st.warning("No selectable text found (likely a scanned PDF). You’ll need OCR.")
        st.text_area("Extracted text", value=text, height=500)
        st.download_button("Download extracted text", text, file_name="extracted.txt")
    except Exception as e:
        st.error(f"Failed to read PDF: {e}\nIf this is a scanned PDF, run OCR first.")
