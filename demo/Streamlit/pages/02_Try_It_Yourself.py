import sys, pathlib, os, io, re, time, textwrap
from typing import Optional

# Path setup
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
import requests
import streamlit as st
from pypdf import PdfReader
from dotenv import load_dotenv

load_dotenv()

from afsc_pipeline.pipeline import run_pipeline_demo

# PDF Sources
SOURCES = {
    "AFECD (Enlisted)": "https://raw.githubusercontent.com/Kyleinexile/fall-2025-group6/main/src/docs/AFECD%202025%20Split.pdf",
    "AFOCD (Officer)": "https://raw.githubusercontent.com/Kyleinexile/fall-2025-group6/main/src/docs/AFOCD%202025%20Split.pdf",
}

st.set_page_config(page_title="Try It Yourself", page_icon="🔬", layout="wide")

# ============ CSS - AIR FORCE BLUE THEME ============
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .step-header {
        background: linear-gradient(90deg, #004785 0%, #0066cc 100%);
        color: white;
        padding: 16px 24px;
        border-radius: 8px;
        font-size: 20px;
        font-weight: 700;
        margin: 24px 0 16px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .stButton > button[kind="primary"] {
        background-color: #28a745 !important;
        color: white !important;
        font-size: 18px !important;
        font-weight: 700 !important;
    }
    
    .stButton > button[kind="primary"]:hover {
        background-color: #218838 !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "afsc_code" not in st.session_state:
    st.session_state.afsc_code = ""
if "afsc_text" not in st.session_state:
    st.session_state.afsc_text = ""
if "loaded_text" not in st.session_state:
    st.session_state.loaded_text = None

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

def search_pages(pages, query: str, max_hits: int = 50):
    if not query.strip():
        return []
    results = []
    rx = re.compile(re.escape(query), flags=re.IGNORECASE)
    for page in pages:
        text = page["text"]
        if rx.search(text):
            matches = rx.findall(text)
            snippet = textwrap.shorten(text, width=700, placeholder=" ...")
            results.append({
                "page": page["page"],
                "matches": len(matches),
                "snippet": snippet,
                "full_text": text,
            })
            if len(results) >= max_hits:
                break
    return results

# Main UI
st.title("🔬 Try It Yourself - Interactive KSA Extraction")
st.markdown("**Test the pipeline with your own LLM API key** (LAiSER uses system OpenAI)")

st.divider()

# ============ ARCHITECTURE INFO ============
with st.expander("ℹ️ How This Works", expanded=False):
    st.markdown("""
    ### Pipeline Architecture
    
    This tool runs the **same pipeline as Admin Tools**, but with two key differences:
    
    **1. LAiSER (Skill Extraction)**
    - ✅ Uses the **system OpenAI API key** (from app secrets)
    - ⚠️ **Note:** LAiSER's Gemini integration is currently broken - OpenAI only
    - ✅ You don't need to provide a key for this
    - ✅ Extracts skills with ESCO taxonomy codes
    - ✅ Always enabled and working
    
    **2. LLM Enhancement (Knowledge & Abilities)**
    - 🔑 Uses **YOUR API key** (whichever provider you choose)
    - 🔑 You provide the key below
    - 🔑 Generates complementary Knowledge and Ability items
    - 🔑 Supports: OpenAI, Anthropic, Gemini, HuggingFace
    
    **Privacy:**
    - Your API key is session-only (cleared when you close browser)
    - Results are NOT saved to database (demo mode only)
    - Download results as CSV
    
    **Comparison to Admin Tools:**
    - Admin Tools: Uses system keys for both LAiSER and enhancement, saves to Neo4j
    - Try It Yourself: Uses system OpenAI for LAiSER, YOUR key for enhancement, no database writes
    """)

st.divider()

# ============ STEP 1: Configure LLM Enhancement Key ============
st.markdown('<div class="step-header">🔑 Step 1: Your LLM API Key (for K/A Generation)</div>', unsafe_allow_html=True)

st.info("🔒 **Privacy:** Your API key is stored in browser session only. Never saved to servers.")

col_provider, col_key = st.columns([1, 3])

with col_provider:
    provider = st.selectbox(
        "LLM Provider",
        ["openai", "anthropic", "gemini", "huggingface"],
        help="This controls ONLY the K/A generation. LAiSER always uses system OpenAI."
    )

with col_key:
    placeholder = {
        "openai": "sk-proj-...",
        "anthropic": "sk-ant-...",
        "gemini": "AIza...",
        "huggingface": "hf_..."
    }[provider]
    
    api_key = st.text_input(
        "Your API Key",
        type="password",
        placeholder=placeholder,
        help="Required for generating Knowledge/Ability items"
    )

has_key = bool(api_key.strip())

col_status, col_clear = st.columns([3, 1])
with col_status:
    if has_key:
        st.success(f"✅ API key loaded for **{provider}** (K/A generation)")
    else:
        st.warning("⚠️ No API key - LAiSER will still work, but no K/A items will be generated")

with col_clear:
    if st.button("🗑️ Clear Key", use_container_width=True):
        api_key = ""
        st.rerun()

st.markdown("""
> 💡 **What runs with what:**
> - **LAiSER** → System OpenAI key → Extracts skills with taxonomy (Gemini support broken)
> - **LLM Enhancement** → Your key (above) → Generates Knowledge & Abilities
""")

st.divider()

# ============ STEP 2: Search Documentation ============
st.markdown('<div class="step-header">🔍 Step 2: Search AFSC Documentation</div>', unsafe_allow_html=True)

col_doc, col_search = st.columns([2, 1])
with col_doc:
    source = st.selectbox("📄 Document", list(SOURCES.keys()))
with col_search:
    search_mode = st.radio("Search by", ["AFSC Code", "Keywords"], horizontal=True, label_visibility="collapsed")

query = st.text_input(
    "🔍 Search Query",
    placeholder="e.g., 14N, 1N4X1, intelligence, pilot...",
)

if st.button("🔍 Search", type="primary", use_container_width=True):
    if not query.strip():
        st.warning("⚠️ Enter a search term")
    else:
        with st.spinner("Searching..."):
            pages = load_pdf_pages(SOURCES[source])
            results = search_pages(pages, query)
            
            if results:
                st.success(f"✅ Found {len(results)} result(s)")
                
                for idx, r in enumerate(results):
                    full = r["full_text"]
                    
                    with st.expander(f"📄 Page {r['page']} • {r['matches']} match(es)"):
                        # Show snippet
                        st.markdown("**Preview:**")
                        st.markdown(r["snippet"])
                        
                        st.markdown("---")
                        
                        # Load button at top
                        if st.button(f"✅ Load Page {r['page']} into Step 3", key=f"load_{idx}", type="primary"):
                            st.session_state.loaded_text = full
                            st.success(f"✅ Loaded! Scroll down to Step 3")
                            st.rerun()
                        
                        # Show full text below (not nested)
                        st.markdown("**Full Page Text:**")
                        st.text_area(
                            "Full content",
                            value=full,
                            height=300,
                            key=f"fulltext_{idx}",
                            label_visibility="collapsed",
                            disabled=True
                        )
            else:
                st.info("ℹ️ No matches found")

st.divider()

# ============ STEP 3: AFSC Input ============
st.markdown('<div class="step-header">📝 Step 3: AFSC Code & Text</div>', unsafe_allow_html=True)

# Check if text was loaded from search
if "loaded_text" in st.session_state and st.session_state.loaded_text:
    if "afsc_text" not in st.session_state or st.session_state.afsc_text != st.session_state.loaded_text:
        st.session_state.afsc_text = st.session_state.loaded_text
        st.session_state.loaded_text = None  # Clear the flag

col_code, col_info = st.columns([2, 1])

with col_code:
    afsc_code = st.text_input(
        "AFSC Code *",
        value=st.session_state.afsc_code,
        placeholder="e.g., 14N, 1N4X1"
    )
    st.session_state.afsc_code = afsc_code

with col_info:
    char_count = len(st.session_state.afsc_text)
    st.metric("Text Length", f"{char_count:,} chars")

afsc_text = st.text_area(
    "AFSC Documentation",
    value=st.session_state.afsc_text,
    height=300,
    placeholder="Paste AFSC text, or load from search above...",
    key="afsc_text_input"
)

# Only update state if user actually edited the text
if afsc_text != st.session_state.afsc_text:
    st.session_state.afsc_text = afsc_text

if st.button("🗑️ Clear", use_container_width=True):
    st.session_state.afsc_code = ""
    st.session_state.afsc_text = ""
    st.rerun()

st.divider()

# ============ STEP 4: Run Extraction ============
st.markdown('<div class="step-header">🚀 Step 4: Extract KSAs</div>', unsafe_allow_html=True)

can_run = bool(afsc_code.strip()) and bool(afsc_text.strip())

if not afsc_code.strip():
    st.warning("⚠️ Enter an AFSC Code")
elif not afsc_text.strip():
    st.warning("⚠️ Add AFSC text")

if st.button("🚀 Extract KSAs", type="primary", disabled=not can_run, use_container_width=True):
    try:
        # Backup system keys
        old_openai = os.getenv("OPENAI_API_KEY")
        old_anthropic = os.getenv("ANTHROPIC_API_KEY")
        old_gemini = os.getenv("GEMINI_API_KEY") 
        old_google = os.getenv("GOOGLE_API_KEY")
        old_hf = os.getenv("HF_TOKEN")
        old_provider = os.getenv("LLM_PROVIDER")
        old_enhancer = os.getenv("USE_LLM_ENHANCER")
        
        # Set user's provider for enhancement (LAiSER still uses system OpenAI)
        os.environ["LLM_PROVIDER"] = provider
        
        # Only set enhancement key if user provided one
        if has_key:
            os.environ["USE_LLM_ENHANCER"] = "true"
            key_map = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY", 
                "gemini": "GEMINI_API_KEY",
                "huggingface": "HF_TOKEN"
            }
            os.environ[key_map[provider]] = api_key.strip()
        else:
            os.environ["USE_LLM_ENHANCER"] = "false"
        
        with st.status("Running pipeline...", expanded=True) as status:
            status.write("🔍 LAiSER extracting skills (using system OpenAI)...")
            time.sleep(0.3)
            
            if has_key:
                status.write(f"🤖 LLM generating K/A items (using your {provider} key)...")
            else:
                status.write("⚠️ Skipping LLM enhancement (no API key provided)")
            
            time.sleep(0.3)
            
            t0 = time.time()
            summary = run_pipeline_demo(
                afsc_code=afsc_code or "UNKNOWN",
                afsc_raw_text=afsc_text,
            )
            elapsed = time.time() - t0
            
            items = summary.get("items", []) or []
            n_total = len(items)
            n_esco = summary.get("esco_tagged_count", 0)
            
            status.write(f"✅ Complete in {elapsed:.2f}s – {n_total} items ({n_esco} with ESCO)")
            status.update(label="✅ Extraction Complete!", state="complete")
        
        # Restore system keys
        if old_openai:
            os.environ["OPENAI_API_KEY"] = old_openai
        if old_anthropic:
            os.environ["ANTHROPIC_API_KEY"] = old_anthropic
        if old_gemini:
            os.environ["GEMINI_API_KEY"] = old_gemini
        if old_google:
            os.environ["GOOGLE_API_KEY"] = old_google
        if old_hf:
            os.environ["HF_TOKEN"] = old_hf
        if old_provider:
            os.environ["LLM_PROVIDER"] = old_provider
        if old_enhancer:
            os.environ["USE_LLM_ENHANCER"] = old_enhancer
        
        # Convert to display format
        all_items = []
        for it in items:
            raw_type = getattr(it, "item_type", "")
            type_val = str(raw_type.value if hasattr(raw_type, "value") else raw_type).lower()
            
            all_items.append({
                "Type": type_val,
                "Text": getattr(it, "text", ""),
                "Confidence": float(getattr(it, "confidence", 0.0) or 0.0),
                "Source": getattr(it, "source", ""),
                "Taxonomy": getattr(it, "esco_id", "") or "",
            })
        
        if not all_items:
            st.warning("⚠️ No items extracted")
            st.stop()
        
        st.success(f"✅ Extracted {len(all_items)} KSAs!")
        st.balloons()
        
        # Metrics
        k_count = sum(1 for i in all_items if i['Type'] == 'knowledge')
        s_count = sum(1 for i in all_items if i['Type'] == 'skill')
        a_count = sum(1 for i in all_items if i['Type'] == 'ability')
        tax_count = sum(1 for i in all_items if i['Taxonomy'])
        laiser_count = sum(1 for i in all_items if 'laiser' in i['Source'].lower() or i['Taxonomy'])
        llm_count = sum(1 for i in all_items if 'llm-' in i['Source'].lower())
        
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("Total", len(all_items))
        col2.metric("Knowledge", k_count)
        col3.metric("Skills", s_count)
        col4.metric("Abilities", a_count)
        col5.metric("From LAiSER", laiser_count)
        col6.metric("From LLM", llm_count)
        
        # Results Table
        st.markdown("### 📊 Results")
        df = pd.DataFrame(all_items)
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            type_filter = st.multiselect(
                "Filter by type",
                ['knowledge', 'skill', 'ability'],
                default=['knowledge', 'skill', 'ability']
            )
        with col_f2:
            source_filter = st.selectbox(
                "Filter by source",
                ["All", "LAiSER only", "LLM only", "With taxonomy"],
                index=0
            )
        
        filtered_df = df[df['Type'].isin(type_filter)]
        
        if source_filter == "LAiSER only":
            filtered_df = filtered_df[filtered_df['Source'].str.contains('laiser|pattern', case=False, na=False)]
        elif source_filter == "LLM only":
            filtered_df = filtered_df[filtered_df['Source'].str.contains('llm-', case=False, na=False)]
        elif source_filter == "With taxonomy":
            filtered_df = filtered_df[filtered_df['Taxonomy'] != ""]
        
        st.caption(f"Showing {len(filtered_df)} of {len(df)} items")
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        
        # Export
        st.markdown("### 💾 Export")
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            "⬇️ Download Results",
            csv,
            f"{afsc_code or 'extracted'}_ksas.csv",
            "text/csv",
            use_container_width=True
        )
        
        st.info("💡 Results are NOT saved to database (demo mode)")
        
    except Exception as e:
        st.error(f"❌ Extraction failed: {e}")
        import traceback
        with st.expander("📋 Error Details"):
            st.code(traceback.format_exc())

st.divider()
st.caption("🔬 Try It Yourself | LAiSER: System OpenAI | Enhancement: Your API key | No database writes")
