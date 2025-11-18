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
from afsc_pipeline.pipeline import run_pipeline_demo

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

# Custom CSS
st.markdown(
    """
<style>
    .step-header {
        font-size: 1.3rem;
        font-weight: 700;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
    }
    .metric-card {
        padding: 0.75rem;
        border-radius: 0.5rem;
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #6c757d;
    }
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.title("🔬 Try It Yourself - Interactive KSA Extraction")

# ============ SESSION STATE SETUP ============

if "user_api_key" not in st.session_state:
    st.session_state.user_api_key = None
if "user_provider" not in st.session_state:
    st.session_state.user_provider = None

if "search_results" not in st.session_state:
    st.session_state.search_results = None
if "search_info" not in st.session_state:
    st.session_state.search_info = {}
if "selected_page_text" not in st.session_state:
    st.session_state.selected_page_text = ""
if "selected_source" not in st.session_state:
    st.session_state.selected_source = "AFECD (Enlisted)"
if "afsc_code" not in st.session_state:
    st.session_state.afsc_code = ""
if "afsc_text" not in st.session_state:
    st.session_state.afsc_text = ""

# ============ UTILITIES ============

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
            snippet = textwrap.shorten(text, width=400, placeholder="...")
            snippet = highlight_matches(snippet, query)
            results.append(
                {
                    "page": page["page"],
                    "matches": len(matches),
                    "snippet": snippet,
                }
            )
            if len(results) >= max_hits:
                break
    return results

# ============ LAYOUT ============

cols = st.columns([2, 3])

# ============ COLUMN 1: SOURCING TEXT FROM PDF ============

with cols[0]:
    st.markdown('<div class="step-header">📄 Step 1: Select Source Document</div>', unsafe_allow_html=True)

    source = st.radio(
        "Choose AFSC Catalog",
        list(SOURCES.keys()),
        index=list(SOURCES.keys()).index(st.session_state.selected_source),
    )
    st.session_state.selected_source = source

    pages = load_pdf_pages(source)

    st.markdown("### 🔍 Search within the document")
    query = st.text_input("Search term (e.g., '1N4', 'Intelligence')", value=st.session_state.search_info.get("query", ""))

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
            st.warning("⚠️ Enter a search term to find AFSC sections")
        else:
            with st.spinner("Searching pages..."):
                results = search_pages(pages, query)
                st.session_state.search_results = results
                st.session_state.search_info = {
                    "query": query,
                    "timestamp": time.time(),
                }

    results = st.session_state.search_results

    if results is not None:
        st.markdown("### 📑 Matching Pages")
        if not results:
            st.info("No matches found. Try another search term.")
        else:
            for r in results:
                with st.expander(f"Page {r['page']} • {r['matches']} match(es)"):
                    st.markdown(r["snippet"])
                    if st.button(
                        f"📥 Use Page {r['page']} as AFSC text",
                        key=f"use_page_{r['page']}",
                        use_container_width=True,
                    ):
                        page_full = next((p for p in pages if p["page"] == r["page"]), None)
                        if page_full:
                            st.session_state.selected_page_text = page_full["text"]
                            st.session_state.afsc_text = page_full["text"]
                            st.info(f"Loaded full text from page {r['page']} into Step 3.")
                            st.rerun()
    else:
        st.info("Use the search bar above to find relevant AFSC sections, then load them into Step 3.")

# ============ COLUMN 2: USER INPUT & EXTRACTION ============

with cols[1]:
    # ---- Step 2: Configure API Key (still present, no longer a hard requirement) ----
    st.markdown('<div class="step-header">🔑 Step 2: Configure LLM API Key (optional)</div>', unsafe_allow_html=True)

    st.info(
        "🔒 **Privacy Notice:** Your API key is stored in browser session state only and never sent to our servers or database. "
        "Cleared when you close the browser."
    )

    col_provider, col_key = st.columns([1, 3])

    with col_provider:
        provider = st.selectbox(
            "LLM Provider",
            ["openai", "anthropic", "gemini"],
            help="Choose which LLM provider to use for Knowledge/Ability generation",
        )

    with col_key:
        placeholder = {
            "openai": "sk-proj-...",
            "anthropic": "sk-ant-...",
            "gemini": "AIza...",
        }.get(provider, "API key...")
        api_key_input = st.text_input(
            "API Key (optional for this demo)",
            type="password",
            placeholder=placeholder,
            help="Used for LLM-based Knowledge/Ability generation in some configurations.",
        )

    col_save, col_clear = st.columns([1, 1])
    with col_save:
        if st.button("💾 Save Key", use_container_width=True):
            if api_key_input.strip():
                st.session_state.user_api_key = api_key_input.strip()
                st.session_state.user_provider = provider
                st.success(f"Saved API key for {provider}.")
            else:
                st.warning("⚠️ No API key provided.")
    with col_clear:
        if st.button("🗑️ Clear Key", use_container_width=True):
            st.session_state.user_api_key = None
            st.session_state.user_provider = None
            st.rerun()

    with st.expander("🔐 How to get an API key"):
        st.markdown(
            """
    **Get your API key from these providers:**
    
    - **OpenAI**: https://platform.openai.com/api-keys
    - **Anthropic**: https://console.anthropic.com/settings/keys
    - **Google Gemini**: https://aistudio.google.com/app/apikey
    
    You only need *one* provider for this tool.
    """
        )

    # ---- Step 3: AFSC Code & Text ----
    st.markdown('<div class="step-header">🧩 Step 3: Provide AFSC Code and Text</div>', unsafe_allow_html=True)

    st.markdown("Enter the AFSC code and paste the relevant text (duties, qualifications, etc.).")

    col_code, col_example = st.columns([2, 1])
    with col_code:
        afsc_code = st.text_input("AFSC Code", value=st.session_state.afsc_code, placeholder="e.g., 1N4, 14N, 21A")
        st.session_state.afsc_code = afsc_code

    with col_example:
        if st.button("Use Example (1N4)", use_container_width=True):
            example_text = "1N4X1 - Fusion Analyst / Cyber Intelligence ..."
            st.session_state.afsc_code = "1N4"
            st.session_state.afsc_text = example_text
            st.session_state.selected_page_text = example_text
            st.experimental_rerun()

    afsc_text = st.text_area(
        "AFSC Text (duties, responsibilities, qualifications)",
        value=st.session_state.afsc_text or st.session_state.selected_page_text,
        height=260,
        placeholder="Paste the AFSC section here...",
    )
    st.session_state.afsc_text = afsc_text

    st.markdown(
        """
> 💡 **Tip:** Paste the full AFSC section from AFECD/AFOCD, including summary, duties, and qualifications. 
> The more complete the context, the better the KSA extraction.
"""
    )

    # ============ STEP 4: Run Extraction ============
    st.markdown('<div class="step-header">🚀 Step 4: Run KSA Extraction</div>', unsafe_allow_html=True)

    # Settings Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Extraction Settings")

        st.markdown("**LAiSER Configuration**")
        use_laiser = st.checkbox(
            "Enable LAiSER",
            value=True,
            help="Use LAiSER for skill extraction with ESCO taxonomy",
        )
        laiser_topk = st.slider(
            "LAiSER max items",
            10,
            30,
            25,
            help="Maximum skills to extract from LAiSER",
        )

        st.markdown("**LLM Configuration**")
        max_llm_items = st.slider(
            "Max K/A to generate",
            3,
            10,
            6,
            help="(For pipeline LLM enhancer) Maximum Knowledge/Ability items to generate",
        )
        temperature = st.slider(
            "Temperature",
            0.0,
            1.0,
            0.2,
            0.05,
            help="Lower = more focused, Higher = more creative",
        )

        st.markdown("---")
        st.markdown(
            """
**How this works (high level):**

1. AFSC text is cleaned and normalized
2. LAiSER (if enabled) extracts skill candidates with ESCO IDs
3. Pipeline applies quality filters and dedupe
4. Optional LLM enhancer adds Knowledge/Ability items
"""
        )

        st.markdown(
            """
**Best practices:**

- Include complete AFSC sections
- Include both duties AND qualifications
- Longer text generally yields better results
- LAiSER finds skills with taxonomy codes
- LLM generates complementary K/A items
"""
        )

    # Process Button
    can_run = bool(afsc_code.strip() and afsc_text.strip())

    if not afsc_code.strip():
        st.warning("⚠️ Enter an AFSC Code in Step 3 (required)")
    elif not afsc_text.strip():
        st.warning("⚠️ Add AFSC text in Step 3 to enable extraction")

    # Green extract button with custom styling
    st.markdown(
        """
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
""",
        unsafe_allow_html=True,
    )

    if st.button("🚀 Extract KSAs", type="primary", disabled=not can_run, use_container_width=True):
        try:
            # Temporarily align LAiSER settings with the sidebar controls
            old_use_laiser = os.getenv("USE_LAISER")
            old_topk = os.getenv("LAISER_ALIGN_TOPK")

            os.environ["USE_LAISER"] = "true" if use_laiser else "false"
            os.environ["LAISER_ALIGN_TOPK"] = str(laiser_topk)

            with st.status("Running full pipeline...", expanded=True) as status:
                status.write("🧹 Cleaning text and running LAiSER / filters / dedupe...")
                t0 = time.time()
                summary = run_pipeline_demo(
                    afsc_code=afsc_code or "UNKNOWN",
                    afsc_raw_text=afsc_text,
                )
                elapsed = time.time() - t0

                items = summary.get("items", []) or []

                n_total = len(items)
                n_esco = summary.get(
                    "esco_tagged_count",
                    sum(1 for it in items if getattr(it, "esco_id", None)),
                )
                used_fallback = summary.get("used_fallback", False)

                status.write(
                    f"✅ Pipeline complete in {elapsed:0.2f}s – {n_total} items ({n_esco} with ESCO IDs)"
                )
                if used_fallback:
                    status.write("⚠️ LAiSER unavailable; fallback pattern extractor was used.")

                status.update(label="✅ Extraction Complete!", state="complete")

            # Build display rows from ItemDraft objects
            all_items = []
            for it in items:
                raw_type = getattr(it, "item_type", "")
                if hasattr(raw_type, "value"):
                    raw_type_val = str(raw_type.value)
                else:
                    raw_type_val = str(raw_type)

                lt = raw_type_val.lower()
                if "know" in lt:
                    type_label = "knowledge"
                elif "abil" in lt:
                    type_label = "ability"
                else:
                    type_label = "skill"

                all_items.append(
                    {
                        "Type": type_label,
                        "Text": getattr(it, "text", ""),
                        "Confidence": float(getattr(it, "confidence", 0.0) or 0.0),
                        "Source": getattr(it, "source", "pipeline"),
                        "Taxonomy": getattr(it, "esco_id", "") or "",
                    }
                )

            if not all_items:
                st.warning(
                    "⚠️ No items extracted. Try enabling LAiSER or adjusting settings in the sidebar."
                )
            else:
                # Metrics
                k_count = sum(1 for i in all_items if i["Type"] == "knowledge")
                s_count = sum(1 for i in all_items if i["Type"] == "skill")
                a_count = sum(1 for i in all_items if i["Type"] == "ability")
                tax_count = sum(1 for i in all_items if i["Taxonomy"])

                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("Total KSAs", len(all_items))
                col2.metric("Knowledge", k_count)
                col3.metric("Skills", s_count)
                col4.metric("Abilities", a_count)
                col5.metric("Taxonomy Aligned", tax_count)

                # Results table
                st.markdown("### 📊 Extracted KSAs")

                df = pd.DataFrame(all_items)

                # Add filters
                col_filter1, col_filter2 = st.columns(2)
                with col_filter1:
                    type_filter = st.multiselect(
                        "Filter by type",
                        ["knowledge", "skill", "ability"],
                        default=["knowledge", "skill", "ability"],
                    )
                with col_filter2:
                    taxonomy_filter = st.selectbox(
                        "Filter by taxonomy",
                        ["All", "Only taxonomy-aligned", "Only non-taxonomy"],
                        index=0,
                    )

                filtered_df = df[df["Type"].isin(type_filter)]

                if taxonomy_filter == "Only taxonomy-aligned":
                    filtered_df = filtered_df[filtered_df["Taxonomy"] != ""]
                elif taxonomy_filter == "Only non-taxonomy":
                    filtered_df = filtered_df[filtered_df["Taxonomy"] == ""]

                st.caption(f"Showing {len(filtered_df)} of {len(df)} items")

                st.dataframe(
                    filtered_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Confidence": st.column_config.NumberColumn(format="%.2f"),
                        "Taxonomy": st.column_config.TextColumn("Skill Taxonomy"),
                    },
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
                        use_container_width=True,
                    )

                with col_exp2:
                    full_csv = df.to_csv(index=False)
                    st.download_button(
                        "⬇️ Download All Results",
                        full_csv,
                        f"{afsc_code or 'extracted'}_ksas_full.csv",
                        "text/csv",
                        use_container_width=True,
                    )

        except Exception as e:
            st.error(f"❌ Extraction failed: {e}")
            import traceback

            with st.expander("📋 Error Details"):
                st.code(traceback.format_exc())

        finally:
            # Restore LAiSER-related env vars to their previous values
            if old_use_laiser is not None:
                os.environ["USE_LAISER"] = old_use_laiser
            else:
                os.environ.pop("USE_LAISER", None)

            if old_topk is not None:
                os.environ["LAISER_ALIGN_TOPK"] = old_topk
            else:
                os.environ.pop("LAISER_ALIGN_TOPK", None)

# Help Section
with st.expander("❓ Help & FAQ"):
    st.markdown(
        """
    ### How This Tool Works
    
    This interactive tool lets you experience the full KSA extraction pipeline using your own API credentials:
    
    **Step 1: Configure API Key**
    - Securely enter your LLM provider credentials
    - Keys are stored in browser session only
    - Never saved to our database or servers
    
    **Step 2: Select AFSC Text**
    - Search AFECD/AFOCD PDFs by AFSC code or keywords
    - Load full page text into the editor
    
    **Step 3: Run Extraction**
    - Run the AFSC → KSA pipeline with LAiSER + LLM
    - Review and download the resulting KSAs
    
    ### What the Pipeline Does
    
    1. Cleans and normalizes the AFSC text
    2. Uses LAiSER to extract skill candidates aligned to ESCO taxonomy (if enabled)
    3. Applies quality filters and de-duplicates near-duplicates
    4. Optionally uses an LLM to generate Knowledge/Ability items
    5. Returns combined KSA items for local review and export
    
    ### Differences vs. Admin Tools
    
    | Feature | Try It Yourself | Admin Tools |
    |--------|-----------------|-------------|
    | Writes to Neo4j | ❌ No | ✅ Yes |
    | API keys | Browser session only | Streamlit secrets / env |
    | Scope | Single AFSC at a time | Bulk AFSC ingestion |
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
    
    Skills extracted by LAiSER are aligned to the **Open Skills / ESCO** taxonomy. Each taxonomy code (e.g., ESCO.95) corresponds to a specific skill label.
    
    - **View complete taxonomy:** [LAiSER Taxonomy CSV](https://github.com/LAiSER-Software/extract-module/blob/main/laiser/public/combined.csv)
    - **Total skills:** 2,217+ standardized skills
    - **Format:** SkillTag (ESCO.XX) → SkillLabel
    """
    )

st.divider()
st.caption("🔬 Try It Yourself | Session-only API keys | No database writes | Download results only")
