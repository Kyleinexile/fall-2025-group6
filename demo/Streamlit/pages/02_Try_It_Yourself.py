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

# Paths
DOCS_ROOTS = [
    pathlib.Path("/workspaces/docs_text"),
    SRC / "src" / "docs_text",
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

# ============ POLISHED CSS - AIR FORCE BLUE THEME ============
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stButton > button { font-size: 16px !important; padding: 12px 24px !important; font-weight: 600 !important; }
    .stButton > button[kind="primary"] { background-color: #004785 !important; border: none !important; }
    .stButton > button[kind="primary"]:hover { background-color: #003366 !important; }
    div[data-testid="stButton"] button[kind="primary"] { background-color: #28a745 !important; color: white !important; border: none !important; font-size: 18px !important; font-weight: 700 !important; }
    div[data-testid="stButton"] button[kind="primary"]:hover { background-color: #218838 !important; }
    .step-header { background: linear-gradient(90deg, #004785 0%, #0066cc 100%); color: white; padding: 16px 24px; border-radius: 8px; font-size: 20px; font-weight: 700; margin: 24px 0 16px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    hr { margin: 32px 0; border: none; height: 3px; background: linear-gradient(90deg, #004785 0%, transparent 100%); }
    [data-testid="stMetricValue"] { font-size: 28px; font-weight: 700; color: #004785; }
</style>
""", unsafe_allow_html=True)

# ============ Session State ============
for key, default in {
    "selected_source": "AFECD (Enlisted)",
    "search_results": None,
    "search_info": {},
    "selected_page_text": "",
    "afsc_code": "",
    "afsc_text": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ============ Helpers ============
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
        except Exception:
            pages.append({"page": i + 1, "text": ""})
    return pages

def highlight_matches(text: str, pattern: str) -> str:
    try:
        rx = re.compile(pattern, flags=re.IGNORECASE)
        return rx.sub(lambda m: f"**`{m.group(0)}`**", text)
    except Exception:
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
                "full_text": text,
            })
            if len(results) >= max_hits:
                break
    return results

def get_key_env_name(provider: str) -> str:
    provider = provider.lower()
    if provider == "openai":
        return "OPENAI_API_KEY"
    if provider == "anthropic":
        return "ANTHROPIC_API_KEY"
    if provider in {"gemini", "google", "googleai"}:
        return "GOOGLE_API_KEY"  # enhance_llm prefers GOOGLE_API_KEY or GEMINI_API_KEY
    if provider == "huggingface":
        return "HF_TOKEN"
    return f"{provider.upper()}_API_KEY"

def apply_provider_and_key(provider: str, api_key: str, hf_model: Optional[str] = None):
    """
    Provider-first, then only the correct key. Clears others to avoid
    accidental fallback to Streamlit secrets.
    """
    provider = (provider or "").strip().lower()
    os.environ["LLM_PROVIDER"] = provider

    # Clear all LLM keys so only the selected provider is available
    for key_name in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "HF_TOKEN"]:
        os.environ.pop(key_name, None)

    # Set only the matching key
    key_env_name = get_key_env_name(provider)
    if api_key.strip():
        os.environ[key_env_name] = api_key.strip()

    # HF model hint (optional but helpful)
    if provider == "huggingface":
        if hf_model:
            os.environ["LLM_MODEL_HUGGINGFACE"] = hf_model
        else:
            # safe default if not set
            os.environ.setdefault("LLM_MODEL_HUGGINGFACE", "HuggingFaceH4/zephyr-7b-beta")

# ============ UI ============
st.title("🔬 Try It Yourself - Interactive KSA Extraction")
st.markdown("**Experience the pipeline hands-on with your own API key**")
st.divider()

# STEP 1: Configure API Key
st.markdown('<div class="step-header">🔑 Step 1: Configure Your API Key</div>', unsafe_allow_html=True)
st.info("🔒 **Privacy Notice:** Your API key is stored in browser session only. Never saved to our servers or database. Cleared when you close the browser.")

col_provider, col_key = st.columns([1, 3])
with col_provider:
    provider = st.selectbox(
        "LLM Provider",
        ["openai", "anthropic", "gemini", "huggingface"],
        help="Choose which LLM provider to use for Knowledge/Ability generation."
    )
with col_key:
    placeholder = {
        "openai": "sk-proj-...",
        "anthropic": "sk-ant-...",
        "gemini": "AIza...",
        "huggingface": "hf_xxx_your_token..."
    }[provider]
    api_key = st.text_input(
        "API Key / Token",
        type="password",
        placeholder=placeholder,
        help="Required for this demo. Not written to Neo4j or any external store."
    )

# HF model picker (only visible for HF)
hf_model = None
if provider == "huggingface":
    st.caption("💡 Hugging Face tip: choose a chat-capable model. Defaults to **HuggingFaceH4/zephyr-7b-beta**.")
    hf_model = st.selectbox(
        "Hugging Face model",
        [
            "HuggingFaceH4/zephyr-7b-beta",
            "google/gemma-2-9b-it",
            "mistralai/Mistral-7B-Instruct-v0.3",  # supported via chat endpoint
            "meta-llama/Llama-3.2-3B-Instruct",
        ],
        index=0,
        help="We will call HF's chat endpoint first; if unavailable, we fall back to text-generation."
    )

has_key = bool(api_key.strip())
col_status, col_clear = st.columns([3, 1])
with col_status:
    if has_key:
        st.success(f"✅ API key loaded for **{provider}**")
    else:
        st.warning("⚠️ No API key provided - required for Step 4")
with col_clear:
    if st.button("🗑️ Clear Key", use_container_width=True):
        api_key = ""
        st.rerun()

with st.expander("🔐 How to get an API key / token"):
    st.markdown("""
    - **OpenAI**: https://platform.openai.com/api-keys  
    - **Anthropic**: https://console.anthropic.com/settings/keys  
    - **Google Gemini**: https://aistudio.google.com/app/apikey  
    - **Hugging Face (FREE tokens)**: https://huggingface.co/settings/tokens
    """)

st.divider()

# STEP 2: Search Documentation
st.markdown('<div class="step-header">🔍 Step 2: Search Documentation</div>', unsafe_allow_html=True)
st.markdown("Search **AFOCD (Officer)** and **AFECD (Enlisted)** documents from the repository")

col_doc, col_mode = st.columns([2, 1])
with col_doc:
    source = st.selectbox("📄 Select Document", list(SOURCES.keys()))
with col_mode:
    _ = st.radio("Search by", ["AFSC Code", "Keywords"], horizontal=True, label_visibility="collapsed")

query = st.text_input(
    "🔍 Search Query",
    placeholder="Try: 14N, 1N4X1, pilot, intelligence, cyber...",
    help="Enter an AFSC code (e.g., 14N, 1N4X1) or keywords (e.g., intelligence, pilot)"
)
col_search, col_clear_search = st.columns([3, 1])
with col_search:
    if st.button("🔍 Search Document", type="primary", use_container_width=True):
        if not query.strip():
            st.warning("⚠️ Enter a search term")
        else:
            with st.spinner("Searching..."):
                pages = load_pdf_pages(SOURCES[source])
                results = search_pages(pages, query)
                st.session_state.search_results = results
                st.session_state.search_info = {"query": query, "source": source, "count": len(results)}
with col_clear_search:
    if st.button("🗑️ Clear", use_container_width=True):
        st.session_state.search_results = None
        st.session_state.search_info = {}
        st.rerun()

if st.session_state.search_results is not None:
    results = st.session_state.search_results
    info = st.session_state.search_info
    if results:
        st.success(f"✅ Found {len(results)} result(s) for **'{info['query']}'** in {info['source']}")
        for idx, r in enumerate(results):
            full = r["full_text"]
            full_highlighted = highlight_matches(full, info["query"]) if info["query"] else full
            with st.expander(f"📄 Page {r['page']} • {r['matches']} match(es)", expanded=False):
                st.markdown(r["snippet"])
                with st.expander("📖 Show full page text"):
                    st.markdown(full_highlighted)
                col_btn = st.columns([1, 2])[0]
                with col_btn:
                    if st.button(f"✅ Load Page {r['page']}", key=f"load_{idx}", use_container_width=True):
                        st.session_state.selected_page_text = full
                        st.session_state.afsc_text = full
                        st.success(f"✅ Loaded page {r['page']} text into Step 3")
                        time.sleep(0.3)
                        st.rerun()
            if idx < len(results) - 1:
                st.markdown("---")
    else:
        st.info("ℹ️ No matches found. Try different search terms.")
else:
    st.info("💡 Use the search above to find AFSC sections, then load them into Step 3")

st.divider()

# STEP 3: AFSC Code & Text
st.markdown('<div class="step-header">📝 Step 3: Provide AFSC Code and Text</div>', unsafe_allow_html=True)
col_code, col_info = st.columns([2, 1])
with col_code:
    afsc_code = st.text_input(
        "AFSC Code *",
        value=st.session_state.afsc_code,
        placeholder="e.g., 14N, 1N4X1",
        help="Required - used to tag output and provide context for LLM"
    )
    st.session_state.afsc_code = afsc_code
with col_info:
    char_count = len(st.session_state.afsc_text or st.session_state.selected_page_text or "")
    st.metric("Text Length", f"{char_count:,} chars")

afsc_text = st.text_area(
    "AFSC Documentation",
    value=st.session_state.afsc_text or st.session_state.selected_page_text,
    height=300,
    placeholder="Paste AFSC text here, or use Step 2 to search and load documentation...",
    help="You can paste text directly or load it from the search above"
)
st.session_state.afsc_text = afsc_text

if st.button("🗑️ Clear Text", use_container_width=True):
    st.session_state.afsc_code = ""
    st.session_state.afsc_text = ""
    st.session_state.selected_page_text = ""
    st.rerun()

st.markdown("""
> 💡 **Tip:** Paste the full AFSC section from AFECD/AFOCD, including summary, duties, and qualifications.
""")
st.divider()

# SIDEBAR: Settings
with st.sidebar:
    st.markdown("### ⚙️ Extraction Settings")
    st.markdown("**LAiSER Configuration**")
    use_laiser = st.checkbox("Enable LAiSER", value=True, help="Use LAiSER for skill extraction with ESCO taxonomy alignment")
    laiser_topk = st.slider("LAiSER max items", 10, 30, 25, help="Maximum number of skills LAiSER will extract")
    st.divider()
    st.markdown("**LLM Enhancement (Fixed)**\n\n- Max K/A items: 6\n- Temperature: 0.2–0.3")
    st.divider()
    st.markdown("**Pipeline Steps:**\n1. Clean & normalize\n2. LAiSER extraction\n3. Quality filter\n4. Deduplication\n5. LLM K/A generation\n6. Combine & export")

# STEP 4: Run Extraction
st.markdown('<div class="step-header">🚀 Step 4: Run KSA Extraction</div>', unsafe_allow_html=True)

can_run = has_key and bool(afsc_code.strip()) and bool(afsc_text.strip())
if not has_key:
    st.warning("⚠️ Configure your API key in Step 1 to enable extraction")
elif not afsc_code.strip():
    st.warning("⚠️ Enter an AFSC Code in Step 3 (required)")
elif not afsc_text.strip():
    st.warning("⚠️ Add AFSC text in Step 3 to enable extraction")

if st.button("🚀 Extract KSAs", type="primary", disabled=not can_run, use_container_width=True):
    try:
        # Backup env
        old_env = {k: os.getenv(k) for k in [
            "USE_LAISER", "LAISER_ALIGN_TOPK", "LLM_PROVIDER",
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "HF_TOKEN",
            "LLM_MODEL_HUGGINGFACE"
        ]}

        # Apply run-time provider/key (provider-first, clear others)
        os.environ["USE_LAISER"] = "true" if use_laiser else "false"
        os.environ["LAISER_ALIGN_TOPK"] = str(laiser_topk)
        apply_provider_and_key(provider, api_key, hf_model)

        # Debug panel so you can *see* what's being used
        with st.expander("🔎 Runtime Debug (what the backend will see)", expanded=False):
            st.write({
                "LLM_PROVIDER": os.getenv("LLM_PROVIDER"),
                "OPENAI_API_KEY_set": bool(os.getenv("OPENAI_API_KEY")),
                "ANTHROPIC_API_KEY_set": bool(os.getenv("ANTHROPIC_API_KEY")),
                "GOOGLE_API_KEY_set": bool(os.getenv("GOOGLE_API_KEY")),
                "HF_TOKEN_set": bool(os.getenv("HF_TOKEN")),
                "LLM_MODEL_HUGGINGFACE": os.getenv("LLM_MODEL_HUGGINGFACE"),
            })

        with st.status("Running full pipeline...", expanded=True) as status:
            status.write("🧹 Preprocessing text...")
            time.sleep(0.2)
            if use_laiser:
                status.write("🔍 LAiSER extracting skills with ESCO taxonomy...")
            status.write("🤖 LLM generating Knowledge/Ability items...")
            status.write("🔄 Deduplicating and filtering...")

            t0 = time.time()
            summary = run_pipeline_demo(
                afsc_code=afsc_code or "UNKNOWN",
                afsc_raw_text=afsc_text,
            )
            elapsed = time.time() - t0

            items = summary.get("items", []) or []
            n_total = len(items)
            n_esco = summary.get("esco_tagged_count", sum(1 for it in items if getattr(it, "esco_id", None)))
            used_fallback = summary.get("used_fallback", False)

            status.write(f"✅ Pipeline complete in {elapsed:.2f}s – {n_total} items ({n_esco} with ESCO IDs)")
            if used_fallback:
                status.write("⚠️ LAiSER unavailable; fallback pattern extractor was used")
            status.update(label="✅ Extraction Complete!", state="complete")

        all_items = []
        for it in items:
            raw_type = getattr(it, "item_type", "")
            raw_type_val = str(raw_type.value) if hasattr(raw_type, "value") else str(raw_type)
            lt = raw_type_val.lower()
            if "know" in lt:
                type_label = "knowledge"
            elif "abil" in lt:
                type_label = "ability"
            else:
                type_label = "skill"
            all_items.append({
                "Type": type_label,
                "Text": getattr(it, "text", ""),
                "Confidence": float(getattr(it, "confidence", 0.0) or 0.0),
                "Source": getattr(it, "source", "pipeline"),
                "Taxonomy": getattr(it, "esco_id", "") or "",
            })

        if not all_items:
            st.warning("⚠️ No items extracted. Try enabling LAiSER or adjusting settings in the sidebar.")
            st.stop()

        st.success(f"✅ Successfully extracted {len(all_items)} KSAs!")
        st.balloons()

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

        st.markdown("### 📊 Extracted KSAs")
        df = pd.DataFrame(all_items)

        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            type_filter = st.multiselect("Filter by type", ['knowledge', 'skill', 'ability'], default=['knowledge', 'skill', 'ability'])
        with col_filter2:
            taxonomy_filter = st.selectbox("Filter by taxonomy", ["All", "Only taxonomy-aligned", "Only non-taxonomy"], index=0)

        filtered_df = df[df['Type'].isin(type_filter)]
        if taxonomy_filter == "Only taxonomy-aligned":
            filtered_df = filtered_df[filtered_df['Taxonomy'] != ""]
        elif taxonomy_filter == "Only non-taxonomy":
            filtered_df = filtered_df[filtered_df['Taxonomy'] == ""]

        st.caption(f"Showing {len(filtered_df)} of {len(df)} items")
        st.dataframe(filtered_df, use_container_width=True, hide_index=True,
                     column_config={"Confidence": st.column_config.NumberColumn(format="%.2f"),
                                    "Taxonomy": st.column_config.TextColumn("Skill Taxonomy")})

        st.markdown("### 💾 Export Results")
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            csv = filtered_df.to_csv(index=False)
            st.download_button("⬇️ Download Filtered Results", csv, f"{afsc_code or 'extracted'}_ksas.csv", "text/csv", use_container_width=True)
        with col_exp2:
            full_csv = df.to_csv(index=False)
            st.download_button("⬇️ Download All Results", full_csv, f"{afsc_code or 'extracted'}_ksas_full.csv", "text/csv", use_container_width=True)

        st.info("💡 **Note:** These results are NOT saved to the database. Use Admin Tools for permanent storage.")
        st.caption("📖 Skill Taxonomy: [LAiSER Taxonomy CSV](https://github.com/LAiSER-Software/extract-module/blob/main/laiser/public/combined.csv)")

    except Exception as e:
        st.error(f"❌ Extraction failed: {e}")
        import traceback
        with st.expander("📋 Error Details"):
            st.code(traceback.format_exc())

    finally:
        # Restore environment
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

# Help
with st.expander("❓ Help & FAQ"):
    st.markdown("""
    ### Keys & Privacy
    - Your API key is session-only. Not stored server-side.
    ### Providers
    - Hugging Face free tokens work well; choose a chat-capable model like **HuggingFaceH4/zephyr-7b-beta**.
    """)
st.divider()
st.caption("🔬 Try It Yourself | Session-only API keys | No database writes | Download results only")
