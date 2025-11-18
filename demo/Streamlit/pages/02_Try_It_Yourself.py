import sys, pathlib, os, io, re, time, textwrap, importlib
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

load_dotenv()  # load TOML/.env for defaults

# ---- PDF Sources (unchanged) ----
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
    .stButton > button[kind="primary"] { background-color: #004785 !important; border: none !important; color: white !important; }
    .stButton > button[kind="primary"]:hover { background-color: #003366 !important; }

    /* Green primary button for Extract action */
    div[data-testid="stButton"] button[kind="primary"] {
        background-color: #28a745 !important; color: white !important; border: none !important;
        font-size: 18px !important; font-weight: 700 !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover { background-color: #218838 !important; }

    .step-header {
        background: linear-gradient(90deg, #004785 0%, #0066cc 100%);
        color: white; padding: 16px 24px; border-radius: 8px; font-size: 20px; font-weight: 700;
        margin: 24px 0 16px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    hr { margin: 32px 0; border: none; height: 3px; background: linear-gradient(90deg, #004785 0%, transparent 100%); }
    [data-testid="stMetricValue"] { font-size: 28px; font-weight: 700; color: #004785; }
</style>
""", unsafe_allow_html=True)

# ---------- Session State ----------
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

# ---------- Helpers ----------
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
    if provider == "gemini":
        return "GEMINI_API_KEY"
    if provider == "huggingface":
        return "HF_TOKEN"
    return f"{provider.upper()}_API_KEY"

def _apply_laiser_env(provider: str, api_key: str):
    """Mirror the BYO provider/key into LAISER's expected env namespace."""
    os.environ["USE_LAISER"] = "true"
    os.environ.pop("LAISER_NO_LLM", None)
    os.environ["LAISER_LLM_ENABLED"] = "true"
    os.environ["LAISER_LLM_PROVIDER"] = provider
    if provider == "openai":
        os.environ["LAISER_OPENAI_API_KEY"] = api_key
    elif provider in {"gemini", "google", "googleai"}:
        os.environ["LAISER_GEMINI_API_KEY"] = api_key
        os.environ["LAISER_GOOGLE_API_KEY"] = api_key
    elif provider == "anthropic":
        os.environ["LAISER_ANTHROPIC_API_KEY"] = api_key
    elif provider == "huggingface":
        os.environ["LAISER_HF_TOKEN"] = api_key

def _preflight_laiser_gemini_or_fallback():
    """
    If LAISER is set to gemini but the Gemini client isn't importable,
    flip LAISER to openai to avoid the pattern fallback.
    """
    laiser_provider = os.getenv("LAISER_LLM_PROVIDER", "").lower()
    if laiser_provider != "gemini":
        return
    ok = False
    try:
        gm = importlib.import_module("laiser.llm_models.gemini")
        ok = hasattr(gm, "GeminiAPI")
    except Exception:
        ok = False
    if not ok:
        st.warning("LAiSER Gemini client not available in this environment; "
                   "temporarily switching LAiSER skill extractor to OpenAI.")
        os.environ["LAISER_LLM_PROVIDER"] = "openai"
        # If we have a generic OPENAI key, reuse it for LAISER as well.
        if os.getenv("OPENAI_API_KEY") and not os.getenv("LAISER_OPENAI_API_KEY"):
            os.environ["LAISER_OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]

# ---------- UI ----------
st.title("🔬 Try It Yourself - Interactive KSA Extraction")
st.markdown("**Experience the pipeline hands-on with your own API key**")
st.divider()

# STEP 1
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

has_key = bool(api_key.strip())
col_status, col_clear = st.columns([3, 1])
with col_status:
    if has_key:
        st.success(f"✅ API key loaded for **{provider}**")
    else:
        st.warning("⚠️ No API key provided - required for Step 4")
with col_clear:
    if st.button("🗑️ Clear Key"):
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

# STEP 2: Search
st.markdown('<div class="step-header">🔍 Step 2: Search Documentation</div>', unsafe_allow_html=True)
st.markdown("Search through **AFOCD (Officer)** and **AFECD (Enlisted)** documents from the repository")

col_doc, _ = st.columns([2, 1])
with col_doc:
    source = st.selectbox("📄 Select Document", list(SOURCES.keys()))

query = st.text_input(
    "🔍 Search Query",
    placeholder="Try: 14N, 1N4X1, pilot, intelligence, cyber...",
    help="Enter an AFSC code (e.g., 14N, 1N4X1) or keywords (e.g., intelligence, pilot)"
)

col_search, col_clear_search = st.columns([3, 1])
with col_search:
    if st.button("🔍 Search Document", type="primary"):
        if not query.strip():
            st.warning("⚠️ Enter a search term")
        else:
            with st.spinner("Searching..."):
                pages = load_pdf_pages(SOURCES[source])
                results = search_pages(pages, query)
                st.session_state.search_results = results
                st.session_state.search_info = {"query": query, "source": source, "count": len(results)}
with col_clear_search:
    if st.button("🗑️ Clear"):
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
                    if st.button(f"✅ Load Page {r['page']}", key=f"load_{idx}"):
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

# STEP 3: AFSC inputs
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

if st.button("🗑️ Clear Text"):
    st.session_state.afsc_code = ""
    st.session_state.afsc_text = ""
    st.session_state.selected_page_text = ""
    st.rerun()

st.markdown("""
> 💡 **Tip:** Paste the full AFSC section from AFECD/AFOCD, including summary, duties, and qualifications.
> The more complete the context, the better the KSA extraction.
""")

st.divider()

# SIDEBAR
with st.sidebar:
    st.markdown("### ⚙️ Extraction Settings")
    st.markdown("**LAiSER Configuration**")
    use_laiser = st.checkbox("Enable LAiSER", value=True, help="Use LAiSER for skill extraction with ESCO taxonomy alignment")
    laiser_topk = st.slider("LAiSER max items", 10, 30, 25, help="Maximum number of skills LAiSER will extract")
    st.divider()
    st.markdown("""
**LLM Enhancement (Fixed Settings)**

- **Max K/A items:** 6 per AFSC
- **Temperature:** ~0.3 (conservative)
""")
    st.divider()
    st.markdown("""
**Pipeline Steps:**
1. Clean & normalize text
2. LAiSER skill extraction
3. Quality filtering
4. Deduplication
5. LLM K/A generation
6. Combine & export
""")

# STEP 4: Run
st.markdown('<div class="step-header">🚀 Step 4: Run KSA Extraction</div>', unsafe_allow_html=True)
can_run = has_key and bool((st.session_state.afsc_code or "").strip()) and bool((st.session_state.afsc_text or "").strip())
if not has_key:
    st.warning("⚠️ Configure your API key in Step 1 to enable extraction")
elif not (st.session_state.afsc_code or "").strip():
    st.warning("⚠️ Enter an AFSC Code in Step 3 (required)")
elif not (st.session_state.afsc_text or "").strip():
    st.warning("⚠️ Add AFSC text in Step 3 to enable extraction")

if st.button("🚀 Extract KSAs", type="primary", disabled=not can_run):
    try:
        afsc_code = st.session_state.afsc_code
        afsc_text = st.session_state.afsc_text

        # Preserve existing env to restore later
        env_keys_to_backup = [
            "USE_LAISER","LAISER_ALIGN_TOPK","LLM_PROVIDER",
            "OPENAI_API_KEY","ANTHROPIC_API_KEY","GEMINI_API_KEY","GOOGLE_API_KEY","HF_TOKEN",
            "LAISER_NO_LLM","LAISER_LLM_ENABLED","LAISER_LLM_PROVIDER",
            "LAISER_OPENAI_API_KEY","LAISER_ANTHROPIC_API_KEY",
            "LAISER_GEMINI_API_KEY","LAISER_GOOGLE_API_KEY","LAISER_HF_TOKEN"
        ]
        old_env = {k: os.getenv(k) for k in env_keys_to_backup}

        # Clear generic provider keys to avoid unintended fallbacks
        for k in ["OPENAI_API_KEY","ANTHROPIC_API_KEY","GEMINI_API_KEY","GOOGLE_API_KEY","HF_TOKEN"]:
            os.environ.pop(k, None)

        # Apply user-selected provider & key for the enhancer
        os.environ["LLM_PROVIDER"] = provider
        os.environ[get_key_env_name(provider)] = api_key.strip()

        # Apply LAISER settings (try to keep it on gemini by default unless user chose differently)
        os.environ["USE_LAISER"] = "true" if use_laiser else "false"
        os.environ["LAISER_ALIGN_TOPK"] = str(laiser_topk)
        os.environ.pop("LAISER_NO_LLM", None)
        # Prefer Gemini for LAiSER unless user specifically chose something else
        laiser_provider = provider if provider != "huggingface" else "gemini"
        os.environ["LAISER_LLM_ENABLED"] = "true"
        os.environ["LAISER_LLM_PROVIDER"] = laiser_provider
        _apply_laiser_env(laiser_provider, api_key.strip() if laiser_provider == provider else os.getenv("GEMINI_API_KEY",""))

        # Preflight: if LAISER is configured to gemini but client missing, fall back LAISER→openai
        _preflight_laiser_gemini_or_fallback()

        # Lazy import AFTER env is set; reload if already imported
        if "afsc_pipeline.extract_laiser" in sys.modules:
            importlib.reload(sys.modules["afsc_pipeline.extract_laiser"])
        if "afsc_pipeline.pipeline" in sys.modules:
            importlib.reload(sys.modules["afsc_pipeline.pipeline"])
        from afsc_pipeline.pipeline import run_pipeline_demo

        with st.status("Running full pipeline...", expanded=True) as status:
            status.write("🧹 Preprocessing text...")
            time.sleep(0.2)
            if use_laiser:
                status.write("🔍 LAiSER extracting skills with taxonomy alignment...")
                time.sleep(0.2)
            status.write("🤖 LLM generating Knowledge/Ability items...")
            time.sleep(0.2)
            status.write("🔄 Deduplicating and filtering...")

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

            laiser_diag = {
                "provider": os.getenv("LAISER_LLM_PROVIDER"),
                "use_llm": os.getenv("LAISER_LLM_ENABLED"),
                "openai": bool(os.getenv("LAISER_OPENAI_API_KEY")),
                "anthropic": bool(os.getenv("LAISER_ANTHROPIC_API_KEY")),
                "gemini/google": bool(os.getenv("LAISER_GEMINI_API_KEY") or os.getenv("LAISER_GOOGLE_API_KEY")),
                "hf": bool(os.getenv("LAISER_HF_TOKEN")),
            }

            status.write(f"✅ Pipeline complete in {elapsed:.2f}s – {n_total} items ({n_esco} with taxonomy)")
            if used_fallback:
                status.write("⚠️ LAiSER unavailable; fallback extractor was used")
            status.write(f"🔎 LAISER diag → {laiser_diag}")
            status.update(label="✅ Extraction Complete!", state="complete")

        # Format results for display
        all_items = []
        for it in items:
            raw_type = getattr(it, "item_type", "")
            raw_type_val = raw_type.value if hasattr(raw_type, "value") else str(raw_type)
            lt = str(raw_type_val).lower()
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

        # Results
        st.markdown("### 📊 Extracted KSAs")
        df = pd.DataFrame(all_items)

        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            type_filter = st.multiselect(
                "Filter by type",
                ['knowledge', 'skill', 'ability'],
                default=['knowledge', 'skill', 'ability']
            )
        with col_filter2:
            taxonomy_filter = st.selectbox(
                "Filter by taxonomy",
                ["All", "Only taxonomy-aligned", "Only non-taxonomy"],
                index=0
            )

        filtered_df = df[df['Type'].isin(type_filter)]
        if taxonomy_filter == "Only taxonomy-aligned":
            filtered_df = filtered_df[filtered_df['Taxonomy'] != ""]
        elif taxonomy_filter == "Only non-taxonomy":
            filtered_df = filtered_df[filtered_df['Taxonomy'] == ""]

        st.caption(f"Showing {len(filtered_df)} of {len(df)} items")
        st.dataframe(filtered_df, hide_index=True, width='stretch',
                     column_config={
                         "Confidence": st.column_config.NumberColumn(format="%.2f"),
                         "Taxonomy": st.column_config.TextColumn("Skill Taxonomy")
                     })

        # Exports
        st.markdown("### 💾 Export Results")
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            csv = filtered_df.to_csv(index=False)
            st.download_button("⬇️ Download Filtered Results", csv, f"{afsc_code or 'extracted'}_ksas.csv", "text/csv")
        with col_exp2:
            full_csv = df.to_csv(index=False)
            st.download_button("⬇️ Download All Results", full_csv, f"{afsc_code or 'extracted'}_ksas_full.csv", "text/csv")

        st.info("💡 **Note:** These results are NOT saved to the database. This is a demo/testing tool only. Use Admin Tools for permanent storage.")
        st.caption("📖 **Skill Taxonomy Reference:** Skills are aligned to the Open Skills Network (OSN) taxonomy. View the complete taxonomy codes and labels: [LAiSER Taxonomy CSV](https://github.com/LAiSER-Software/extract-module/blob/main/laiser/public/combined.csv)")

    except Exception as e:
        st.error(f"❌ Extraction failed: {e}")
        import traceback
        with st.expander("📋 Error Details"):
            st.code(traceback.format_exc())

    finally:
        # Restore env
        for k, v in (old_env or {}).items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

# Help
with st.expander("❓ Help & FAQ"):
    st.markdown("""
### How This Tool Works
1) Enter your own API key, 2) find/load AFSC text, 3) run the extractor.

- LAiSER runs with your chosen provider (prefers Gemini; auto-falls back to OpenAI if Gemini client missing)
- LLM adds Knowledge/Ability bullets with your selected provider
- No database writes; download CSVs

### Providers
- **OpenAI** · **Anthropic** · **Google Gemini** · **Hugging Face (FREE)**
""")

st.divider()
st.caption("🔬 Try It Yourself | Session-only API keys | No database writes | Download results only")
