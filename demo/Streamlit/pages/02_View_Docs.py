# --- repo path bootstrap ---
import sys, pathlib
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]  # repo root
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# ---------------------------

import streamlit as st
from pypdf import PdfReader  # pip install pypdf

st.set_page_config(page_title="AFSC Docs Viewer", page_icon="📄", layout="wide")
st.title("AFSC Docs Viewer (Copy-Friendly)")
st.caption("Use the URL preview for hosted PDFs, or upload a PDF to extract selectable text.")

# Option 1: Preview a hosted PDF via URL (e.g., GitHub Pages / Drive preview link)
pdf_url = st.text_input("PDF URL (optional)", placeholder="https://.../AFECD-2025-04-30.pdf")
if pdf_url:
    st.components.v1.iframe(pdf_url, height=700)

st.markdown("---")

# Option 2: Upload a PDF and extract text (best for copy/paste)
uploaded = st.file_uploader("Or upload a PDF to extract text", type=["pdf"])
if uploaded:
    try:
        reader = PdfReader(uploaded)
        parts = []
        for i, page in enumerate(reader.pages, 1):
            # pypdf uses .extract_text()
            parts.append(f"\n\n--- Page {i} ---\n")
            parts.append(page.extract_text() or "")
        text = "".join(parts).strip()

        if not text:
            st.warning("No selectable text found. This PDF is likely a scanned image. Use OCR (e.g., Google Drive \"Open with Google Docs\" or Tesseract) and re-upload.")

        st.text_area("Extracted text", value=text, height=500)
        if text:
            st.download_button("Download extracted text", text, file_name="extracted.txt")
    except Exception as e:
        st.error(f"Failed to read PDF: {e}\nIf this is a scanned PDF, run OCR first and try again.")
