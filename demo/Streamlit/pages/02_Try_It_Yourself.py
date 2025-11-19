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

# ===== SESSION STATE (TIY-namespaced to prevent collision with Admin Tools) =====
if "tiy_selected_source" not in st.session_state:
    st.session_state.tiy_selected_source = "AFECD (Enlisted)"
if "tiy_search_results" not in st.session_state:
    st.session_state.tiy_search_results = None
if "tiy_search_info" not in st.session_state:
    st.session_state.tiy_search_info = {}
if "tiy_pages" not in st.session_state:
    st.session_state.tiy_pages = []
if "tiy_selected_page_text" not in st.session_state:
    st.session_state.tiy_selected_page_text = ""
if "tiy_afsc_code" not in st.session_state:
    st.session_state.tiy_afsc_code = ""
if "tiy_afsc_text" not in st.session_state:
    st.session_state.tiy_afsc_text = ""

# ===== UTILITIES =====
@st.cache_data(show_spinner=False)
def fetch_pdf(url: str) -> bytes:
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.content

@st.cache_data(show_spinner=False)
def load_pdf_pages(source_key: str):
    url = SOURCES[source_key]
    pdf_bytes = fetch_pdf(url)
    reader = PdfReader(io.BytesIO(pdf_bytes))
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
        return rx.sub(lambda m: f"**{m.group(0)}**", text)
    except re.error:
        return text

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
            snippet = highlight_matches(snippet, query)
            results.append({
                "page": page["page"],
                "matches": len(matches),
                "snippet": snippet,
            })
            if len(results) >= max_hits:
                break
    return results

# Sidebar: Cache Management
with st.sidebar:
    st.markdown("### 🔬 Try It Yourself")
    
    if st.button("🔄 Clear Page Cache", use_container_width=True, help="Clear search results and reset form"):
        # Clear all TIY-specific session state
        for key in list(st.session_state.keys()):
            if key.startswith("tiy_"):
                del st.session_state[key]
        st.cache_data.clear()
        st.success("Cache cleared!")
        st.rerun()
    
    st.markdown("---")
    st.caption("💡 Use this to reset the page if you encounter any issues")

# Main UI
st.title("🔬 Try It Yourself - Interactive KSA Extraction")
st.markdown("**Test the pipeline with your own LLM API key** (LAiSER uses system OpenAI)")

st.divider()

# ============ ARCHITECTURE INFO ============
with st.expander("ℹ️ How This Works", expanded=False):
    st.markdown("""
    ### Pipeline Architecture (5-Stage Process)
    
    **Stage 1: LAiSER Skill Extraction** 🎯
    - ✅ Uses **system OpenAI API key** (from app secrets)
    - ⚠️ LAiSER's Gemini integration is currently broken - OpenAI only
    - 📊 Extracts 20-30 skills per AFSC from job descriptions
    - 🏷️ Automatically aligns skills to ESCO/O*NET taxonomy codes
    - 📚 [LAiSER Taxonomy Reference (ESCO + O*NET combined)](https://github.com/LAiSER-Software/extract-module/blob/main/laiser/public/combined.csv)
    
    **Stage 2: Quality Filtering** ✂️
    - Removes duplicates and low-confidence extractions
    - Filters out generic/vague skills
    - Ensures minimum text length and coherence
    
    **Stage 3: ESCO Mapping** 🗺️
    - Maps extracted skills to standardized taxonomy IDs
    - Links to European Skills/Competences/Occupations framework
    - Enables cross-AFSC skill comparison
    
    **Stage 4: LLM Enhancement (Knowledge & Abilities)** 🤖
    - 🔑 Uses **YOUR API key** (whichever provider you choose)
    - 🧠 Generates complementary Knowledge items (what you need to know)
    - 💪 Generates complementary Ability items (what you need to be capable of)
    - 🔑 Supports: OpenAI, Anthropic, Gemini, HuggingFace
    - ⚡ Produces 15-25 additional KSAs to complement LAiSER's skills
    
    **Stage 5: Deduplication & Output** 🎯
    - Final deduplication pass across all KSA types
    - Confidence scoring and source attribution
    - Structured output ready for Neo4j database (but not written in demo mode)
    
    **Privacy & Security:**
    - Your API key is session-only (cleared when you close browser)
    - Results are NOT saved to database (demo mode only)
    - No data retention or logging of your inputs
    
    **Expected Output:**
    - 25-50 total KSAs per AFSC (varies by complexity)
    - ~60-70% with ESCO taxonomy alignment
    - Mix of Skills (from LAiSER), Knowledge & Abilities (from LLM)
    """)

st.divider()

# ============ STEP 1: Configure LLM Enhancement Key ============
st.markdown('<div class="step-header">🔑 Step 1: Your LLM API Key</div>', unsafe_allow_html=True)

st.info("🔒 **Privacy:** Your API key is stored in browser session only. Never saved to servers.")

col_provider, col_key = st.columns([1, 3])

with col_provider:
    provider = st.selectbox(
        "LLM Provider",
        ["openai", "anthropic", "gemini", "huggingface"],
        help="For K/A generation. LAiSER always uses system OpenAI."
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

if has_key:
    st.success(f"✅ API key loaded for **{provider}**")
else:
    st.warning("⚠️ No API key - LAiSER will still work, but no K/A items")

st.divider()

# ============ STEP 2: Search Documentation ============
st.markdown('<div class="step-header">🔍 Step 2: Search Documentation</div>', unsafe_allow_html=True)

source = st.radio(
    "Select Document",
    list(SOURCES.keys()),
    index=list(SOURCES.keys()).index(st.session_state.tiy_selected_source),
    horizontal=True,
)
st.session_state.tiy_selected_source = source

st.markdown("#### 🔍 Search within the document")
query = st.text_input(
    "Search term (e.g., '14N', '1N4X1', 'Intelligence')",
    value=st.session_state.tiy_search_info.get("query", ""),
    key="tiy_search_query_input"
)

col_search_btn, col_clear_btn = st.columns([3, 1])
with col_search_btn:
    search_btn = st.button("🔎 Search Document", type="primary", use_container_width=True)
with col_clear_btn:
    if st.button("Clear Results", use_container_width=True):
        st.session_state.tiy_search_results = None
        st.session_state.tiy_search_info = {}
        st.rerun()

if search_btn:
    if not query.strip():
        st.warning("⚠️ Enter a search term")
    else:
        with st.spinner("Loading document and searching..."):
            # LAZY LOAD: Only fetch PDF when user actually searches
            pages = load_pdf_pages(source)
            # Store in session state for "Load Page" buttons
            st.session_state.tiy_pages = pages
            results = search_pages(pages, query)
            st.session_state.tiy_search_results = results
            st.session_state.tiy_search_info = {
                "query": query,
                "timestamp": time.time()
            }

results = st.session_state.tiy_search_results

if results is not None:
    # Retrieve pages from session state (loaded during search)
    pages = st.session_state.get("tiy_pages", [])
    
    # Show when these results were generated
    search_info = st.session_state.tiy_search_info
    if "timestamp" in search_info:
        time_ago = int(time.time() - search_info["timestamp"])
        time_str = f"{time_ago}s ago" if time_ago < 60 else f"{time_ago//60}m ago"
        st.caption(f"📍 Results for **'{search_info.get('query', '')}'** (searched {time_str})")
    
    st.markdown("#### 📑 Matching Pages")
    if not results:
        st.info("No matches found. Try another search term.")
    else:
        for r in results:
            # FIXED: Safety check for 'matches' key to prevent KeyError
            match_count = r.get('matches', '?')
            with st.expander(f"📄 Page {r['page']} • {match_count} match(es)"):
                st.markdown(r.get("snippet", ""))
                
                # Show full text in expandable section
                with st.expander("📖 Show full page text"):
                    page_full = next((p for p in pages if p["page"] == r["page"]), None)
                    if page_full:
                        st.text_area(
                            "Full page content",
                            value=page_full["text"],
                            height=400,
                            key=f"tiy_fulltext_{r['page']}",
                            label_visibility="collapsed"
                        )
                
                # Load button
                if st.button(
                    f"✅ Load Page {r['page']} into Step 3",
                    key=f"tiy_use_page_{r['page']}",
                    use_container_width=True,
                ):
                    page_full = next((p for p in pages if p["page"] == r["page"]), None)
                    if page_full:
                        st.session_state.tiy_selected_page_text = page_full["text"]
                        st.session_state.tiy_afsc_text = page_full["text"]
                        st.success(f"✅ Loaded page {r['page']}! Scroll down to Step 3")
                        st.rerun()
else:
    st.info("💡 Use the search above to find AFSC sections, then load them into Step 3")

st.divider()

# ============ STEP 3: AFSC Input ============
st.markdown('<div class="step-header">📝 Step 3: AFSC Code & Text</div>', unsafe_allow_html=True)

col_code, col_info = st.columns([2, 1])

with col_code:
    afsc_code = st.text_input(
        "AFSC Code *",
        value=st.session_state.tiy_afsc_code,
        placeholder="e.g., 14N, 1N4X1"
    )
    st.session_state.tiy_afsc_code = afsc_code

with col_info:
    char_count = len(st.session_state.tiy_afsc_text or st.session_state.tiy_selected_page_text or "")
    st.metric("Text Length", f"{char_count:,} chars")

afsc_text = st.text_area(
    "AFSC Documentation",
    value=st.session_state.tiy_afsc_text or st.session_state.tiy_selected_page_text,
    height=300,
    placeholder="Paste AFSC text, or load from search above..."
)
st.session_state.tiy_afsc_text = afsc_text

if st.button("🗑️ Clear", use_container_width=True):
    st.session_state.tiy_afsc_code = ""
    st.session_state.tiy_afsc_text = ""
    st.session_state.tiy_selected_page_text = ""
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
    # 🧹 Auto-clear: Remove old results to prevent memory buildup
    for key in list(st.session_state.keys()):
        if key.startswith("extraction_") or key == "last_results_df":
            del st.session_state[key]
    
    try:
        # Backup system keys
        old_openai = os.getenv("OPENAI_API_KEY")
        old_anthropic = os.getenv("ANTHROPIC_API_KEY")
        old_gemini = os.getenv("GEMINI_API_KEY")
        old_google = os.getenv("GOOGLE_API_KEY")
        old_hf = os.getenv("HF_TOKEN")
        old_provider = os.getenv("LLM_PROVIDER")
        old_enhancer = os.getenv("USE_LLM_ENHANCER")
        
        # Set user's provider for enhancement
        os.environ["LLM_PROVIDER"] = provider
        
        # Only enable enhancer if user provided key
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
            status.write("🔍 LAiSER extracting skills (system OpenAI)...")
            time.sleep(0.3)
            
            if has_key:
                status.write(f"🤖 LLM generating K/A items (your {provider} key)...")
            else:
                status.write("⚠️ Skipping LLM enhancement (no API key)")
            
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
            
            status.write(f"✅ Complete in {elapsed:.2f}s – {n_total} items ({n_esco} ESCO)")
            status.update(label="✅ Extraction Complete!", state="complete")
        
        # Restore system keys
        if old_openai: os.environ["OPENAI_API_KEY"] = old_openai
        if old_anthropic: os.environ["ANTHROPIC_API_KEY"] = old_anthropic
        if old_gemini: os.environ["GEMINI_API_KEY"] = old_gemini
        if old_google: os.environ["GOOGLE_API_KEY"] = old_google
        if old_hf: os.environ["HF_TOKEN"] = old_hf
        if old_provider: os.environ["LLM_PROVIDER"] = old_provider
        if old_enhancer: os.environ["USE_LLM_ENHANCER"] = old_enhancer
        
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
        
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Export
        st.markdown("### 💾 Export")
        csv = df.to_csv(index=False)
        st.download_button(
            "⬇️ Download Results (CSV)",
            csv,
            f"{afsc_code or 'extracted'}_ksas.csv",
            "text/csv",
            use_container_width=True
        )
        
        st.info("💡 Results are NOT saved to database (demo mode)")
        
        # Quick reset button
        st.divider()
        if st.button("🔄 Start New Extraction", type="primary", use_container_width=True):
            st.session_state.tiy_afsc_code = ""
            st.session_state.tiy_afsc_text = ""
            st.session_state.tiy_selected_page_text = ""
            st.session_state.tiy_search_results = None
            st.session_state.tiy_search_info = {}
            st.rerun()
        
    except Exception as e:
        st.error(f"❌ Extraction failed: {e}")
        import traceback
        with st.expander("📋 Error Details"):
            st.code(traceback.format_exc())

st.divider()
st.caption("🔬 Try It Yourself | LAiSER: System OpenAI | Enhancement: Your API key | No database writes")
