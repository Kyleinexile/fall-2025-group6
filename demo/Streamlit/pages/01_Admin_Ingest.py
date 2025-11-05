from __future__ import annotations
import sys, pathlib, os

# Try to import - if it fails, fix the path and retry
try:
    from afsc_pipeline.preprocess import clean_afsc_text
except ModuleNotFoundError:
    # Path setup for Streamlit Cloud
    REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
    SRC = REPO_ROOT / "src"
    
    # DEBUG: Print what we calculated
    print(f"[DEBUG] __file__ = {__file__}")
    print(f"[DEBUG] REPO_ROOT = {REPO_ROOT}")
    print(f"[DEBUG] SRC = {SRC}")
    print(f"[DEBUG] SRC exists? {SRC.exists()}")
    print(f"[DEBUG] REPO_ROOT contents: {list(REPO_ROOT.glob('*')) if REPO_ROOT.exists() else 'DOES NOT EXIST'}")
    
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    
    print(f"[DEBUG] sys.path[0] = {sys.path[0]}")
    
    # Retry import
    from afsc_pipeline.preprocess import clean_afsc_text

# Now import everything else
import json, time, re
from typing import Dict, Any, List
import pandas as pd
import streamlit as st
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError
from dotenv import load_dotenv
load_dotenv()

# Other local imports
from afsc_pipeline.pipeline import run_pipeline, ItemDraft
from afsc_pipeline.extract_laiser import extract_ksa_items
from afsc_pipeline.enhance_llm import enhance_items_with_llm

# Config
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")

# NEW: LLM Config
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "disabled").lower()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Path fallback for both Codespaces and Streamlit Cloud
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"

DOCS_ROOTS = [
    pathlib.Path("/workspaces/docs_text"),  # Codespaces
    SRC / "docs_text",  # Fallback to repo
]

def _first_existing(*paths):
    for p in paths:
        if p.exists():
            return p
    return paths[-1]

DOCS_ROOT = _first_existing(*DOCS_ROOTS)
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
st.caption("Process AFSC documentation through the LAiSER + LLM extraction pipeline")

# Connection status check
db_connected = False
with st.sidebar:
    st.markdown("### 🔌 Connections")
    
    # Neo4j Status
    st.markdown("**Neo4j Database**")
    st.code(f"URI: {NEO4J_URI[:30]}...")
    st.code(f"DB: {NEO4J_DATABASE}")
    
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session(database=NEO4J_DATABASE) as s:
            s.run("RETURN 1").single()
        st.success("✅ Connected")
        db_connected = True
        driver.close()
    except Exception as e:
        st.error("❌ Connection failed")
        st.caption(str(e)[:100])
    
    st.markdown("---")
    
    # NEW: LLM Enhancement Status
    st.markdown("**🤖 LLM Enhancement**")
    if LLM_PROVIDER == "disabled":
        st.warning("⚠️ Disabled (using heuristics)")
        st.caption("Set GOOGLE_API_KEY for better K/A extraction")
    elif LLM_PROVIDER == "gemini":
        if GOOGLE_API_KEY:
            st.success("✅ Gemini Active")
            if ANTHROPIC_API_KEY:
                st.caption("Anthropic fallback available")
        else:
            st.error("❌ Key not set")
    elif LLM_PROVIDER == "anthropic":
        if ANTHROPIC_API_KEY:
            st.success("✅ Anthropic Active")
        else:
            st.error("❌ Key not set")
    else:
        st.info(f"Provider: {LLM_PROVIDER}")

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
                    st.session_state.admin_loaded_code = code
                    st.session_state.admin_loaded_text = text
                    st.session_state.data_sent = True
                    st.success(f"✅ Loaded {code}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.info("No pre-split docs found")
            st.caption(f"Looking in: {DOCS_ROOT}")
            
        st.markdown("---")
        st.caption("Or use the form →")
    
    with col_process:
        st.markdown("#### Process AFSC")
        
        # Get values from session state
        loaded_code = st.session_state.get("admin_loaded_code", "")
        loaded_text = st.session_state.get("admin_loaded_text", "")
        
        # Show indicator if data was loaded from View Docs
        if st.session_state.get("data_sent") and loaded_text:
            st.info("📄 Text preloaded from Docs Viewer")
            st.session_state.data_sent = False  # Clear flag
        
        code = st.text_input(
            "AFSC Code",
            value=loaded_code,
            placeholder="e.g., 1N1X1",
            key="afsc_code_input"
        )
        
        text = st.text_area(
            "AFSC Text",
            value=loaded_text,
            height=300,
            placeholder="Paste duties, knowledge, skills, and abilities...",
            key="afsc_text_input"
        )
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("👀 Preview Clean", use_container_width=True, disabled=not text):
                cleaned = clean_afsc_text(text)
                lines = [l for l in cleaned.split('\n') if l.strip()]
                with st.expander("Cleaned Text Preview", expanded=True):
                    st.text(cleaned[:1000] + "..." if len(cleaned) > 1000 else cleaned)
                    st.caption(f"Original: {len(text)} chars → Cleaned: {len(cleaned)} chars • {len(lines)} lines")
        
        with col_btn2:
            if st.button("🗑️ Clear Form", use_container_width=True):
                st.session_state.admin_loaded_code = ""
                st.session_state.admin_loaded_text = ""
                st.rerun()
        
        # Disable process button if DB not connected
        process = st.button(
            "🚀 Process with LAiSER + LLM", 
            type="primary", 
            use_container_width=True, 
            disabled=not (code and text and db_connected)
        )
        
        if not db_connected:
            st.warning("⚠️ Database not connected - fix connection to enable processing")
        
        if process:
            try:
                driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
                
                with st.status("Processing with LAiSER + LLM...", expanded=True) as status:
                    # Step 1: Clean text
                    st.write("🧹 Cleaning text...")
                    cleaned_text = clean_afsc_text(text)
                    time.sleep(0.3)
                    
                    # Step 2: LAiSER extraction
                    st.write("🔍 LAiSER: Extracting skills...")
                    laiser_items = extract_ksa_items(cleaned_text)
                    st.write(f"   ✓ Found {len(laiser_items)} items from LAiSER")
                    time.sleep(0.3)
                    
                    # Step 3: LLM enhancement
                    st.write(f"🤖 LLM ({LLM_PROVIDER}): Adding Knowledge/Abilities...")
                    enhanced_items = enhance_items_with_llm(
                        afsc_code=code.strip(),
                        afsc_text=cleaned_text,
                        items=laiser_items,
                        max_new=6
                    )
                    st.write(f"   ✓ Generated {len(enhanced_items)} K/A items")
                    time.sleep(0.3)
                    
                    # Combine items
                    all_items = laiser_items + enhanced_items
                    
                    # Step 4: Write to Neo4j
                    st.write("💾 Writing to Neo4j...")
                    with driver.session(database=NEO4J_DATABASE) as session:
                        # Create AFSC node
                        session.run("""
                            MERGE (a:AFSC {code: $code})
                            ON CREATE SET a.created_at = datetime()
                            SET a.updated_at = datetime()
                        """, {"code": code.strip()})
                        
                        # Create KSA nodes and relationships
                        for item in all_items:
                            session.run("""
                                MERGE (k:Item {text: $text, item_type: $item_type})
                                ON CREATE SET 
                                    k.confidence = $confidence,
                                    k.source = $source,
                                    k.esco_id = $esco_id,
                                    k.created_at = datetime()
                                WITH k
                                MATCH (a:AFSC {code: $code})
                                MERGE (a)-[:HAS_ITEM]->(k)
                            """, {
                                "text": item.text,
                                "item_type": item.item_type.value if hasattr(item.item_type, 'value') else str(item.item_type),
                                "confidence": float(getattr(item, 'confidence', 0)),
                                "source": getattr(item, 'source', 'unknown'),
                                "esco_id": getattr(item, 'esco_id', None),
                                "code": code.strip()
                            })
                    
                    status.update(label="✅ Complete!", state="complete")
                
                driver.close()
                
                # Results Summary
                st.success(f"✅ Processed {code}")
                st.balloons()
                
                # Count by type
                k_count = sum(1 for i in all_items if getattr(i.item_type, 'value', str(i.item_type)) == 'knowledge')
                s_count = sum(1 for i in all_items if getattr(i.item_type, 'value', str(i.item_type)) == 'skill')
                a_count = sum(1 for i in all_items if getattr(i.item_type, 'value', str(i.item_type)) == 'ability')
                esco_count = sum(1 for i in all_items if getattr(i, 'esco_id', None))
                
                # Metrics
                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("Total KSAs", len(all_items))
                col2.metric("Knowledge", k_count)
                col3.metric("Skills", s_count)
                col4.metric("Abilities", a_count)
                col5.metric("ESCO IDs", esco_count)
                
                # Show contribution breakdown
                st.caption(f"💡 LAiSER: {len(laiser_items)} items ({len(laiser_items)/len(all_items)*100:.0f}%) • LLM: {len(enhanced_items)} items ({len(enhanced_items)/len(all_items)*100:.0f}%)")
                
                # Show items
                if all_items:
                    with st.expander(f"📊 View {len(all_items)} Extracted Items", expanded=False):
                        df = pd.DataFrame([{
                            "Type": getattr(i.item_type, 'value', str(i.item_type)).upper(),
                            "Text": i.text[:80] + "..." if len(i.text) > 80 else i.text,
                            "Confidence": f"{float(getattr(i, 'confidence', 0)):.2f}",
                            "Source": getattr(i, 'source', 'unknown'),
                            "ESCO": (getattr(i, 'esco_id', "") or "")[:20]
                        } for i in all_items])
                        st.dataframe(df, use_container_width=True, hide_index=True)
                
                st.info("💡 View results in the **Explore KSAs** page")
                
                # Clear loaded data after successful processing
                if st.button("✨ Process Another AFSC", use_container_width=True):
                    st.session_state.admin_loaded_code = ""
                    st.session_state.admin_loaded_text = ""
                    st.rerun()
                
            except Exception as e:
                st.error(f"❌ Processing failed: {e}")
                import traceback
                with st.expander("Error Details"):
                    st.code(traceback.format_exc())

# ============ TAB 2: Bulk JSONL ============
with tab2:
    st.markdown("### Bulk Processing")
    st.caption("Upload JSONL with one AFSC per line (fields: `afsc`, `md` or `sections`)")
    
    file = st.file_uploader("Upload JSONL", type=["jsonl"])
    
    if file:
        lines = file.getvalue().decode("utf-8").splitlines()
        st.info(f"Found {len(lines)} records")
        
        if st.button("🚀 Process All", type="primary", disabled=not db_connected):
            try:
                driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
                
                success = fail = 0
                failed_lines = []
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
                                failed_lines.append(f"Line {i}: missing afsc or text")
                        except Exception as e:
                            fail += 1
                            failed_lines.append(f"Line {i}: {str(e)[:50]}")
                        
                        progress_bar.progress(i / len(lines))
                        status_text.text(f"Processing {i}/{len(lines)} • ✓ {success} • ✗ {fail}")
                
                driver.close()
                st.success(f"Complete! Success: {success}, Failed: {fail}")
                
                # Show failed lines if any
                if failed_lines and len(failed_lines) <= 10:
                    with st.expander("Failed Records"):
                        for err in failed_lines:
                            st.text(err)
                elif len(failed_lines) > 10:
                    with st.expander(f"Failed Records ({len(failed_lines)} total, showing first 10)"):
                        for err in failed_lines[:10]:
                            st.text(err)
                
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
    
    if st.button("🗑️ Delete AFSCs", disabled=(confirm != "DELETE" or not db_connected), type="secondary"):
        try:
            afsc_list = [c.strip() for c in re.split(r"[,\s]+", codes) if c.strip()]
            
            if not afsc_list:
                st.error("No AFSCs specified")
            else:
                driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
                with driver.session(database=NEO4J_DATABASE) as s:
                    # Delete relationships and orphaned items
                    result1 = s.run("""
                        MATCH (a:AFSC)-[r:HAS_ITEM|REQUIRES]->(i:Item)
                        WHERE a.code IN $codes
                        DELETE r
                        WITH i
                        WHERE NOT ()-[:HAS_ITEM|REQUIRES]->(i)
                        DELETE i
                        RETURN count(i) as items_deleted
                    """, {"codes": afsc_list})
                    
                    items_deleted = result1.single()["items_deleted"]
                    
                    # Delete AFSCs
                    result2 = s.run("""
                        MATCH (a:AFSC) 
                        WHERE a.code IN $codes 
                        DELETE a
                        RETURN count(a) as afscs_deleted
                    """, {"codes": afsc_list})
                    
                    afscs_deleted = result2.single()["afscs_deleted"]
                
                driver.close()
                st.success(f"Deleted {afscs_deleted} AFSCs and {items_deleted} orphaned items")
                st.cache_data.clear()
                
        except Exception as e:
            st.error(f"Delete failed: {e}")
    
    st.markdown("---")
    
    if st.button("🔄 Clear All Caches"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success("Caches cleared")
