import sys, pathlib, io, re, textwrap
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import requests
import pandas as pd
import streamlit as st
from pypdf import PdfReader

st.set_page_config(page_title="View Docs", page_icon="📄", layout="wide")

# PDFs
SOURCES = {
    "AFECD (Enlisted)": "https://raw.githubusercontent.com/Kyleinexile/fall-2025-group6/main/src/docs/AFECD%202025%20Split.pdf",
    "AFOCD (Officer)": "https://raw.githubusercontent.com/Kyleinexile/fall-2025-group6/main/src/docs/AFOCD%202025%20Split.pdf",
}

DOCS_ROOT = pathlib.Path("/workspaces/docs_text")
DOC_FOLDERS = [("AFECD", DOCS_ROOT / "AFECD"), ("AFOCD", DOCS_ROOT / "AFOCD")]

# Helper functions
@st.cache_data(show_spinner=False, ttl=3600)
def load_pdf_pages(url: str):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    reader = PdfReader(io.BytesIO(r.content))
    pages = []
    for i, p in enumerate(reader.pages):
        try:
            text = p.extract_text() or ""
            text = re.sub(r"[ \t]+\n", "\n", text)
            text = re.sub(r"\u00ad", "", text)
            pages.append({"page": i + 1, "text": text})
        except:
            pages.append({"page": i + 1, "text": ""})
    return pages

def highlight_matches(text: str, pattern: str) -> str:
    try:
        rx = re.compile(pattern, flags=re.IGNORECASE)
        return rx.sub(lambda m: f"**`{m.group(0)}`**", text)
    except:
        return text

@st.cache_data(ttl=300)
def build_markdown_index():
    rows = []
    for source, folder in DOC_FOLDERS:
        if folder.exists():
            for p in folder.glob("*.md"):
                rows.append({"afsc": p.stem, "source": source, "path": str(p)})
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["afsc", "source", "path"])

# Main UI
st.title("📄 AFSC Documentation")
st.caption("Search official PDFs or browse pre-split markdown files")

# Show if something was sent (for debugging)
if "data_sent" in st.session_state and st.session_state.data_sent:
    st.success("✅ Data sent to Admin Ingest! Navigate there using the sidebar.")
    if st.button("Clear this message"):
        st.session_state.data_sent = False
        st.rerun()

# Mode selection
mode = st.radio("", ["🔍 Search PDFs", "📁 Browse Markdown"], horizontal=True, label_visibility="collapsed")

if mode == "🔍 Search PDFs":
    st.markdown("### Search Official PDFs")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        source = st.selectbox("Source", list(SOURCES.keys()))
        search_mode = st.radio("Search by", ["AFSC Code", "Keywords"], label_visibility="collapsed")
        query = st.text_input(
            "Search",
            placeholder="1N1X1" if search_mode == "AFSC Code" else "cable antenna systems"
        )
        
        with st.expander("⚙️ Options"):
            min_len = st.slider("Excerpt length", 200, 600, 360, 20)
            max_results = st.slider("Max results", 5, 30, 10)
        
        search_btn = st.button("🔍 Search", use_container_width=True, type="primary")
    
    with col2:
        if search_btn:
            if not query.strip():
                st.warning("Enter a search term")
                st.stop()
            
            with st.spinner("Searching PDF..."):
                try:
                    pages = load_pdf_pages(SOURCES[source])
                except Exception as e:
                    st.error(f"Could not load PDF: {e}")
                    st.stop()
            
            # Build search pattern
            if search_mode == "AFSC Code":
                pattern = rf"(?i)\b{re.escape(query.strip().upper())}[A-Z0-9]*\b"
            else:
                pattern = re.escape(query) if not any(c in query for c in ".*?+[]()") else query
            
            # Search
            hits = []
            try:
                rx = re.compile(pattern, flags=re.IGNORECASE)
                for rec in pages:
                    if not rec["text"]:
                        continue
                    for m in rx.finditer(rec["text"]):
                        start = max(0, m.start() - min_len // 2)
                        end = min(len(rec["text"]), m.end() + min_len // 2)
                        snippet = rec["text"][start:end].replace("\n", " ")
                        snippet = textwrap.shorten(snippet, width=min_len, placeholder="...")
                        hits.append({
                            "page": rec["page"],
                            "snippet": snippet,
                            "full": rec["text"]
                        })
                        if len(hits) >= max_results:
                            break
                    if len(hits) >= max_results:
                        break
            except Exception as e:
                st.error(f"Search error: {e}")
                st.stop()
            
            # Display results
            st.markdown(f"**Found {len(hits)} match(es)** in {source}")
            
            if not hits:
                st.info("No matches found. Try different keywords or switch sources.")
            else:
                for i, h in enumerate(hits, 1):
                    with st.container():
                        st.markdown(f"**Result {i}** • Page {h['page']}")
                        st.markdown(highlight_matches(h["snippet"], pattern))
                        
                        with st.expander("View full page"):
                            st.text(h["full"])
                            
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.download_button(
                                    "⬇️ Download",
                                    h["full"],
                                    f"page_{h['page']}.txt",
                                    use_container_width=True,
                                    key=f"dl_{i}"
                                )
                            with col_b:
                                if st.button("📤 Send to Ingest", key=f"send_{i}", use_container_width=True):
                                    # Set the session state
                                    st.session_state.admin_loaded_text = h["full"]
                                    st.session_state.admin_loaded_code = ""
                                    st.session_state.data_sent = True
                                    st.success("✅ Data saved! Now go to **Admin Ingest** using the sidebar →")
                        
                        st.markdown("---")

else:  # Browse Markdown
    st.markdown("### Browse Pre-Split Files")
    
    df = build_markdown_index()
    
    if df.empty:
        st.info(f"No markdown files found in {DOCS_ROOT}")
        st.caption("Use the PDF splitter tool to generate them first")
    else:
        col1, col2 = st.columns([1, 3])
        
        with col1:
            # Filter controls
            sources = ["All"] + sorted(df["source"].unique().tolist())
            src_filter = st.selectbox("Source", sources)
            
            filtered = df if src_filter == "All" else df[df["source"] == src_filter]
            
            search_text = st.text_input("Filter AFSC", placeholder="e.g., 1N1, 11F")
            if search_text.strip():
                filtered = filtered[filtered["afsc"].str.contains(search_text.strip(), case=False)]
            
            st.caption(f"Showing {len(filtered)} of {len(df)}")
            
            # Select AFSC
            options = [f"{r.afsc} ({r.source})" for r in filtered.itertuples()]
            selected = st.selectbox("Select AFSC", options if options else ["<none>"])
        
        with col2:
            if selected and selected != "<none>":
                code = selected.split(" ")[0]
                row = filtered[filtered["afsc"] == code].iloc[0]
                
                st.markdown(f"### {code}")
                st.caption(f"Source: {row['source']}")
                
                try:
                    content = pathlib.Path(row["path"]).read_text(encoding="utf-8")
                    
                    # Show preview
                    with st.expander("📄 Preview", expanded=True):
                        st.markdown(content[:2000] + "\n\n..." if len(content) > 2000 else content)
                    
                    # Actions
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.download_button(
                            "⬇️ Download Markdown",
                            content,
                            f"{code}.md",
                            use_container_width=True
                        )
                    with col_b:
                        if st.button("📤 Send to Ingest", use_container_width=True):
                            st.session_state.admin_loaded_text = content
                            st.session_state.admin_loaded_code = code
                            st.session_state.data_sent = True
                            st.success("✅ Data saved! Now go to **Admin Ingest** using the sidebar →")
                    
                except Exception as e:
                    st.error(f"Could not read file: {e}")
            else:
                st.info("👈 Select an AFSC from the sidebar")

# Help section
with st.sidebar:
    with st.expander("💡 Help"):
        st.markdown("""
        **PDF Search**: Find AFSCs or keywords in official documents
        
        **Markdown Browser**: View pre-processed AFSC files
        
        **Workflow**:
        1. Find your AFSC here
        2. Click "Send to Ingest"
        3. Go to Admin Ingest (sidebar)
        4. Process through pipeline
        5. Explore in main app
        """)
    
    # Debug info
    with st.expander("🐛 Debug Info"):
        st.write("Session State Keys:", list(st.session_state.keys()))
        if "admin_loaded_text" in st.session_state:
            text_len = len(st.session_state.admin_loaded_text)
            st.write(f"Text loaded: {text_len} chars")
