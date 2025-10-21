from __future__ import annotations
import sys, pathlib, os, json, time, re
from typing import Dict, Any, List

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
import streamlit as st
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

from afsc_pipeline.preprocess import clean_afsc_text
from afsc_pipeline.pipeline import run_pipeline, ItemDraft

# Config
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")

DOCS_ROOT = pathlib.Path("/workspaces/docs_text")
DOC_FOLDERS = [("AFECD", DOCS_ROOT / "AFECD"), ("AFOCD", DOCS_ROOT / "AFOCD")]

st.set_page_config(page_title="Admin Ingest", page_icon="🔧", layout="wide")

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

# Main UI
st.title("🔧 Admin: AFSC Ingest")
st.caption("Process AFSC documentation through the extraction pipeline")

# Connection status in sidebar
with st.sidebar:
    st.markdown("### Connection")
    st.code(f"URI: {NEO4J_URI[:30]}...")
    st.code(f"DB: {NEO4J_DATABASE}")
    
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session(database=NEO4J_DATABASE) as s:
            s.run("RETURN 1").single()
        st.success("✅ Connected")
        driver.close()
    except Exception:
        st.error("❌ Connection failed")

# Tabs for different ingest methods
tab1, tab2, tab3 = st.tabs(["📝 Manual Entry", "📁 Bulk JSONL", "🗑️ Management"])

# ============ TAB 1: Manual Entry ============
with tab1:
    st.markdown("### Single AFSC Processing")
    
    # Two-column layout
    col_load, col_process = st.columns([1, 2])
    
    with col_load:
        st.markdown("#### Load from Docs")
        
        @st.cache_data(ttl=60)
        def get_afsc_list():
            items = []
            for source, folder in DOC_FOLDERS:
                if folder.exists():
                    for p in folder.glob("*.md"):
                        items.append(f"{p.stem} ({source})")
            return sorted(items)
        
        docs = get_afsc_list()
        if docs:
            selected = st.selectbox("Select pre-split doc", [""] + docs)
            if selected and st.button("📂 Load", use_container_width=True):
                code = selected.split(" ")[0]
                source = selected.split("(")[1].rstrip(")")
                folder = DOCS_ROOT / source
                path = folder / f"{code}.md"
                try:
                    text = path.read_text(encoding="utf-8")
                    st.session_state["admin_loaded_code"] = code
                    st.session_state["admin_loaded_text"] = text
                    st.success(f"✅ Loaded {code}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.info("No pre-split docs found")
            
        st.markdown("---")
        st.caption("Or use the form →")
    
    with col_process:
        st.markdown("#### Process AFSC")
        
        # Show indicator if data was loaded from View Docs
        if st.session_state.get("admin_loaded_text"):
            st.success("✅ Text loaded from View Docs page")
        
        code = st.text_input(
            "AFSC Code",
            value=st.session_state.get("admin_loaded_code", ""),
            placeholder="e.g., 1N1X1"
        )
        
        text = st.text_area(
            "AFSC Text",
            value=st.session_state.get("admin_loaded_text", ""),
            height=300,
            placeholder="Paste duties, knowledge, skills, and abilities..."
        )
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("👀 Preview Clean", use_container_width=True, disabled=not text):
                cleaned = clean_afsc_text(text)
                with st.expander("Cleaned Text Preview"):
                    st.text(cleaned[:1000] + "..." if len(cleaned) > 1000 else cleaned)
                    st.caption(f"Original: {len(text)} chars → Cleaned: {len(cleaned)} chars")
        
        with col_btn2:
            if st.button("🗑️ Clear Form", use_container_width=True):
                st.session_state["admin_loaded_code"] = ""
                st.session_state["admin_loaded_text"] = ""
                st.rerun()
        
        process = st.button("🚀 Process", type="primary", use_container_width=True, disabled=not (code and text))
        
        if process:
            try:
                driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
                
                with st.status("Processing...", expanded=True) as status:
                    st.write("🧹 Cleaning text...")
                    time.sleep(0.5)
                    st.write("🔍 Extracting items...")
                    
                    with driver.session(database=NEO4J_DATABASE) as session:
                        summary = run_pipeline(
                            afsc_code=code.strip(),
                            afsc_raw_text=text,
                            neo4j_session=session
                        )
                    
                    st.write("✅ Writing to Neo4j...")
                    status.update(label="Complete!", state="complete")
                
                driver.close()
                
                # Results
                st.success(f"Processed {code}")
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Raw Items", summary.get("n_items_raw", 0))
                m2.metric("After Filters", summary.get("n_items_after_filters", 0))
                m3.metric("After Dedupe", summary.get("n_items_after_dedupe", 0))
                m4.metric("Fallback Used", "Yes" if summary.get("used_fallback") else "No")
                
                # Show items
                items = summary.get("items", [])
                if items:
                    with st.expander(f"📊 View {len(items)} Items", expanded=True):
                        df = pd.DataFrame([{
                            "text": i.text[:80] + "..." if len(i.text) > 80 else i.text,
                            "type": i.item_type.value if hasattr(i.item_type, "value") else str(i.item_type),
                            "conf": f"{float(getattr(i, 'confidence', 0)):.2f}",
                            "esco": getattr(i, "esco_id", "")[:20]
                        } for i in items])
                        st.dataframe(df, use_container_width=True, hide_index=True)
                
                st.info("💡 View results in the Explore page")
                
                # Clear loaded data after successful processing
                if st.button("✨ Process Another AFSC", use_container_width=True):
                    st.session_state["admin_loaded_code"] = ""
                    st.session_state["admin_loaded_text"] = ""
                    st.rerun()
                
            except Exception as e:
                st.error(f"Processing failed: {e}")

# ============ TAB 2: Bulk JSONL ============
with tab2:
    st.markdown("### Bulk Processing")
    st.caption("Upload JSONL with one AFSC per line (fields: `afsc`, `md` or `sections`)")
    
    file = st.file_uploader("Upload JSONL", type=["jsonl"])
    
    if file:
        lines = file.getvalue().decode("utf-8").splitlines()
        st.info(f"Found {len(lines)} records")
        
        if st.button("🚀 Process All", type="primary"):
            try:
                driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
                
                success = fail = 0
                progress_bar = st.progress(0)
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
                        except:
                            fail += 1
                        
                        progress_bar.progress(i / len(lines))
                        status_text.text(f"Processing {i}/{len(lines)} • ✓ {success} • ✗ {fail}")
                
                driver.close()
                st.success(f"Complete! Success: {success}, Failed: {fail}")
                
            except Exception as e:
                st.error(f"Bulk processing failed: {e}")

# ============ TAB 3: Management ============
with tab3:
    st.markdown("### Database Management")
    
    st.warning("⚠️ Destructive operations - use with caution")
    
    codes = st.text_area(
        "AFSC codes to delete (comma/space/newline separated)",
        placeholder="1N1X1, 17S3X, 1D7"
    )
    
    confirm = st.text_input("Type DELETE to confirm")
    
    if st.button("🗑️ Delete AFSCs", disabled=(confirm != "DELETE"), type="secondary"):
        try:
            afsc_list = [c.strip() for c in re.split(r"[,\s]+", codes) if c.strip()]
            
            if not afsc_list:
                st.error("No AFSCs specified")
            else:
                driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
                with driver.session(database=NEO4J_DATABASE) as s:
                    # Delete relationships and orphaned items
                    s.run("""
                        MATCH (a:AFSC)-[r:HAS_ITEM|REQUIRES]->(i:Item)
                        WHERE a.code IN $codes
                        DELETE r
                        WITH i
                        WHERE NOT ()-[:HAS_ITEM|REQUIRES]->(i)
                        DELETE i
                    """, {"codes": afsc_list})
                    
                    # Delete AFSCs
                    s.run("MATCH (a:AFSC) WHERE a.code IN $codes DETACH DELETE a", 
                          {"codes": afsc_list})
                
                driver.close()
                st.success(f"Deleted: {', '.join(afsc_list)}")
                st.cache_data.clear()
                
        except Exception as e:
            st.error(f"Delete failed: {e}")
    
    st.markdown("---")
    
    if st.button("🔄 Clear All Caches"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success("Caches cleared")
