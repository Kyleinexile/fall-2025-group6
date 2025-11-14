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

# Pipeline imports
from afsc_pipeline.preprocess import clean_afsc_text
from afsc_pipeline.extract_laiser import extract_ksa_items

# Paths
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

st.set_page_config(page_title="Try It Yourself", page_icon="🔬", layout="wide")

# Custom CSS for Air Force Blue theme and large buttons
st.markdown("""
<style>
    /* Air Force Blue theme */
    .stButton > button {
        font-size: 16px !important;
        padding: 12px 24px !important;
        font-weight: 600 !important;
    }
    
    .stButton > button[kind="primary"] {
        background-color: #004785 !important;
        border: none !important;
    }
    
    .stButton > button[kind="primary"]:hover {
        background-color: #003366 !important;
    }
    
    /* Green button for extract action */
    .stButton > button[data-testid="baseButton-primary"].extract-button {
        background-color: #28a745 !important;
        color: white !important;
        border: none !important;
    }
    
    .stButton > button[data-testid="baseButton-primary"].extract-button:hover {
        background-color: #218838 !important;
    }
    
    /* Step headers */
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
    
    /* Section dividers */
    hr {
        margin: 32px 0;
        border: none;
        height: 3px;
        background: linear-gradient(90deg, #004785 0%, transparent 100%);
    }
    
    /* Metric styling */
    [data-testid="stMetricValue"] {
        font-size: 28px;
        font-weight: 700;
        color: #004785;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "user_api_key" not in st.session_state:
    st.session_state.user_api_key = None
if "user_provider" not in st.session_state:
    st.session_state.user_provider = None
if "loaded_afsc_code" not in st.session_state:
    st.session_state.loaded_afsc_code = ""
if "loaded_afsc_text" not in st.session_state:
    st.session_state.loaded_afsc_text = ""
if "search_results" not in st.session_state:
    st.session_state.search_results = None
if "search_info" not in st.session_state:
    st.session_state.search_info = {}

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

# Main UI
st.title("🔬 Try It Yourself - Interactive KSA Extraction")
st.markdown("**Experience the pipeline hands-on with your own API key**")

st.divider()

# ============ STEP 1: Configure API Key ============
st.markdown('<div class="step-header">🔑 Step 1: Configure Your API Key</div>', unsafe_allow_html=True)

# Prominent privacy notice
st.info("🔒 **Privacy Notice:** Your API key is stored in browser session only. Never saved to our servers or database. Cleared when you close the browser.")

col_provider, col_key = st.columns([1, 3])

with col_provider:
    provider = st.selectbox(
        "LLM Provider",
        ["openai", "anthropic", "gemini"],
        help="Choose which LLM provider to use for Knowledge/Ability generation"
    )

with col_key:
    placeholder = {
        "openai": "sk-proj-...",
        "anthropic": "sk-ant-...",
        "gemini": "AIza..."
    }[provider]
    
    api_key = st.text_input(
        "API Key",
        type="password",
        placeholder=placeholder
    )
    
    if api_key:
        st.session_state.user_api_key = api_key
        st.session_state.user_provider = provider

# Status indicator
has_key = st.session_state.user_api_key is not None

col_status, col_clear = st.columns([3, 1])
with col_status:
    if has_key:
        st.success(f"✅ API key loaded for **{st.session_state.user_provider}**")
    else:
        st.warning("⚠️ No API key provided - required for Step 4")

with col_clear:
    if st.button("🗑️ Clear Key", use_container_width=True):
        st.session_state.user_api_key = None
        st.session_state.user_provider = None
        st.rerun()

with st.expander("🔐 How to get an API key"):
    st.markdown("""
    **Get your API key from these providers:**
    
    - **OpenAI**: https://platform.openai.com/api-keys
    - **Anthropic**: https://console.anthropic.com/settings/keys
    - **Google Gemini**: https://aistudio.google.com/app/apikey
    """)

st.divider()

# ============ STEP 2: Search Documentation ============
st.markdown('<div class="step-header">🔍 Step 2: Search Documentation</div>', unsafe_allow_html=True)
st.markdown("Search through **AFOCD (Officer)** and **AFECD (Enlisted)** documents from the repository")

# Search interface - cleaner, more prominent layout
col_doc, col_mode = st.columns([2, 1])
with col_doc:
    source = st.selectbox("📄 Select Document", list(SOURCES.keys()))
with col_mode:
    search_mode = st.radio("Search by", ["AFSC Code", "Keywords"], horizontal=True, label_visibility="collapsed")

# Large, prominent search box
query = st.text_input(
    "🔍 Search Query",
    placeholder="Try: 14N, 1N1X1, pilot, intelligence, cyber...",
    help="Enter an AFSC code (e.g., 14N, 1N1X1) or keywords (e.g., intelligence, pilot)"
)

# Search options in expandable section
with st.expander("⚙️ Advanced Search Options"):
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        min_len = st.slider("Excerpt length", 200, 600, 360, 20, help="Length of text excerpts in search results")
    with col_opt2:
        max_results = st.slider("Max results", 5, 30, 10, help="Maximum number of results to display")

# Search buttons
col_search_btn, col_clear_btn = st.columns([3, 1])
with col_search_btn:
    search_btn = st.button("🔍 Search Document", use_container_width=True, type="primary")
with col_clear_btn:
    if st.button("Clear", use_container_width=True):
        st.session_state.search_results = None
        st.session_state.search_info = {}
        st.rerun()

# Search logic
if search_btn:
    if not query.strip():
        st.warning("⚠️ Enter a search term")
    else:
        with st.spinner("🔍 Searching PDF..."):
            try:
                pages = load_pdf_pages(SOURCES[source])
            except Exception as e:
                st.error(f"❌ Could not load PDF: {e}")
                st.stop()
        
        # Build pattern - RESTORED FROM ADMIN TOOLS
        if search_mode == "AFSC Code":
            pattern = rf"(?i)\b{re.escape(query.strip().upper())}[A-Z0-9]*\b"
        else:
            pattern = re.escape(query) if not any(c in query for c in ".*?+[]()") else query
        
        # Search with better implementation
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
                        "full": rec["text"]  # Store full page for loading
                    })
                    if len(hits) >= max_results:
                        break
                if len(hits) >= max_results:
                    break
        except Exception as e:
            st.error(f"❌ Search error: {e}")
            st.stop()
        
        if not hits:
            st.info("ℹ️ No results found. Try different keywords or check spelling.")
            st.session_state.search_results = None
        else:
            st.session_state.search_results = hits
            st.session_state.search_info = {
                "source": source,
                "query": query,
                "mode": search_mode,
                "pattern": pattern
            }

# Display results
if st.session_state.search_results:
    info = st.session_state.search_info
    st.success(f"✅ Found {len(st.session_state.search_results)} results for **'{info['query']}'**")
    
    st.markdown("---")
    
    for i, match in enumerate(st.session_state.search_results, 1):
        # Result card with better styling
        st.markdown(f"#### 📄 Result {i} • Page {match['page']}")
        
        # Highlighted snippet
        highlighted = highlight_matches(match['snippet'], info['pattern'])
        st.markdown(highlighted)
        
        # Expandable full page view
        with st.expander("📖 View Full Page"):
            display_text = match["full"][:10000] + "\n..." if len(match["full"]) > 10000 else match["full"]
            st.text(display_text)
        
        # Action buttons
        col_info, col_download, col_load = st.columns([3, 1, 1])
        with col_info:
            st.caption(f"Source: {info['source']} • Page {match['page']}")
        with col_download:
            st.download_button(
                "⬇️ Download",
                match["full"],
                f"page_{match['page']}.txt",
                key=f"dl_{i}",
                use_container_width=True
            )
        with col_load:
            # Load button
            if st.button("✅ Load", key=f"load_{i}", use_container_width=True, type="secondary"):
                st.session_state.loaded_afsc_text = match["full"]  # Load FULL text, not snippet
                st.session_state.loaded_afsc_code = ""
                st.success("✅ Text loaded! See Step 3 below ↓")
                time.sleep(1.5)
                st.rerun()
        
        if i < len(st.session_state.search_results):
            st.markdown("---")

st.divider()

# ============ STEP 3: Paste/Edit AFSC Text ============
st.markdown('<div class="step-header">📝 Step 3: Paste or Edit AFSC Text</div>', unsafe_allow_html=True)

# Show loaded indicator
if st.session_state.loaded_afsc_text:
    st.info(f"📄 Text loaded from search ({len(st.session_state.loaded_afsc_text)} characters)")

afsc_code = st.text_input(
    "AFSC Code *",
    value=st.session_state.loaded_afsc_code,
    placeholder="e.g., 14N, 1N1X1",
    help="Required - used to tag output and provide context for LLM"
)

afsc_text = st.text_area(
    "AFSC Documentation",
    value=st.session_state.loaded_afsc_text,
    height=300,
    placeholder="Paste AFSC text here, or use Step 2 to search and load documentation...",
    help="Full AFSC documentation text for extraction"
)

if st.button("🗑️ Clear Text", use_container_width=True):
    st.session_state.loaded_afsc_code = ""
    st.session_state.loaded_afsc_text = ""
    st.rerun()

st.divider()

# ============ STEP 4: Run Extraction ============
st.markdown('<div class="step-header">🚀 Step 4: Run KSA Extraction</div>', unsafe_allow_html=True)

# Settings Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Extraction Settings")
    
    st.markdown("**LAiSER Configuration**")
    use_laiser = st.checkbox("Enable LAiSER", value=True, help="Use LAiSER for skill extraction with ESCO taxonomy")
    laiser_topk = st.slider("LAiSER max items", 10, 30, 25, help="Maximum skills to extract from LAiSER")
    
    st.markdown("**LLM Configuration**")
    max_llm_items = st.slider("Max K/A to generate", 3, 10, 6, help="Maximum Knowledge/Ability items to generate")
    temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.05, help="Lower = more focused, Higher = more creative")
    
    st.markdown("---")
    
    st.markdown("### 💡 Best Practices")
    st.caption("""
    **For optimal results:**
    - Include complete AFSC sections
    - Include both duties AND qualifications
    - Longer text generally yields better results
    - LAiSER finds skills with taxonomy codes
    - LLM generates complementary K/A items
    """)

# Process Button
can_run = has_key and afsc_code.strip() and afsc_text.strip()

if not has_key:
    st.warning("⚠️ Configure your API key in Step 1 to enable extraction")
elif not afsc_code.strip():
    st.warning("⚠️ Enter an AFSC Code in Step 3 (required)")
elif not afsc_text.strip():
    st.warning("⚠️ Add AFSC text in Step 3 to enable extraction")

# Green extract button with custom styling
st.markdown("""
<style>
    div[data-testid="stButton"] button[kind="primary"] {
        background-color: #28a745 !important;
        color: white !important;
        border: none !important;
        font-size: 18px !important;
        font-weight: 700 !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        background-color: #218838 !important;
    }
</style>
""", unsafe_allow_html=True)

if st.button("🚀 Extract KSAs", type="primary", disabled=not can_run, use_container_width=True):
    try:
        with st.status("Processing...", expanded=True) as status:
            # Step 1: Clean
            st.write("🧹 Cleaning text...")
            cleaned_text = clean_afsc_text(afsc_text)
            st.write(f"   ✓ Cleaned to {len(cleaned_text)} characters")
            time.sleep(0.2)
            
            # Step 2: LAiSER (if enabled)
            laiser_items = []
            if use_laiser:
                st.write("🔍 LAiSER extracting skills...")
                
                # Temporarily set environment for this extraction
                old_use_laiser = os.getenv("USE_LAISER")
                old_topk = os.getenv("LAISER_ALIGN_TOPK")
                
                os.environ["USE_LAISER"] = "true"
                os.environ["LAISER_ALIGN_TOPK"] = str(laiser_topk)
                
                try:
                    laiser_items = extract_ksa_items(cleaned_text)
                    st.write(f"   ✓ Extracted {len(laiser_items)} skills with taxonomy codes")
                finally:
                    # Restore original env
                    if old_use_laiser:
                        os.environ["USE_LAISER"] = old_use_laiser
                    if old_topk:
                        os.environ["LAISER_ALIGN_TOPK"] = old_topk
                
                time.sleep(0.2)
            else:
                st.write("⏭️ LAiSER disabled, skipping skill extraction")
            
            # Step 3: LLM Enhancement
            st.write("🤖 LLM generating Knowledge/Abilities...")
            
            # Import and configure LLM
            from afsc_pipeline.enhance_llm import run_llm
            
            # Build hints from LAiSER items
            hints = []
            if laiser_items:
                skills = [item.text for item in laiser_items[:10]]  # Top 10 as hints
                hints = skills
            
            # Build prompt
            context = f"AFSC: {afsc_code or 'Unknown'}\n\n{cleaned_text[:2000]}"
            
            prompt = f"""Extract {max_llm_items} items from this Air Force job description.

Context:
{context}

Extracted Skills (use as hints):
{chr(10).join(f'- {h}' for h in hints[:5]) if hints else '(none)'}

Generate exactly {max_llm_items} items total:
- {max_llm_items // 2} Knowledge items (theoretical understanding needed)
- {max_llm_items // 2} Ability items (cognitive/physical capacities)

Format EACH as JSON on separate lines:
{{"type": "knowledge", "text": "..."}}
{{"type": "ability", "text": "..."}}

Requirements:
- Must be SPECIFIC to this role
- NO generic statements
- NO duplicates
- CONCISE (under 100 chars each)"""

            # Call LLM with user's key
            try:
                import json
                
                response_text = run_llm(
                    prompt=prompt,
                    provider=st.session_state.user_provider,
                    api_key=st.session_state.user_api_key,
                    temperature=temperature
                )
                
                # Parse response
                enhanced_items = []
                for line in response_text.strip().split('\n'):
                    line = line.strip()
                    if line.startswith('{'):
                        try:
                            obj = json.loads(line)
                            enhanced_items.append({
                                'type': obj.get('type', 'knowledge'),
                                'text': obj.get('text', ''),
                                'confidence': 0.7,
                                'source': f'llm-{st.session_state.user_provider}'
                            })
                        except:
                            pass
                
                st.write(f"   ✓ Generated {len(enhanced_items)} Knowledge/Ability items")
                time.sleep(0.2)
                
            except Exception as e:
                st.error(f"❌ LLM call failed: {e}")
                enhanced_items = []
            
            status.update(label="✅ Extraction Complete!", state="complete")
        
        # Combine results
        all_items = []
        
        # Add LAiSER items
        for item in laiser_items:
            all_items.append({
                'Type': 'skill',
                'Text': item.text,
                'Confidence': float(getattr(item, 'confidence', 0.0)),
                'Source': getattr(item, 'source', 'laiser'),
                'Taxonomy': getattr(item, 'esco_id', '') or ''
            })
        
        # Add LLM items
        for item in enhanced_items:
            all_items.append({
                'Type': item['type'],
                'Text': item['text'],
                'Confidence': item['confidence'],
                'Source': item['source'],
                'Taxonomy': ''
            })
        
        if not all_items:
            st.warning("⚠️ No items extracted. Try enabling LAiSER or adjusting settings in the sidebar.")
            st.stop()
        
        # Display Results
        st.success(f"✅ Successfully extracted {len(all_items)} KSAs!")
        st.balloons()
        
        # Metrics
        k_count = sum(1 for i in all_items if i['Type'] == 'knowledge')
        s_count = sum(1 for i in all_items if i['Type'] == 'skill')
        a_count = sum(1 for i in all_items if i['Type'] == 'ability')
        tax_count = sum(1 for i in all_items if i['Taxonomy'])
        
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total KSAs", len(all_items))
        col2.metric("Knowledge", k_count)
        col3.metric("Skills", s_count)
        col4.metric("Abilities", a_count)
        col5.metric("Taxonomy Aligned", tax_count)
        
        # Results Table
        st.markdown("### 📊 Extracted KSAs")
        
        df = pd.DataFrame(all_items)
        
        # Add filters
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            type_filter = st.multiselect(
                "Filter by type",
                ['knowledge', 'skill', 'ability'],
                default=['knowledge', 'skill', 'ability']
            )
        with col_filter2:
            min_conf = st.slider("Minimum confidence", 0.0, 1.0, 0.0, 0.05)
        
        # Apply filters
        filtered_df = df[df['Type'].isin(type_filter)]
        filtered_df = filtered_df[filtered_df['Confidence'] >= min_conf]
        
        st.caption(f"Showing {len(filtered_df)} of {len(df)} items")
        
        # Display
        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Confidence": st.column_config.NumberColumn(format="%.2f"),
                "Taxonomy": st.column_config.TextColumn("Skill Taxonomy")
            }
        )
        
        # Export
        st.markdown("### 💾 Export Results")
        
        col_exp1, col_exp2 = st.columns(2)
        
        with col_exp1:
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                "⬇️ Download Filtered Results",
                csv,
                f"{afsc_code or 'extracted'}_ksas.csv",
                "text/csv",
                use_container_width=True
            )
        
        with col_exp2:
            full_csv = df.to_csv(index=False)
            st.download_button(
                "⬇️ Download All Results",
                full_csv,
                f"{afsc_code or 'extracted'}_ksas_full.csv",
                "text/csv",
                use_container_width=True
            )
        
        st.info("💡 **Note:** These results are NOT saved to the database. This is a demo/testing tool only. Use Admin Tools for permanent storage.")
        
        st.caption("📖 **Skill Taxonomy Reference:** Skills are aligned to the Open Skills Network (OSN) taxonomy. View the complete taxonomy codes and labels: [LAiSER Taxonomy CSV](https://github.com/LAiSER-Software/extract-module/blob/main/laiser/public/combined.csv)")
        
    except Exception as e:
        st.error(f"❌ Extraction failed: {e}")
        import traceback
        with st.expander("📋 Error Details"):
            st.code(traceback.format_exc())

# Help Section
with st.expander("❓ Help & FAQ"):
    st.markdown("""
    ### How This Tool Works
    
    This interactive tool lets you experience the full KSA extraction pipeline using your own API credentials:
    
    **Step 1: Configure API Key**
    - Securely enter your LLM provider credentials
    - Keys are stored in browser session only
    - Never saved to our database or servers
    
    **Step 2: Search Documentation**
    - Browse AFOCD (Officer) and AFECD (Enlisted) documents
    - Search by AFSC code or keywords
    - View pre-extracted markdown files
    
    **Step 3: Edit Text**
    - Load text from search results
    - Or paste your own AFSC documentation
    - Edit and refine as needed
    
    **Step 4: Extract KSAs**
    - LAiSER extracts skills with ESCO taxonomy codes
    - LLM generates complementary knowledge and abilities
    - Download results as CSV
    
    ### Privacy & Security
    
    - ✅ Your API key is session-only storage
    - ✅ No data written to our database
    - ✅ You control your API usage and costs
    - ✅ Results can be downloaded but not permanently stored
    
    ### Comparison with Admin Tools
    
    | Feature | Try It Yourself | Admin Tools |
    |---------|----------------|-------------|
    | API Key | Your own (BYO) | System credentials |
    | Database | No writes | Full integration |
    | Results | Download only | Permanent storage |
    | Access | Public demo | Admin only |
    | Use Case | Testing/demos | Production ingestion |
    
    ### Getting API Keys
    
    - **OpenAI**: https://platform.openai.com/api-keys
    - **Anthropic**: https://console.anthropic.com/settings/keys
    - **Google Gemini**: https://aistudio.google.com/app/apikey
    
    ### Tips for Best Results
    
    1. Use complete AFSC sections (not fragments)
    2. Include both duties and qualifications
    3. More context = better extraction quality
    4. Enable LAiSER for taxonomy-aligned skills
    5. Adjust temperature for creativity vs. precision
    
    ### Skill Taxonomy Reference
    
    Skills extracted by LAiSER are aligned to the **Open Skills Network (OSN)** taxonomy, which provides standardized skill definitions. Each taxonomy code (e.g., ESCO.95) corresponds to a specific skill label.
    
    - **View complete taxonomy:** [LAiSER Taxonomy CSV](https://github.com/LAiSER-Software/extract-module/blob/main/laiser/public/combined.csv)
    - **Total skills:** 2,217+ standardized skills
    - **Format:** SkillTag (ESCO.XX) → SkillLabel
    """)

st.divider()
st.caption("🔬 Try It Yourself | Session-only API keys | No database writes | Download results only")
