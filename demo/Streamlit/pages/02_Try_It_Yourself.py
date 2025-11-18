import sys, pathlib, os, io, re, time
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

# -------- Paths for local docs (if needed later) --------
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

# PDF sources in the repo
SOURCES = {
    "AFECD (Enlisted)": "https://raw.githubusercontent.com/Kyleinexile/fall-2025-group6/main/src/docs/AFECD%202025%20Split.pdf",
    "AFOCD (Officer)": "https://raw.githubusercontent.com/Kyleinexile/fall-2025-group6/main/src/docs/AFOCD%202025%20Split.pdf",
}

st.set_page_config(page_title="Try It Yourself", page_icon="🔬", layout="wide")

# -------- CSS --------
st.markdown(
    """
<style>
    .step-header {
        font-size: 1.3rem;
        font-weight: 700;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.title("🔬 Try It Yourself - Interactive KSA Extraction")

# -------- SESSION STATE (no keys here) --------
if "selected_source" not in st.session_state:
    st.session_state.selected_source = "AFECD (Enlisted)"
if "search_results" not in st.session_state:
    st.session_state.search_results = None
if "search_info" not in st.session_state:
    st.session_state.search_info = {}
if "selected_page_text" not in st.session_state:
    st.session_state.selected_page_text = ""
if "afsc_code" not in st.session_state:
    st.session_state.afsc_code = ""
if "afsc_text" not in st.session_state:
    st.session_state.afsc_text = ""

# -------- UTILITIES --------

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
        except Exception:
            pages.append({"page": i + 1, "text": ""})
    return pages

def highlight_matches(text: str, pattern: str) -> str:
    try:
        rx = re.compile(pattern, flags=re.IGNORECASE)
        return rx.sub(lambda m: f"**{m.group(0)}**", text)
    except re.error:
        return text

def search_pages(pages, query: str, max_hits: int = 50):
    """
    Return full-page text for pages that match, no truncation.
    """
    if not query.strip():
        return []

    results = []
    rx = re.compile(re.escape(query), flags=re.IGNORECASE)
    for page in pages:
        text = page["text"]
        if rx.search(text):
            matches = rx.findall(text)
            results.append(
                {
                    "page": page["page"],
                    "matches": len(matches),
                }
            )
            if len(results) >= max_hits:
                break
    return results

# ================== STEP 1: LLM PROVIDER + API KEY ==================

st.markdown('<div class="step-header">🔑 Step 1: Configure LLM API Key (optional)</div>', unsafe_allow_html=True)

col_p1, col_p2 = st.columns([1, 3])

with col_p1:
    provider_choice = st.selectbox(
        "LLM Provider",
        ["openai", "anthropic", "gemini"],
        help="Provider for the pipeline's Knowledge/Ability generation.",
    )

with col_p2:
    st.markdown(
        f"""
- If you **leave the API key blank**, the pipeline uses **server-side keys** configured in Streamlit secrets.
- If you **enter a key**, it is only used for this run and **not stored**.
- Default behavior (no changes): **OpenAI with server-side key**.
"""
    )

api_key_input = st.text_input(
    f"{provider_choice} API key (optional)",
    type="password",
    placeholder={
        "openai": "sk-...",
        "anthropic": "sk-ant-...",
        "gemini": "AIza...",
    }.get(provider_choice, "API key..."),
    help="Optional override for this run only; not saved anywhere.",
)

# ================== STEP 2: SOURCE DOCUMENT & SEARCH ==================

st.markdown('<div class="step-header">📄 Step 2: Select Source Document & Search</div>', unsafe_allow_html=True)

source = st.radio(
    "Choose AFSC Catalog",
    list(SOURCES.keys()),
    index=list(SOURCES.keys()).index(st.session_state.selected_source),
    horizontal=True,
)
st.session_state.selected_source = source
pages = load_pdf_pages(source)

st.markdown("#### 🔍 Search within the document")
query = st.text_input(
    "Search term (e.g., '1N4', 'Intelligence')",
    value=st.session_state.search_info.get("query", ""),
)

col_search_btn, col_clear_btn = st.columns([3, 1])
with col_search_btn:
    search_btn = st.button("🔎 Search Document", type="primary", use_container_width=True)
with col_clear_btn:
    if st.button("Clear Results", use_container_width=True):
        st.session_state.search_results = None
        st.session_state.search_info = {}
        st.rerun()

if search_btn:
    if not query.strip():
        st.warning("⚠️ Enter a search term to find AFSC sections.")
    else:
        with st.spinner("Searching pages..."):
            results = search_pages(pages, query)
            st.session_state.search_results = results
            st.session_state.search_info = {"query": query, "timestamp": time.time()}

results = st.session_state.search_results

if results is not None:
    st.markdown("#### 📑 Matching Pages")
    if not results:
        st.info("No matches found. Try another search term.")
    else:
        for r in results:
            # Get full text for this page
            page_full = next((p for p in pages if p["page"] == r["page"]), None)
            full_text = page_full["text"] if page_full else ""
            highlighted = highlight_matches(full_text, query)

            with st.expander(f"Page {r['page']} • {r['matches']} match(es)"):
                # Show the full page text, highlighted, no truncation
                st.markdown(highlighted)

                if st.button(
                    f"📥 Use Page {r['page']} as AFSC text",
                    key=f"use_page_{r['page']}",
                    use_container_width=True,
                ):
                    st.session_state.selected_page_text = full_text
                    st.session_state.afsc_text = full_text
                    st.info(f"Loaded full text from page {r['page']} into Step 3.")
                    st.rerun()
else:
    st.info("Use the search bar above to find relevant AFSC sections, then load them into Step 3.")

# ================== STEP 3: AFSC CODE & TEXT ==================

st.markdown('<div class="step-header">🧩 Step 3: Provide AFSC Code and Text</div>', unsafe_allow_html=True)

st.markdown("Enter the AFSC code and paste the relevant text (duties, responsibilities, qualifications, etc.).")

afsc_code = st.text_input(
    "AFSC Code",
    value=st.session_state.afsc_code,
    placeholder="e.g., 1N4, 14N, 21A",
)
st.session_state.afsc_code = afsc_code

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

# ================== SIDEBAR: PIPELINE SETTINGS ==================

with st.sidebar:
    st.markdown("### ⚙️ Extraction Settings")

    st.markdown("**LAiSER Configuration**")
    use_laiser = st.checkbox(
        "Enable LAiSER",
        value=True,
        help="Use LAiSER for skill extraction with ESCO taxonomy.",
    )
    laiser_topk = st.slider(
        "LAiSER max items",
        10,
        30,
        25,
        help="Maximum skills to extract via LAiSER.",
    )

    st.markdown("**LLM Enhancer Configuration**")
    max_llm_items = st.slider(
        "Max K/A to generate",
        3,
        10,
        6,
        help="Maximum Knowledge/Ability items the pipeline's LLM enhancer will generate.",
    )
    temperature = st.slider(
        "Temperature",
        0.0,
        1.0,
        0.2,
        0.05,
        help="Lower = more focused, higher = more creative.",
    )

    st.markdown("---")
    st.markdown(
        """
**Pipeline Overview**

1. Clean & normalize AFSC text  
2. LAiSER extracts skill candidates (optional)  
3. Quality filters & deduplication  
4. LLM enhancer generates Knowledge/Ability items  
5. Combined KSAs returned for review & export  
"""
    )

# ================== STEP 4: RUN EXTRACTION ==================

st.markdown('<div class="step-header">🚀 Step 4: Run KSA Extraction</div>', unsafe_allow_html=True)

can_run = bool(afsc_code.strip() and afsc_text.strip())

if not afsc_code.strip():
    st.warning("⚠️ Enter an AFSC Code in Step 3 (required).")
elif not afsc_text.strip():
    st.warning("⚠️ Add AFSC text in Step 3 to enable extraction.")

# Green primary button styling
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
        # Preserve old env settings
        old_use_laiser = os.getenv("USE_LAISER")
        old_topk = os.getenv("LAISER_ALIGN_TOPK")
        old_llm_provider = os.getenv("LLM_PROVIDER")
        old_openai_key = os.getenv("OPENAI_API_KEY")
        old_anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        old_gemini_key = os.getenv("GEMINI_API_KEY")

        # Apply sidebar / Step 1 overrides for this run only
        os.environ["USE_LAISER"] = "true" if use_laiser else "false"
        os.environ["LAISER_ALIGN_TOPK"] = str(laiser_topk)
        os.environ["LLM_PROVIDER"] = provider_choice  # expected by enhance_llm

        # Optional: override provider-specific key for this run
        key = api_key_input.strip()
        if key:
            if provider_choice == "openai":
                os.environ["OPENAI_API_KEY"] = key
            elif provider_choice == "anthropic":
                os.environ["ANTHROPIC_API_KEY"] = key
            elif provider_choice == "gemini":
                # Adjust if your code expects a different env var name
                os.environ["GEMINI_API_KEY"] = key

        with st.status("Running full pipeline...", expanded=True) as status:
            status.write("🧹 Cleaning text and running LAiSER / filters / dedupe / LLM enhancer...")
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

        # Build rows for display
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

            st.markdown("### 📊 Extracted KSAs")

            df = pd.DataFrame(all_items)

            # Filters
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                type_filter = st.multiselect(
                    "Filter by type",
                    ["knowledge", "skill", "ability"],
                    default=["knowledge", "skill", "ability"],
                )
            with col_f2:
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

            col_e1, col_e2 = st.columns(2)
            with col_e1:
                csv = filtered_df.to_csv(index=False)
                st.download_button(
                    "⬇️ Download Filtered Results",
                    csv,
                    f"{afsc_code or 'extracted'}_ksas.csv",
                    "text/csv",
                    "text/csv",
                    use_container_width=True,
                )
            with col_e2:
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
        # Restore env vars
        if old_use_laiser is not None:
            os.environ["USE_LAISER"] = old_use_laiser
        else:
            os.environ.pop("USE_LAISER", None)

        if old_topk is not None:
            os.environ["LAISER_ALIGN_TOPK"] = old_topk
        else:
            os.environ.pop("LAISER_ALIGN_TOPK", None)

        if old_llm_provider is not None:
            os.environ["LLM_PROVIDER"] = old_llm_provider
        else:
            os.environ.pop("LLM_PROVIDER", None)

        if old_openai_key is not None:
            os.environ["OPENAI_API_KEY"] = old_openai_key
        else:
            os.environ.pop("OPENAI_API_KEY", None)

        if old_anthropic_key is not None:
            os.environ["ANTHROPIC_API_KEY"] = old_anthropic_key
        else:
            os.environ.pop("ANTHROPIC_API_KEY", None)

        if old_gemini_key is not None:
            os.environ["GEMINI_API_KEY"] = old_gemini_key
        else:
            os.environ.pop("GEMINI_API_KEY", None)

# ================== HELP & FOOTER ==================

with st.expander("❓ Help & FAQ"):
    st.markdown(
        """
### How This Tool Works

1. Clean & normalize AFSC text  
2. Run LAiSER (if enabled) to extract ESCO-aligned skills  
3. Apply quality filters & deduplication  
4. Run the LLM enhancer (OpenAI / Anthropic / Gemini) for Knowledge/Ability items  
5. Return combined KSA items for local review and export  

### Key Differences vs Admin Tools

| Feature | Try It Yourself | Admin Tools |
|--------|-----------------|-------------|
| Writes to Neo4j | ❌ No | ✅ Yes |
| API keys | Optional per-run input | Server-side secrets |
| Scope | Single AFSC at a time | Bulk AFSC ingestion |
| Use Case | Testing, demos | Production ingestion |

This page is a **read-only** playground: it never writes to the database and only returns KSAs for download.
"""
    )

st.divider()
st.caption("🔬 Try It Yourself | API keys optional and not stored | No database writes | Download results only")
