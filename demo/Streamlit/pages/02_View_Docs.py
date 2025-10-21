# --- repo path bootstrap (so imports work when run via streamlit) ---
import sys, pathlib
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]  # .../demo/Streamlit/pages/ -> repo root
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# -------------------------------------------------------------------

import io, re, textwrap
import pathlib as _pl
import requests
import pandas as pd
import streamlit as st
from pypdf import PdfReader

APP_TITLE = "AFSC Docs Viewer (copy-friendly + PDF search)"
st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")
st.title(APP_TITLE)
st.caption("Search the official PDFs or browse pre-split markdown. Copy or send text to Admin Ingest.")

# ----------------------------
# CONFIG
# ----------------------------
# Your two trimmed PDFs in the repo (raw links, not HTML viewer links)
AFECD_URL = "https://raw.githubusercontent.com/Kyleinexile/fall-2025-group6/main/src/docs/AFECD%202025%20Split.pdf"
AFOCD_URL = "https://raw.githubusercontent.com/Kyleinexile/fall-2025-group6/main/src/docs/AFOCD%202025%20Split.pdf"

SOURCES = {
    "AFECD (Enlisted)": AFECD_URL,
    "AFOCD (Officer)": AFOCD_URL,
}

# Where your pre-split markdowns might live (optional)
DOCS_ROOT = _pl.Path("/workspaces/docs_text")
CANDIDATES = [("AFECD", DOCS_ROOT / "AFECD"), ("AFOCD", DOCS_ROOT / "AFOCD")]

# AFSC-ish regex (covers 1N1X1, 1D773, 11FXX, 13A1, 17S3X, etc.)
AFSC_REGEX = r"\b(?:[0-9]{1,2}[A-Z]{1}[A-Z0-9]{0,2})(?:[0-9X]{1,2})\b"

# ----------------------------
# HELPERS
# ----------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def load_pdf_pages(url: str):
    """Return list[dict]: [{page:int, text:str}] for the given PDF."""
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    reader = PdfReader(io.BytesIO(r.content))
    out = []
    for i, p in enumerate(reader.pages):
        try:
            t = p.extract_text() or ""
        except Exception:
            t = ""
        # normalize minor artifacts
        t = re.sub(r"[ \t]+\n", "\n", t)
        t = re.sub(r"\u00ad", "", t)  # soft hyphen
        out.append({"page": i + 1, "text": t})
    return out

def highlight(text: str, pattern: str):
    """Return markdown with light highlighting for matches."""
    try:
        rx = re.compile(pattern, flags=re.IGNORECASE)
    except re.error:
        return text
    return rx.sub(lambda m: f"**`{m.group(0)}`**", text)

@st.cache_data(show_spinner=False, ttl=600)
def build_afsc_index() -> pd.DataFrame:
    rows = []
    for src, folder in CANDIDATES:
        if not folder.exists():
            continue
        for p in folder.glob("*.md"):
            rows.append({"afsc": p.stem, "source": src, "path": str(p)})
    if not rows:
        return pd.DataFrame(columns=["afsc", "source", "path"])
    return pd.DataFrame(rows).sort_values(["source", "afsc"]).reset_index(drop=True)

def send_to_admin_ingest(text: str):
    """Put text into session_state so Admin Ingest page can prefill."""
    st.session_state["admin_ingest_text"] = text
    st.toast("Sent to Admin Ingest. Open the Admin page and it will be prefilled.", icon="✅")

# ----------------------------
# TABS
# ----------------------------
tab_pdf, tab_local = st.tabs(["🔎 PDF Search (AFECD/AFOCD)", "🗂️ Local AFSC Markdown"])

# ===== TAB 1: PDF SEARCH =====
with tab_pdf:
    st.subheader("Search the official trimmed PDFs")
    src = st.selectbox("Source PDF", list(SOURCES.keys()), index=0)
    mode = st.radio("Search mode", ["AFSC code", "Free text"], horizontal=True)
    default_ph = "e.g., 1N1X1 or 11FXX" if mode == "AFSC code" else "e.g., cable and antenna, geospatial"
    q = st.text_input("Search", placeholder=default_ph)

    min_len = st.slider("Min excerpt length (chars)", 160, 800, 360, 20)
    max_hits = st.slider("Max results", 1, 50, 10)

    col_btn1, col_btn2 = st.columns([1, 1])
    do_search = col_btn1.button("Search", type="primary")
    col_btn2.write("")  # spacer

    if do_search:
        if not q.strip():
            st.warning("Type something to search.")
            st.stop()

        url = SOURCES[src]
        try:
            pages = load_pdf_pages(url)
        except Exception as e:
            st.error(f"Could not load PDF: {e}")
            st.stop()

        # Build pattern
        if mode == "AFSC code":
            code = q.strip().upper().replace(" ", "")
            pattern = rf"(?i)\b{re.escape(code)}[A-Z0-9]*\b"
        else:
            # Use regex if it contains metacharacters; else escape for plain contains
            pattern = q if any(c in q for c in ".*?+[]()|") else re.escape(q)

        hits = []
        rx = re.compile(pattern, flags=re.IGNORECASE)

        for rec in pages:
            text = rec["text"]
            if not text:
                continue
            for m in rx.finditer(text):
                start = max(0, m.start() - min_len // 2)
                end = min(len(text), m.end() + min_len // 2)
                snippet = textwrap.shorten(text[start:end].replace("\n", " "), width=min_len, placeholder=" … ")
                hits.append(
                    {"page": rec["page"], "snippet": snippet, "match": m.group(0), "full": text}
                )
                if len(hits) >= max_hits:
                    break
            if len(hits) >= max_hits:
                break

        st.caption(f"Found {len(hits)} match(es) in {src}")
        if not hits:
            st.info("No matches. Try a broader query or switch PDFs.")
        else:
            for i, h in enumerate(hits, 1):
                st.markdown(f"**Result {i} — Page {h['page']}**")
                st.markdown(highlight(h["snippet"], pattern))
                with st.expander("Show full page text"):
                    st.text(h["full"])
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        st.download_button(
                            "⬇️ Download this page text",
                            data=h["full"].encode("utf-8"),
                            file_name=f"{src.replace(' ','_')}_p{h['page']}.txt",
                            mime="text/plain",
                            use_container_width=True,
                            key=f"dl_{src}_{h['page']}_{i}",
                        )
                    with c2:
                        if st.button("📨 Send to Admin Ingest", key=f"send_{src}_{h['page']}_{i}", use_container_width=True):
                            send_to_admin_ingest(h["full"])

    st.markdown("---")
    st.caption(
        "Tip: Use **AFSC code** mode to find exact codes (e.g., *1N1X1*, *11FXX*). "
        "Use **Free text** for duties/knowledge keywords. "
        "Then click **Send to Admin Ingest** and paste/verify there."
    )

# ===== TAB 2: LOCAL MARKDOWN BROWSER =====
with tab_local:
    st.subheader("Browse pre-split AFSC markdown (if available)")
    with st.expander("Location", expanded=False):
        st.code(f"Docs root: {DOCS_ROOT}", language="bash")

    df = build_afsc_index()
    if df.empty:
        st.info("No pre-split markdown found in /workspaces/docs_text/{AFECD,AFOCD}. "
                "Use the PDF Search tab or run your PDF splitter.")
    else:
        q = st.text_input("Find your AFSC", placeholder="e.g., 1N1X1, 11F, ‘cable’, or regex like (?i)^1D7")
        mode = st.radio("Match mode", ["Code/contains", "Regex"], horizontal=True, key="md_mode")

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
        colA, colB = st.columns([1, 3], gap="large")

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
                    text = _pl.Path(path).read_text(encoding="utf-8")
                    st.markdown(text)
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        st.download_button(
                            "⬇️ Download .md",
                            data=text.encode("utf-8"),
                            file_name=f"{chosen['afsc']}.md",
                            mime="text/markdown",
                            use_container_width=True,
                        )
                    with c2:
                        if st.button("📨 Send to Admin Ingest", use_container_width=True, key=f"send_md_{chosen['afsc']}"):
                            send_to_admin_ingest(text)
                except Exception as e:
                    st.error(f"Could not read file: {e}")
            else:
                st.info("Type above to filter, then pick an AFSC on the left.")
