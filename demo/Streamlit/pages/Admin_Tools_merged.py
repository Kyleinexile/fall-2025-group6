from __future__ import annotations
import sys, pathlib, os, io, re, textwrap, json, time
from typing import Dict, Any, List

# Path setup
try:
    from afsc_pipeline.preprocess import clean_afsc_text
except ModuleNotFoundError:
    REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
    SRC = REPO_ROOT / "src"
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    from afsc_pipeline.preprocess import clean_afsc_text

# Imports
import requests
import pandas as pd
import streamlit as st
from neo4j import GraphDatabase
from pypdf import PdfReader
from dotenv import load_dotenv

load_dotenv()

# Pipeline imports
from afsc_pipeline.extract_laiser import extract_ksa_items
from afsc_pipeline.enhance_llm import enhance_items_with_llm
from afsc_pipeline.graph_writer_v2 import upsert_afsc_and_items

# Config
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")

# LLM Config
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "disabled").lower()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Paths
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"

DOCS_ROOTS = [
    pathlib.Path("/workspaces/docs_text"),
    SRC / "docs_text",
]

def _first_existing(*paths):
    for p in paths:
        if p.exists():
            return p
    return paths[-1]

DOCS_ROOT = _first_existing(*DOCS_ROOTS)
DOC_FOLDERS = [("AFECD", DOCS_ROOT / "AFECD"), ("AFOCD", DOCS_ROOT / "AFOCD")]

# PDF Sources
SOURCES = {
    "AFECD (Enlisted)": "https://raw.githubusercontent.com/Kyleinexile/fall-2025-group6/main/src/docs/AFECD%202025%20Split.pdf",
    "AFOCD (Officer)": "https://raw.githubusercontent.com/Kyleinexile/fall-2025-group6/main/src/docs/AFOCD%202025%20Split.pdf",
}

st.set_page_config(page_title="Admin Tools", page_icon="⚙️", layout="wide")

# Auth check
if ADMIN_KEY:
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False
    
    if not st.session_state.admin_authenticated:
        st.title("🔒 Admin Authentication Required")
        key = st.text_input("Enter admin key", type="password")
        if st.button("Unlock"):
            if key.strip() == ADMIN_KEY.strip():
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("Invalid key")
        st.stop()

# Initialize session state
if "search_results" not in st.session_state:
    st.session_state.search_results = None
if "search_info" not in st.session_state:
    st.session_state.search_info = {}
if "admin_loaded_code" not in st.session_state:
    st.session_state.admin_loaded_code = ""
if "admin_loaded_text" not in st.session_state:
    st.session_state.admin_loaded_text = ""

# Main UI
st.title("⚙️ Admin Tools")
st.caption("Browse documents, process AFSC text, and manage the database")

# Sidebar: Connection Status
db_connected = False
with st.sidebar:
    st.markdown("### 🔌 System Status")
    
    # Neo4j
    st.markdown("**Neo4j Database**")
    st.code(f"{NEO4J_URI[:35]}...")
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session(database=NEO4J_DATABASE) as s:
            s.run("RETURN 1").single()
        st.success("✅ Connected")
        db_connected = True
        driver.close()
    except Exception as e:
        st.error("❌ Not connected")
        st.caption(str(e)[:60])
    
    st.markdown("---")
    
    # LLM Status
    st.markdown("**🤖 LLM Enhancement**")
    if LLM_PROVIDER == "disabled":
        st.warning("⚠️ Disabled")
    elif LLM_PROVIDER == "gemini" and GOOGLE_API_KEY:
        st.success("✅ Gemini Active")
    elif LLM_PROVIDER == "anthropic" and ANTHROPIC_API_KEY:
        st.success("✅ Anthropic Active")
    else:
        st.info(f"{LLM_PROVIDER}")
    
    st.markdown("---")
    
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Helper Functions
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

@st.cache_data(ttl=60)
def get_markdown_index():
    rows = []
    for source, folder in DOC_FOLDERS:
        if folder.exists():
            for p in folder.glob("*.md"):
                rows.append({"afsc": p.stem, "source": source, "path": str(p)})
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["afsc", "source", "path"])

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📚 Browse Documents", "🔧 Ingest & Process", "📦 Bulk Upload", "🗑️ Management"])

# ============ TAB 1: Browse Documents ============
with tab1:
    st.markdown("### Browse AFSC Documentation")
    
    mode = st.radio("Source", ["📄 PDF Search", "📁 Markdown Files"], horizontal=True, label_visibility="collapsed")
    
    if mode == "📄 PDF Search":
        col1, col2 = st.columns([1, 3])
        
        with col1:
            source = st.selectbox("PDF", list(SOURCES.keys()))
            search_mode = st.radio("Search by", ["AFSC Code", "Keywords"])
            query = st.text_input("Query", placeholder="1N1X1 or keywords")
            
            with st.expander("⚙️ Options"):
                min_len = st.slider("Excerpt length", 200, 600, 360, 20)
                max_results = st.slider("Max results", 5, 30, 10)
            
            search_btn = st.button("🔍 Search", use_container_width=True, type="primary")
            
            if st.button("Clear", use_container_width=True):
                st.session_state.search_results = None
                st.session_state.search_info = {}
                st.rerun()
        
        with col2:
            if search_btn:
                if not query.strip():
                    st.warning("Enter a search term")
                else:
                    with st.spinner("Searching PDF..."):
                        try:
                            pages = load_pdf_pages(SOURCES[source])
                        except Exception as e:
                            st.error(f"Could not load PDF: {e}")
                            st.stop()
                    
                    # Build pattern
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
                                hits.append({"page": rec["page"], "snippet": snippet, "full": rec["text"]})
                                if len(hits) >= max_results:
                                    break
                            if len(hits) >= max_results:
                                break
                    except Exception as e:
                        st.error(f"Search error: {e}")
                        st.stop()
                    
                    st.session_state.search_results = hits
                    st.session_state.search_info = {"source": source, "pattern": pattern, "query": query}
            
            # Display results
            if st.session_state.search_results is not None:
                hits = st.session_state.search_results
                info = st.session_state.search_info
                
                st.markdown(f"**Found {len(hits)} match(es)**")
                
                if not hits:
                    st.info("No matches found")
                else:
                    for i, h in enumerate(hits, 1):
                        with st.container():
                            st.markdown(f"**Result {i}** • Page {h['page']}")
                            st.markdown(highlight_matches(h["snippet"], info.get("pattern", "")))
                            
                            with st.expander("Full page"):
                                display_text = h["full"][:10000] + "\n..." if len(h["full"]) > 10000 else h["full"]
                                st.text(display_text)
                                
                                col_a, col_b = st.columns(2)
                                with col_a:
                                    st.download_button("⬇️ Download", h["full"], f"page_{h['page']}.txt", key=f"dl_{i}", use_container_width=True)
                                with col_b:
                                    if st.button("→ Load to Ingest", key=f"send_{i}", use_container_width=True):
                                        st.session_state.admin_loaded_text = h["full"]
                                        st.session_state.admin_loaded_code = ""
                                        st.success("✅ Loaded! Go to Ingest & Process tab →")
                            
                            st.markdown("---")
    
    else:  # Markdown Files
        df = get_markdown_index()
        
        if df.empty:
            st.info(f"No markdown files found in {DOCS_ROOT}")
        else:
            col1, col2 = st.columns([1, 3])
            
            with col1:
                sources = ["All"] + sorted(df["source"].unique().tolist())
                src_filter = st.selectbox("Source", sources)
                filtered = df if src_filter == "All" else df[df["source"] == src_filter]
                
                search_text = st.text_input("Filter", placeholder="e.g., 1N1")
                if search_text.strip():
                    filtered = filtered[filtered["afsc"].str.contains(search_text.strip(), case=False)]
                
                st.caption(f"{len(filtered)} files")
                
                options = [f"{r.afsc} ({r.source})" for r in filtered.itertuples()]
                selected = st.selectbox("Select", [""] + options)
            
            with col2:
                if selected:
                    code = selected.split(" ")[0]
                    row = filtered[filtered["afsc"] == code].iloc[0]
                    
                    st.markdown(f"### {code}")
                    st.caption(f"Source: {row['source']}")
                    
                    try:
                        content = pathlib.Path(row["path"]).read_text(encoding="utf-8")
                        
                        with st.expander("📄 Preview", expanded=True):
                            st.markdown(content[:2000] + "\n..." if len(content) > 2000 else content)
                        
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.download_button("⬇️ Download", content, f"{code}.md", use_container_width=True)
                        with col_b:
                            if st.button("→ Load to Ingest", use_container_width=True):
                                st.session_state.admin_loaded_text = content
                                st.session_state.admin_loaded_code = code
                                st.success("✅ Loaded! Go to Ingest & Process tab →")
                    
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.info("👈 Select an AFSC")

# ============ TAB 2: Ingest & Process ============
with tab2:
    st.markdown("### Process Single AFSC")
    
    # Get loaded data
    loaded_code = st.session_state.get("admin_loaded_code", "")
    loaded_text = st.session_state.get("admin_loaded_text", "")
    
    if loaded_text:
        st.info(f"📄 Text loaded ({len(loaded_text)} chars)")
    
    code = st.text_input("AFSC Code", value=loaded_code, placeholder="e.g., 14N")
    text = st.text_area("AFSC Text", value=loaded_text, height=300, placeholder="Paste AFSC documentation here...")
    
    if st.button("🚀 Process", type="primary", disabled=not(code.strip() and text.strip() and db_connected)):
        try:
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            
            with st.status("Processing...", expanded=True) as status:
                # Step 1: Clean
                st.write("🧹 Cleaning text...")
                cleaned_text = clean_afsc_text(text)
                st.write(f"   ✓ Cleaned to {len(cleaned_text)} chars")
                time.sleep(0.3)
                
                # Step 2: LAiSER
                st.write("🔍 LAiSER extracting skills...")
                laiser_items = extract_ksa_items(cleaned_text)
                st.write(f"   ✓ Extracted {len(laiser_items)} items")
                time.sleep(0.3)
                
                # Step 3: LLM
                st.write("🤖 LLM generating Knowledge/Abilities...")
                enhanced_items = enhance_items_with_llm(
                    afsc_code=code.strip(),
                    afsc_text=cleaned_text,
                    items=laiser_items,
                    max_new=6
                )
                st.write(f"   ✓ Generated {len(enhanced_items)} K/A items")
                time.sleep(0.3)
                
                all_items = laiser_items + enhanced_items
                
                # Step 4: Write
                st.write("💾 Writing to Neo4j...")
                with driver.session(database=NEO4J_DATABASE) as session:
                    upsert_afsc_and_items(
                        session=session,
                        afsc_code=code.strip(),
                        items=all_items
                    )
                    st.write(f"   ✓ Wrote {len(all_items)} KSAs")
                
                status.update(label="✅ Complete!", state="complete")
            
            driver.close()
            
            st.success(f"✅ Processed {code}")
            st.balloons()
            
            # Metrics
            k_count = sum(1 for i in all_items if getattr(i.item_type, 'value', str(i.item_type)) == 'knowledge')
            s_count = sum(1 for i in all_items if getattr(i.item_type, 'value', str(i.item_type)) == 'skill')
            a_count = sum(1 for i in all_items if getattr(i.item_type, 'value', str(i.item_type)) == 'ability')
            esco_count = sum(1 for i in all_items if getattr(i, 'esco_id', None))
            
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Total", len(all_items))
            col2.metric("Knowledge", k_count)
            col3.metric("Skills", s_count)
            col4.metric("Abilities", a_count)
            col5.metric("Aligned", esco_count)
            
            st.caption(f"💡 LAiSER: {len(laiser_items)} • LLM: {len(enhanced_items)}")
            
            # Show items
            if all_items:
                with st.expander(f"📊 View {len(all_items)} Items"):
                    df = pd.DataFrame([{
                        "Type": getattr(i.item_type, 'value', str(i.item_type)).upper(),
                        "Text": i.text[:80] + "..." if len(i.text) > 80 else i.text,
                        "Conf": f"{float(getattr(i, 'confidence', 0)):.2f}",
                        "Source": getattr(i, 'source', ''),
                    } for i in all_items])
                    st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Clear button
            if st.button("✨ Process Another", use_container_width=True):
                st.session_state.admin_loaded_code = ""
                st.session_state.admin_loaded_text = ""
                st.rerun()
        
        except Exception as e:
            st.error(f"❌ Failed: {e}")
            import traceback
            with st.expander("Details"):
                st.code(traceback.format_exc())

# ============ TAB 3: Bulk Upload ============
with tab3:
    st.markdown("### Bulk JSONL Processing")
    st.caption("Upload JSONL with fields: `afsc`, `md` or `sections`")
    
    file = st.file_uploader("Upload JSONL", type=["jsonl"])
    
    if file:
        lines = file.getvalue().decode("utf-8").splitlines()
        st.info(f"Found {len(lines)} records")
        
        if st.button("🚀 Process All", type="primary", disabled=not db_connected):
            try:
                from afsc_pipeline.pipeline import run_pipeline
                
                driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
                
                success = fail = 0
                progress = st.progress(0)
                status_text = st.empty()
                
                with driver.session(database=NEO4J_DATABASE) as session:
                    for i, line in enumerate(lines, 1):
                        try:
                            obj = json.loads(line)
                            code = obj.get("afsc", "").strip()
                            text = obj.get("md") or json.dumps(obj.get("sections", {}))
                            
                            if code and text:
                                run_pipeline(code, text, session)
                                success += 1
                            else:
                                fail += 1
                        except Exception:
                            fail += 1
                        
                        progress.progress(i / len(lines))
                        status_text.text(f"{i}/{len(lines)} • ✓ {success} • ✗ {fail}")
                
                driver.close()
                st.success(f"Complete! Success: {success}, Failed: {fail}")
            
            except Exception as e:
                st.error(f"Bulk processing failed: {e}")

# ============ TAB 4: Management ============
with tab4:
    st.markdown("### Database Management")
    st.warning("⚠️ Destructive operations")
    
    codes = st.text_area("AFSCs to delete (comma/space/newline separated)", placeholder="1N1X1, 14N")
    confirm = st.text_input("Type DELETE to confirm")
    
    if st.button("🗑️ Delete", disabled=(confirm != "DELETE" or not db_connected), type="secondary"):
        try:
            afsc_list = [c.strip() for c in re.split(r"[,\s]+", codes) if c.strip()]
            
            if not afsc_list:
                st.error("No AFSCs specified")
            else:
                driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
                with driver.session(database=NEO4J_DATABASE) as s:
                    result = s.run("""
                        MATCH (a:AFSC)
                        WHERE a.code IN $codes
                        OPTIONAL MATCH (a)-[:REQUIRES]->(k:KSA)
                        WITH collect(DISTINCT a) AS afscs, collect(DISTINCT k) AS ksa_nodes
                        
                        UNWIND afscs AS a
                        DETACH DELETE a
                        
                        WITH ksa_nodes
                        UNWIND ksa_nodes AS k
                        WITH DISTINCT k
                        WHERE k IS NOT NULL AND NOT (k)<-[:REQUIRES]-(:AFSC)
                        
                        DETACH DELETE k
                        RETURN count(k) AS ksas_deleted
                    """, {"codes": afsc_list})
                    
                    rec = result.single()
                    ksas_deleted = rec["ksas_deleted"] if rec else 0
                
                driver.close()
                st.success(f"Deleted {len(afsc_list)} AFSCs and {ksas_deleted} orphaned KSAs")
                st.cache_data.clear()
        
        except Exception as e:
            st.error(f"Delete failed: {e}")
    
    st.markdown("---")
    
    if st.button("🔄 Clear All Caches", use_container_width=True):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success("Caches cleared")
