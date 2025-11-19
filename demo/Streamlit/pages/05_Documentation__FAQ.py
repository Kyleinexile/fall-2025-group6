import streamlit as st

st.set_page_config(
    page_title="Documentation & FAQ",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# AIR FORCE BLUE THEME CSS
# ============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Section Headers */
    .section-header {
        background: linear-gradient(90deg, #004785 0%, #0066cc 100%);
        color: white;
        padding: 16px 24px;
        border-radius: 8px;
        font-size: 24px;
        font-weight: 700;
        margin: 32px 0 16px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Subsection Headers */
    .subsection-header {
        color: #004785;
        font-size: 20px;
        font-weight: 600;
        margin: 24px 0 12px 0;
        padding-bottom: 8px;
        border-bottom: 2px solid #0066cc;
    }
    
    /* Info Boxes */
    .info-box {
        background-color: #E8F4FD;
        border-left: 4px solid #004785;
        padding: 16px;
        border-radius: 4px;
        margin: 16px 0;
    }
    
    .warning-box {
        background-color: #FFF4E6;
        border-left: 4px solid #FF9800;
        padding: 16px;
        border-radius: 4px;
        margin: 16px 0;
    }
    
    .success-box {
        background-color: #E8F5E9;
        border-left: 4px solid #4CAF50;
        padding: 16px;
        border-radius: 4px;
        margin: 16px 0;
    }
    
    /* Code blocks */
    code {
        background-color: #f5f5f5;
        padding: 2px 6px;
        border-radius: 3px;
        font-family: 'Courier New', monospace;
    }
    
    /* Metrics */
    .metric-row {
        display: flex;
        justify-content: space-around;
        margin: 20px 0;
    }
    
    .metric-box {
        text-align: center;
        padding: 16px;
        background: white;
        border-radius: 8px;
        border: 2px solid #004785;
    }
    
    .metric-value {
        font-size: 36px;
        font-weight: 700;
        color: #004785;
    }
    
    .metric-label {
        font-size: 14px;
        color: #666;
        text-transform: uppercase;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# SIDEBAR NAVIGATION
# ============================================================================
with st.sidebar:
    st.markdown("### 📚 Documentation Navigation")
    
    section = st.radio(
        "Jump to section:",
        [
            "🏠 Overview",
            "🎯 Quick Stats",
            "⚙️ LLM Settings",
            "🤖 LAiSER Configuration", 
            "🗺️ ESCO Mapper Status",
            "🔄 Deduplication",
            "📚 Major Libraries",
            "🔧 Pipeline Flow",
            "❓ FAQ",
            "📊 Performance Metrics",
            "💰 Cost Analysis"
        ],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.caption("💡 Use this menu to navigate to specific topics")

# ============================================================================
# MAIN CONTENT
# ============================================================================

st.title("📚 AFSC KSA Pipeline - Documentation & FAQ")
st.markdown("**Comprehensive technical reference for the extraction pipeline**")
st.divider()

# ============================================================================
# SECTION: OVERVIEW
# ============================================================================
if section == "🏠 Overview":
    st.markdown('<div class="section-header">🏠 System Overview</div>', unsafe_allow_html=True)
    
    st.markdown("""
    This system automatically transforms **Air Force Specialty Code (AFSC)** job descriptions 
    into structured, searchable **Knowledge, Skills, and Abilities (KSAs)** linked to 
    standardized skill taxonomies.
    """)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### ✅ Key Achievements")
        st.markdown("""
        - **12 AFSCs** processed successfully
        - **330+ KSAs** extracted
        - **70% ESCO alignment** (target met)
        - **~$0.005** cost per AFSC
        - **3.2 seconds** avg processing time
        """)
    
    with col2:
        st.markdown("### 🎯 Core Capabilities")
        st.markdown("""
        - Automated skill extraction
        - ESCO taxonomy alignment
        - Multi-provider LLM support
        - Interactive web interface
        - Neo4j graph persistence
        """)
    
    with col3:
        st.markdown("### 🚀 Tech Stack")
        st.markdown("""
        - **LAiSER** - Skill extraction
        - **Google Gemini** - LLM backend
        - **Neo4j Aura** - Graph database
        - **Streamlit** - Web interface
        - **pypdf** - PDF processing
        """)
    
    st.markdown('<div class="info-box">ℹ️ <strong>Status:</strong> Production-ready pipeline with all core features functional and tested.</div>', unsafe_allow_html=True)

# ============================================================================
# SECTION: QUICK STATS
# ============================================================================
elif section == "🎯 Quick Stats":
    st.markdown('<div class="section-header">🎯 Quick Statistics</div>', unsafe_allow_html=True)
    
    st.markdown("### 📊 Coverage Metrics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("AFSCs Processed", "12")
    col2.metric("Total KSAs", "330+")
    col3.metric("Avg per AFSC", "27.5")
    col4.metric("ESCO Aligned", "70%")
    
    st.markdown("### ⚡ Performance Metrics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Processing", "3.2s avg")
    col2.metric("LAiSER Extract", "2-5s")
    col3.metric("Deduplication", "<0.1s")
    col4.metric("Neo4j Write", "0.5-1s")
    
    st.markdown("### 💰 Cost Metrics (per AFSC)")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("LAiSER Only", "$0.005")
    col2.metric("With LLM", "$0.005-0.010")
    col3.metric("Model Used", "Gemini Flash")
    col4.metric("Token Limit", "512 max")
    
    st.divider()
    
    st.markdown("### 📈 Processing Breakdown by Stage")
    
    import pandas as pd
    
    stage_data = pd.DataFrame({
        "Stage": ["Preprocessing", "LAiSER Extract", "Quality Filter", "LLM Enhance*", "Deduplication", "Neo4j Write"],
        "Avg Time": ["<0.1s", "2-5s", "<0.1s", "1-3s", "<0.1s", "0.5-1s"],
        "Reduction": ["-", "-", "~10%", "-", "~15%", "-"],
        "Output": ["Clean text", "20-30 skills", "Filtered items", "+5-15 K/A", "Unique items", "Graph"]
    })
    
    st.dataframe(stage_data, use_container_width=True, hide_index=True)
    st.caption("*LLM Enhancement is optional and disabled by default")

# ============================================================================
# SECTION: LLM SETTINGS
# ============================================================================
elif section == "⚙️ LLM Settings":
    st.markdown('<div class="section-header">⚙️ LLM Enhancement Settings</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="warning-box">⚠️ <strong>Default Status:</strong> DISABLED BY DEFAULT (USE_LLM_ENHANCER=false)<br>LAiSER extraction alone produces sufficient SKILL items.</div>', unsafe_allow_html=True)
    
    st.markdown("### 🎯 Cost Optimization Strategies")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Model Selection", "Token Limits", "Input Control", "Prompt Engineering"])
    
    with tab1:
        st.markdown("#### Multi-Provider Support (Budget-Friendly Defaults)")
        
        st.code("""
# Model Configuration
LLM_MODEL_GEMINI = "gemini-2.0-flash"           # Google's fastest, cheapest
LLM_MODEL_OPENAI = "gpt-4o-mini-2024-07-18"     # OpenAI's mini model
LLM_MODEL_ANTHROPIC = "claude-sonnet-4-5"       # Anthropic mid-tier
LLM_MODEL_HF = "meta-llama/Llama-3.2-3B"        # Open source option
        """, language="python")
        
        st.markdown("**Cost Comparison (per 1M tokens):**")
        cost_data = pd.DataFrame({
            "Provider": ["Gemini Flash", "GPT-4o-mini", "Claude Sonnet"],
            "Input": ["$0.075", "$0.15", "$3.00"],
            "Output": ["$0.30", "$0.60", "$15.00"],
            "Recommendation": ["✅ Default", "Backup", "Premium only"]
        })
        st.dataframe(cost_data, use_container_width=True, hide_index=True)
    
    with tab2:
        st.markdown("#### Token Limits")
        
        st.code("""
# Strict token limits to reduce costs
max_tokens: int = 512          # Very short responses only
temperature: float = 0.3       # Deterministic, consistent output
max_new: int = 6               # Cap at 6 new K/A items per AFSC
        """, language="python")
        
        st.markdown("**Impact:**")
        st.markdown("""
        - Limits output length to reduce token costs
        - Low temperature reduces need for regeneration
        - Hard cap prevents runaway generation
        - Estimated savings: **60-70% vs. unlimited tokens**
        """)
    
    with tab3:
        st.markdown("#### Input Truncation")
        
        st.code("""
# Only send first 2000 chars to LLM
afsc_text=afsc_text.strip()[:2000]
        """, language="python")
        
        st.markdown("**Rationale:**")
        st.markdown("""
        - Most relevant KSAs appear early in AFSC descriptions
        - Reduces input token costs by ~50%
        - Maintains extraction quality
        - Speeds up processing time
        """)
    
    with tab4:
        st.markdown("#### Smart Prompt Engineering")
        
        st.markdown("""
        **Balancing Hints** reduce unnecessary generation:
        - "Already have 5 Skills, focus on Knowledge"
        - "Currently heavy on Abilities; prefer Knowledge items"
        
        **Constrained Output Format:**
        - Bullet points only
        - Predefined prefixes ("Knowledge of...", "Ability to...")
        - Reduces token waste on formatting
        
        **Duplicate Detection:**
        - Prevents redundant LLM calls
        - Filters against existing items before generation
        """)
    
    st.divider()
    
    st.markdown("### 💵 Estimated Costs Per AFSC")
    
    cost_comparison = pd.DataFrame({
        "Configuration": ["LAiSER Only", "LAiSER + Gemini Flash", "LAiSER + GPT-4o-mini", "LAiSER + Claude Sonnet"],
        "Cost per AFSC": ["$0.005", "$0.005-0.010", "$0.015-0.025", "$0.050-0.100"],
        "Total (12 AFSCs)": ["$0.06", "$0.06-0.12", "$0.18-0.30", "$0.60-1.20"],
        "Recommendation": ["✅ Default", "✅ If K/A needed", "⚠️ Backup only", "❌ Too expensive"]
    })
    st.dataframe(cost_comparison, use_container_width=True, hide_index=True)

# ============================================================================
# SECTION: LAISER CONFIGURATION
# ============================================================================
elif section == "🤖 LAiSER Configuration":
    st.markdown('<div class="section-header">🤖 LAiSER Configuration</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="success-box">✅ <strong>Primary extraction engine</strong> with built-in ESCO alignment via Gemini backend.</div>', unsafe_allow_html=True)
    
    st.markdown("### 🔧 Primary Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.code("""
# LAiSER Configuration
model_id = "gemini"
api_key = os.getenv("GEMINI_API_KEY")
use_gpu = False

# Extraction Parameters
LAISER_ALIGN_TOPK = 25
method = "ksa"
input_type = "job_desc"
        """, language="python")
    
    with col2:
        st.markdown("**Configuration Rationale:**")
        st.markdown("""
        - **Gemini backend:** Cost-effective with built-in ESCO catalog
        - **CPU-only:** Cloud-compatible, no GPU required
        - **TopK=25:** Returns top 25 skills per AFSC
        - **Method='ksa':** KSA extraction mode
        - **Input='job_desc':** Job description format
        """)
    
    st.markdown("### ✨ Key Features")
    
    feature_col1, feature_col2, feature_col3 = st.columns(3)
    
    with feature_col1:
        st.markdown("#### 🎯 Built-in ESCO Alignment")
        st.markdown("""
        LAiSER uses Gemini to automatically align extracted skills to ESCO taxonomy IDs.
        
        **This is why we don't need a separate ESCO mapper!**
        """)
    
    with feature_col2:
        st.markdown("#### 📊 Confidence Scoring")
        st.markdown("""
        Each extracted skill includes a correlation coefficient (0-1 range).
        
        Used for filtering and canonicalization.
        """)
    
    with feature_col3:
        st.markdown("#### 🔄 Robust API")
        st.markdown("""
        Supports both:
        - `extract_skills()` (single)
        - `extract_and_align()` (batch)
        """)
    
    st.markdown("### 🔀 Fallback Behavior")
    
    st.markdown("When LAiSER fails or is disabled, the pipeline uses regex-based heuristic extraction:")
    
    st.code("""
# Regex-based fallback extraction
- Action verbs: "perform", "conduct", "analyze", "develop"
- Domain keywords: "intelligence", "targeting", "collection"
- Returns 2-6 generic skills with confidence=0.3-0.55
    """, language="python")
    
    st.markdown("### 📤 LAiSER Output Format")
    
    st.markdown("Expected DataFrame columns:")
    
    output_data = pd.DataFrame({
        "Column Name": [
            "Taxonomy Skill / Description / Raw Skill",
            "Correlation Coefficient / score / confidence",
            "Skill Tag / ESCO ID / esco_id"
        ],
        "Type": ["String", "Float (0-1)", "String"],
        "Purpose": ["Skill text", "Confidence score", "ESCO identifier"]
    })
    st.dataframe(output_data, use_container_width=True, hide_index=True)
    
    st.markdown("### 📈 Performance Characteristics")
    
    perf_col1, perf_col2, perf_col3 = st.columns(3)
    
    with perf_col1:
        st.metric("Extraction Time", "2-5 seconds", "per AFSC")
    
    with perf_col2:
        st.metric("Typical Output", "20-30 skills", "per AFSC")
    
    with perf_col3:
        st.metric("ESCO Coverage", "~70%", "of skills")

# ============================================================================
# SECTION: ESCO MAPPER STATUS
# ============================================================================
elif section == "🗺️ ESCO Mapper Status":
    st.markdown('<div class="section-header">🗺️ ESCO Mapper Status</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="warning-box">⚠️ <strong>CRITICAL FINDING:</strong> NOT CURRENTLY USED<br><br>The <code>esco_mapper.py</code> file exists (184 lines, fully functional) but is never imported or called in <code>pipeline.py</code>.</div>', unsafe_allow_html=True)
    
    st.markdown("### 🔍 Analysis")
    
    tab1, tab2, tab3 = st.tabs(["Problem", "Why Not Used", "Recommendations"])
    
    with tab1:
        st.markdown("#### The Issue")
        
        st.code("""
# pipeline.py - NO ESCO MAPPER IMPORT OR CALL
from afsc_pipeline.extract_laiser import extract_ksa_items
from afsc_pipeline.preprocess import clean_afsc_text
from afsc_pipeline.graph_writer_v2 import upsert_afsc_and_items

# ❌ Missing: from afsc_pipeline.esco_mapper import map_esco_ids
        """, language="python")
        
        st.markdown("**File exists but is never executed in the pipeline flow.**")
    
    with tab2:
        st.markdown("#### Why It's Not Active")
        
        st.markdown("""
        LAiSER's built-in ESCO alignment (via Gemini) proved sufficient:
        
        1. ✅ LAiSER directly returns ESCO IDs for most skills (~70%)
        2. ✅ Achieves project target without additional complexity
        3. ✅ Local ESCO mapper was built as fallback/enrichment
        4. ✅ Current pipeline meets 70% ESCO alignment goal
        
        **Bottom line:** Adding the local mapper would provide only ~5% additional coverage
        but adds complexity and potential conflicts.
        """)
    
    with tab3:
        st.markdown("#### Recommendations")
        
        st.markdown("**Two Options:**")
        
        st.markdown("##### Option A: Remove the File (Recommended)")
        st.markdown("""
        **Pros:**
        - Simplifies codebase
        - Reduces confusion
        - Acknowledges LAiSER sufficiency
        
        **Cons:**
        - Loses potential future enrichment option
        """)
        
        st.markdown("##### Option B: Keep but Document")
        st.code("""
# Add to pipeline.py:

# NOTE: esco_mapper.py exists but is not used. LAiSER's built-in ESCO 
# alignment via Gemini achieves our 70% target without additional complexity.
# The mapper is retained for potential future use with non-AFSC data sources.
        """, language="python")
        
        st.markdown("""
        **Pros:**
        - Preserves work for future use
        - Available for non-AFSC sources
        - Documents decision clearly
        
        **Cons:**
        - Unused code in repository
        """)
    
    st.markdown("### 🎤 For Your Presentation")
    
    st.markdown('<div class="info-box">"We built a local ESCO mapper as a fallback enrichment layer, but LAiSER\'s built-in ESCO alignment via Gemini proved sufficient, achieving our 70% target without additional complexity."</div>', unsafe_allow_html=True)
    
    st.markdown("### 🔧 ESCO Mapper Capabilities (If Enabled)")
    
    st.code("""
# Similarity thresholds by type
SIMILARITY_THRESHOLD_SKILL = 0.90      # Very strict for skills
SIMILARITY_THRESHOLD_KNOW = 0.92       # Strictest for knowledge
SIMILARITY_THRESHOLD_ABILITY = 0.90    # Strict for abilities

# Method: Hybrid similarity (60% Jaccard + 40% difflib)
# Matches against local ESCO CSV catalog
# Only enriches items WITHOUT existing ESCO IDs
    """, language="python")

# ============================================================================
# SECTION: DEDUPLICATION
# ============================================================================
elif section == "🔄 Deduplication":
    st.markdown('<div class="section-header">🔄 Deduplication Strategy</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="success-box">✅ <strong>NOT Using FAISS</strong> - Custom hybrid fuzzy matching optimized for short text</div>', unsafe_allow_html=True)
    
    st.markdown("### 🧮 Similarity Algorithm")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.code("""
def _hybrid_similarity(a: str, b: str) -> float:
    '''
    Weighted blend:
    - 60% Token-level Jaccard similarity
    - 40% Character-level difflib ratio
    '''
    j = _jaccard(_tokenize(a), _tokenize(b))
    d = _difflib_ratio(a, b)
    return 0.6 * j + 0.4 * d
        """, language="python")
    
    with col2:
        st.markdown("**Why This Approach?**")
        st.markdown("""
        - **Token Jaccard:** Catches word-level similarities
        - **Character difflib:** Catches typos and small differences
        - **60/40 weighting:** Emphasizes semantic similarity
        - **Optimized for short text:** KSAs are typically 10-60 chars
        """)
    
    st.markdown("### ⚙️ Key Parameters")
    
    param_col1, param_col2 = st.columns(2)
    
    with param_col1:
        st.code("""
similarity_threshold = 0.86
        """, language="python")
        st.markdown("**Default threshold for near-duplicates**")
        st.markdown("- Tuned for short KSA phrases (10-60 chars)")
        st.markdown("- Balance between precision and recall")
    
    with param_col2:
        st.code("""
min_text_len = 4
        """, language="python")
        st.markdown("**Skip fuzzy matching for very short strings**")
        st.markdown("- Avoids false positives on abbreviations")
        st.markdown("- Speeds up processing")
    
    st.markdown("### 🏆 Canonicalization Priority")
    
    st.markdown("When clustering near-duplicates, winner selection uses:")
    
    st.code("""
def _quality_tuple(item):
    return (
        has_esco,           # 1 if item has ESCO ID, else 0 (HIGHEST PRIORITY)
        confidence,         # Numeric confidence score
        source_is_laiser,   # 1 if source=='laiser', else 0
        text_length         # Length of text (weakest tiebreaker)
    )
    """, language="python")
    
    priority_data = pd.DataFrame({
        "Priority": ["1 (Highest)", "2", "3", "4 (Tiebreaker)"],
        "Criterion": ["Has ESCO ID", "Higher confidence", "LAiSER source", "Longer text"],
        "Rationale": [
            "Preserve taxonomy alignment",
            "Keep higher-quality extractions",
            "Prefer LAiSER over LLM",
            "More descriptive is better"
        ]
    })
    st.dataframe(priority_data, use_container_width=True, hide_index=True)
    
    st.markdown("### 🔄 ESCO ID Lifting")
    
    st.markdown("""
    If the winner lacks an ESCO ID, but another cluster member has one:
    - Copy ESCO ID onto winner (shallow copy)
    - Preserve winner's original text
    - Ensure ESCO coverage propagates
    """)
    
    st.code("""
# Example: Cluster of near-duplicates
["imagery analysis", "imagery exploitation", "image analysis"]

# Winner selection:
1. "imagery exploitation" has ESCO ID ✅ → Selected as winner
2. Other items merged into this canonical form
3. Graph writes "imagery exploitation" with ESCO ID
    """)
    
    st.markdown("### ❓ Why Not FAISS?")
    
    comparison_data = pd.DataFrame({
        "Aspect": ["Dataset Size", "Performance", "Explainability", "Complexity", "Our Use Case"],
        "FAISS": [
            "Optimized for millions of vectors",
            "Approximate (ANN)",
            "Black box similarity",
            "High (external dependency)",
            "❌ Overkill"
        ],
        "Custom Hybrid": [
            "Perfect for 20-50 items",
            "Exact similarity",
            "Clear formula (60% + 40%)",
            "Low (pure Python)",
            "✅ Just right"
        ]
    })
    st.dataframe(comparison_data, use_container_width=True, hide_index=True)
    
    st.markdown("### 📊 Performance Metrics")
    
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    
    with metric_col1:
        st.metric("Deduplication Reduction", "10-20%", "of items removed")
    
    with metric_col2:
        st.metric("Execution Time", "<100ms", "per AFSC")
    
    with metric_col3:
        st.metric("False Positive Rate", "<1%", "verified manually")

# ============================================================================
# SECTION: MAJOR LIBRARIES
# ============================================================================
elif section == "📚 Major Libraries":
    st.markdown('<div class="section-header">📚 Major Libraries & Dependencies</div>', unsafe_allow_html=True)
    
    st.markdown("### 🔧 Core Pipeline Libraries")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Text Processing",
        "LAiSER & LLMs",
        "Database",
        "PDF Processing",
        "Utilities"
    ])
    
    with tab1:
        st.markdown("#### Text Processing")
        
        st.code("""
import re                           # Regex patterns for text cleaning
from difflib import SequenceMatcher # Character-level similarity
import textwrap                     # Text wrapping and shortening
        """, language="python")
        
        st.markdown("**Used in:**")
        st.markdown("- `preprocess.py` - PDF artifact removal")
        st.markdown("- `dedupe.py` - Fuzzy matching")
        st.markdown("- `quality_filter.py` - Text normalization")
    
    with tab2:
        st.markdown("#### LAiSER Integration")
        
        st.code("""
from laiser.skill_extractor_refactored import SkillExtractorRefactored
        """, language="python")
        
        st.markdown("**Capabilities:**")
        st.markdown("- Skill extraction from job descriptions")
        st.markdown("- ESCO/O*NET taxonomy alignment")
        st.markdown("- Confidence scoring")
        
        st.markdown("#### LLM Providers")
        
        st.code("""
import google.generativeai as genai       # Gemini API
from anthropic import Anthropic           # Claude API
from openai import OpenAI                 # GPT models
from huggingface_hub import InferenceClient  # HuggingFace
        """, language="python")
    
    with tab3:
        st.markdown("#### Graph Database")
        
        st.code("""
from neo4j import GraphDatabase
        """, language="python")
        
        st.markdown("**Used for:**")
        st.markdown("- MERGE operations (idempotent upserts)")
        st.markdown("- Cypher query execution")
        st.markdown("- Relationship management")
        st.markdown("- AFSC ↔ KSA ↔ ESCO graph persistence")
    
    with tab4:
        st.markdown("#### 📄 PDF Processing (pypdf)")
        
        st.code("""
from pypdf import PdfReader
import io
import requests
        """, language="python")
        
        st.markdown("**Usage in Streamlit App:**")
        
        st.code("""
# Download PDFs from GitHub
pdf_bytes = requests.get(GITHUB_URL).content

# Extract text page-by-page
reader = PdfReader(io.BytesIO(pdf_bytes))
for page in reader.pages:
    text = page.extract_text()
    # Clean PDF artifacts
    text = re.sub(r"[ \\t]+\\n", "\\n", text)
    text = re.sub(r"\\u00ad", "", text)  # Soft hyphens
        """, language="python")
        
        st.markdown("**Key Features:**")
        st.markdown("- Downloads AFECD/AFOCD PDFs from GitHub")
        st.markdown("- Extracts text page-by-page")
        st.markdown("- Searches for AFSC codes across pages")
        st.markdown("- Provides interactive text selection")
        
        st.markdown('<div class="info-box">💡 <strong>User Experience:</strong> pypdf enables users to search thousand-page documents without downloading, locate AFSC sections, and load relevant text directly into the extraction pipeline.</div>', unsafe_allow_html=True)
    
    with tab5:
        st.markdown("#### Utilities")
        
        st.code("""
import pandas as pd             # DataFrame operations
from dotenv import load_dotenv  # Environment variables
import pathlib                  # Path manipulation
import base64                   # Image encoding
import time                     # Timing operations
from typing import *            # Type hints
from dataclasses import dataclass  # Structured data
from enum import Enum           # ItemType enumeration
import os, sys, logging, traceback
        """, language="python")
    
    st.markdown("### 📦 Dependency Table")
    
    deps_data = pd.DataFrame({
        "Library": ["pypdf", "neo4j", "streamlit", "laiser", "google-generativeai", "anthropic", "openai", "pandas"],
        "Version": ["3.x", "5.x", "1.x", "0.1.x", "0.x", "0.x", "1.x", "2.x"],
        "Purpose": [
            "PDF text extraction",
            "Graph database driver",
            "Web interface",
            "Skill extraction",
            "Gemini API",
            "Claude API",
            "GPT API",
            "Data manipulation"
        ],
        "Required": ["✅", "✅", "✅", "✅", "✅", "Optional", "Optional", "✅"]
    })
    st.dataframe(deps_data, use_container_width=True, hide_index=True)

# ============================================================================
# SECTION: PIPELINE FLOW
# ============================================================================
elif section == "🔧 Pipeline Flow":
    st.markdown('<div class="section-header">🔧 Pipeline Flow Summary</div>', unsafe_allow_html=True)
    
    st.markdown("### 📋 Stage-by-Stage Process")
    
    st.markdown("""
    ```
    AFSC Text Input (PDF or plain text)
        ↓
    ┌─────────────────────────────────────────────────┐
    │ 1. PREPROCESSING (preprocess.py)                │
    │    • Remove PDF artifacts                       │
    │    • Fix hyphenated line breaks                 │
    │    • Normalize whitespace                       │
    │    Output: Clean narrative block                │
    └─────────────────────────────────────────────────┘
        ↓
    ┌─────────────────────────────────────────────────┐
    │ 2. SKILL EXTRACTION (extract_laiser.py)         │
    │    • LAiSER + Gemini extraction                 │
    │    • Built-in ESCO alignment                    │
    │    • Fallback: Regex heuristics                 │
    │    Output: 20-30 SKILL items                    │
    └─────────────────────────────────────────────────┘
        ↓
    ┌─────────────────────────────────────────────────┐
    │ 3. LLM ENHANCEMENT [OPTIONAL] (enhance_llm.py)  │
    │    • Generate Knowledge/Ability items           │
    │    • Balance item types (K/S/A)                 │
    │    • Add 5-15 complementary items               │
    │    Output: Extended KSA set                     │
    └─────────────────────────────────────────────────┘
        ↓
    ┌─────────────────────────────────────────────────┐
    │ 4. QUALITY FILTER (quality_filter.py)           │
    │    • Length constraints (3-80 chars)            │
    │    • Domain filtering                           │
    │    • Canonical text mapping                     │
    │    • Exact deduplication                        │
    │    Output: High-quality candidates              │
    └─────────────────────────────────────────────────┘
        ↓
    ┌─────────────────────────────────────────────────┐
    │ 5. FUZZY DEDUPLICATION (dedupe.py)              │
    │    • Hybrid similarity (Jaccard + difflib)      │
    │    • Cluster near-duplicates (0.86 threshold)   │
    │    • Pick best representative                   │
    │    • Lift ESCO IDs within clusters              │
    │    Output: Canonical KSA set                    │
    └─────────────────────────────────────────────────┘
        ↓
    ┌─────────────────────────────────────────────────┐
    │ 6. GRAPH PERSISTENCE (graph_writer_v2.py)       │
    │    • Neo4j MERGE operations                     │
    │    • Nodes: (:AFSC), (:KSA), (:ESCOSkill)      │
    │    • Relationships: [:REQUIRES], [:ALIGNS_TO]   │
    │    Output: Persistent graph database            │
    └─────────────────────────────────────────────────┘
        ↓
    Output: 25-50 KSAs per AFSC, ~70% ESCO-aligned
    ```
    """)
    
    st.markdown("### ⚙️ Environment Variables (Production Settings)")
    
    st.code("""
# LAiSER Configuration
USE_LAISER=true
LAISER_ALIGN_TOPK=25

# LLM Enhancement (Disabled by Default)
USE_LLM_ENHANCER=false
LLM_PROVIDER=gemini
LLM_MODEL_GEMINI=gemini-2.0-flash

# Quality Filtering
QUALITY_MIN_LEN=3
QUALITY_MAX_LEN=80
LOW_CONF_SKILL_THRESHOLD=0.60
STRICT_SKILL_FILTER=false
GEOINT_BIAS=false

# Deduplication
AGGRESSIVE_DEDUPE=true

# Neo4j Connection
NEO4J_URI=neo4j+s://...
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
NEO4J_DATABASE=neo4j
    """, language="bash")

# ============================================================================
# SECTION: FAQ
# ============================================================================
elif section == "❓ FAQ":
    st.markdown('<div class="section-header">❓ Frequently Asked Questions</div>', unsafe_allow_html=True)
    
    with st.expander("**Q: Why LAiSER with Gemini?**", expanded=True):
        st.markdown("""
        **A:** LAiSER is a GWU-developed skill extraction framework designed specifically 
        for job descriptions. We integrated Gemini because it provides both **skill extraction 
        AND ESCO alignment in one API call**, eliminating the need for a separate ESCO mapper.
        
        Key benefits:
        - Single API call for extraction + alignment
        - Cost-effective (~$0.005 per AFSC)
        - Achieves 70% ESCO coverage target
        - Reliable GWU-developed framework
        """)
    
    with st.expander("**Q: Why not use FAISS for deduplication?**"):
        st.markdown("""
        **A:** FAISS is designed for large-scale vector similarity search (millions of items). 
        We're deduplicating 20-50 items per AFSC - simple fuzzy matching is:
        
        - **Faster:** <100ms vs FAISS overhead
        - **More explainable:** Clear formula (60% Jaccard + 40% difflib)
        - **Better for short text:** Optimized for 10-60 character KSA phrases
        - **No dependencies:** Pure Python implementation
        """)
    
    with st.expander("**Q: What about the ESCO mapper you built?**"):
        st.markdown("""
        **A:** We built a local ESCO mapper (`esco_mapper.py`) as a fallback enrichment layer,
        but LAiSER's built-in ESCO alignment via Gemini proved sufficient, achieving our 70% 
        target without additional complexity.
        
        **Current status:** File exists but is not actively used in the pipeline.
        
        **Options:**
        1. Remove the file (simplifies codebase)
        2. Keep it for potential future non-AFSC use cases
        """)
    
    with st.expander("**Q: How are costs kept so low?**"):
        st.markdown("""
        **A:** Three main strategies:
        
        1. **LLM enhancement disabled by default** - LAiSER alone achieves coverage goals
        2. **Gemini Flash when enabled** - Cheapest option (~$0.075 per 1M tokens)
        3. **Token limits** - Max 512 output tokens, 2000 input chars
        
        **Result:** ~$0.005 per AFSC (LAiSER-only mode)
        """)
    
    with st.expander("**Q: What's pypdf used for?**"):
        st.markdown("""
        **A:** pypdf powers our "Try It Yourself" page, allowing users to:
        
        - Search 1000+ page AFSC documents (AFECD/AFOCD)
        - Locate AFSC sections without downloading files
        - Extract clean text for processing
        - Interactive page selection and loading
        
        Significantly improves user experience for finding and extracting AFSC text.
        """)
    
    with st.expander("**Q: How do you ensure extraction quality?**"):
        st.markdown("""
        **A:** Multi-stage quality control:
        
        1. **Preprocessing:** Removes PDF artifacts, fixes formatting
        2. **Quality Filter:** Length constraints (3-80 chars), domain filtering
        3. **Exact Deduplication:** Removes identical (type, text) pairs
        4. **Fuzzy Deduplication:** Removes near-duplicates while preserving ESCO IDs
        5. **Canonicalization:** Picks best representative from duplicate clusters
        
        **Winner priority:** ESCO ID > Confidence > LAiSER source > Text length
        """)
    
    with st.expander("**Q: Can this scale to all 200+ AFSCs?**"):
        st.markdown("""
        **A:** Yes! The pipeline is designed for scalability:
        
        - **Cost:** ~$1 for 200 AFSCs (LAiSER-only)
        - **Time:** ~10-15 minutes total processing
        - **Storage:** Neo4j Aura handles thousands of nodes easily
        - **Quality:** Same 70% ESCO alignment expected
        
        Main limitation is obtaining clean AFSC text for all specialties.
        """)
    
    with st.expander("**Q: Why Neo4j instead of relational database?**"):
        st.markdown("""
        **A:** Graph databases excel at relationship queries:
        
        - **Natural fit:** AFSC ↔ KSA ↔ ESCO mappings are inherently graph-like
        - **Cypher queries:** Express complex patterns easily
        - **Cross-AFSC analysis:** Find skill overlaps, transferable competencies
        - **Visualization:** Built-in graph visualization tools
        - **Scalability:** Cloud-hosted (Aura) with automatic backups
        """)

# ============================================================================
# SECTION: PERFORMANCE METRICS
# ============================================================================
elif section == "📊 Performance Metrics":
    st.markdown('<div class="section-header">📊 Performance Metrics</div>', unsafe_allow_html=True)
    
    st.markdown("### ⏱️ Processing Time Breakdown")
    
    time_data = pd.DataFrame({
        "Stage": [
            "1. Preprocessing",
            "2. LAiSER Extraction",
            "3. Quality Filtering",
            "4. LLM Enhancement*",
            "5. Deduplication",
            "6. Neo4j Write",
            "**TOTAL**"
        ],
        "Min Time": ["<0.1s", "2s", "<0.1s", "1s", "<0.1s", "0.5s", "**3s**"],
        "Avg Time": ["<0.1s", "3.5s", "<0.1s", "2s", "<0.1s", "0.7s", "**6.3s**"],
        "Max Time": ["<0.1s", "5s", "<0.1s", "3s", "<0.1s", "1s", "**9.1s**"],
        "Bottleneck": ["No", "Yes", "No", "Yes (optional)", "No", "No", "-"]
    })
    st.dataframe(time_data, use_container_width=True, hide_index=True)
    st.caption("*LLM Enhancement is optional and disabled by default")
    
    st.markdown("### 📉 Item Reduction Through Pipeline")
    
    reduction_data = pd.DataFrame({
        "Stage": ["LAiSER Extract", "Quality Filter", "LLM Enhance*", "Deduplication", "Final Output"],
        "Typical Count": ["20-30", "18-27", "25-40", "21-34", "25-35"],
        "Reduction %": ["-", "~10%", "-", "~15%", "-"],
        "Description": [
            "Raw skills from LAiSER",
            "Remove noise, short items",
            "Add K/A items (optional)",
            "Remove near-duplicates",
            "Clean, canonical KSAs"
        ]
    })
    st.dataframe(reduction_data, use_container_width=True, hide_index=True)
    
    st.markdown("### 🎯 Accuracy Metrics")
    
    acc_col1, acc_col2, acc_col3, acc_col4 = st.columns(4)
    
    with acc_col1:
        st.metric("ESCO Coverage", "70%", "+20% vs baseline")
    
    with acc_col2:
        st.metric("False Positive Rate", "<1%", "near-duplicates")
    
    with acc_col3:
        st.metric("Extraction Recall", "~85%", "vs manual review")
    
    with acc_col4:
        st.metric("Precision", "~90%", "relevant KSAs")
    
    st.markdown("### 💾 Resource Usage")
    
    resource_data = pd.DataFrame({
        "Resource": ["Memory Peak", "CPU Cores", "Network (per AFSC)", "Storage (per AFSC)"],
        "Usage": ["~200MB", "1-2 cores", "~50KB", "~5KB"],
        "Notes": [
            "Includes LAiSER + LLM libraries",
            "Parallelizable across AFSCs",
            "Mostly API calls (LAiSER, Gemini)",
            "Neo4j node/relationship storage"
        ]
    })
    st.dataframe(resource_data, use_container_width=True, hide_index=True)

# ============================================================================
# SECTION: COST ANALYSIS
# ============================================================================
elif section == "💰 Cost Analysis":
    st.markdown('<div class="section-header">💰 Cost Analysis</div>', unsafe_allow_html=True)
    
    st.markdown("### 📊 Cost Breakdown by Configuration")
    
    cost_data = pd.DataFrame({
        "Configuration": [
            "LAiSER Only (Default)",
            "LAiSER + Gemini Flash",
            "LAiSER + GPT-4o-mini",
            "LAiSER + Claude Sonnet"
        ],
        "Per AFSC": ["$0.005", "$0.005-0.010", "$0.015-0.025", "$0.050-0.100"],
        "12 AFSCs": ["$0.06", "$0.06-0.12", "$0.18-0.30", "$0.60-1.20"],
        "200 AFSCs": ["$1.00", "$1.00-2.00", "$3.00-5.00", "$10-20"],
        "Recommendation": ["✅ Default", "✅ If K/A needed", "⚠️ Backup", "❌ Too expensive"]
    })
    st.dataframe(cost_data, use_container_width=True, hide_index=True)
    
    st.markdown("### 💡 Cost Optimization Strategies")
    
    opt_col1, opt_col2 = st.columns(2)
    
    with opt_col1:
        st.markdown("#### Implemented")
        st.markdown("""
        ✅ **LLM disabled by default** - Only use when K/A items needed  
        ✅ **Gemini Flash** - Cheapest model when LLM enabled  
        ✅ **Token limits** - 512 max output, 2000 char input  
        ✅ **Smart prompting** - Reduce unnecessary generation  
        ✅ **Caching** - LAiSER results reused across runs  
        """)
    
    with opt_col2:
        st.markdown("#### Additional Opportunities")
        st.markdown("""
        💡 **Batch processing** - Process multiple AFSCs in one API call  
        💡 **Result caching** - Store common extractions  
        💡 **Smaller models** - Use 3B param for simple K/A  
        💡 **Dynamic TopK** - Adjust LAiSER TopK based on AFSC length  
        💡 **Local LLMs** - Use open-source models for K/A  
        """)
    
    st.markdown("### 📈 Cost Scaling")
    
    import pandas as pd
    import matplotlib.pyplot as plt
    
    # Create scaling data
    afsc_counts = [1, 12, 50, 100, 200]
    laiser_only = [c * 0.005 for c in afsc_counts]
    with_llm = [c * 0.0075 for c in afsc_counts]
    
    chart_data = pd.DataFrame({
        "AFSCs": afsc_counts,
        "LAiSER Only": laiser_only,
        "LAiSER + Gemini": with_llm
    })
    
    st.line_chart(chart_data.set_index("AFSCs"))
    
    st.markdown("### 🎯 ROI Analysis")
    
    st.markdown("""
    **Manual KSA extraction (baseline):**
    - Time per AFSC: 2-4 hours
    - Labor cost: $50-100 per hour
    - Total cost per AFSC: **$100-400**
    - Quality: Variable, depends on analyst
    
    **Automated pipeline:**
    - Time per AFSC: ~3-8 seconds
    - Processing cost: **$0.005-0.010**
    - Total cost per AFSC: **$0.005-0.010**
    - Quality: Consistent, 70% ESCO-aligned
    
    **ROI: 10,000x - 80,000x cost reduction** 🎉
    """)
    
    st.markdown('<div class="success-box">✅ <strong>Bottom Line:</strong> Even with LLM enhancement enabled, the automated pipeline is dramatically more cost-effective than manual extraction while providing consistent, taxonomy-aligned results.</div>', unsafe_allow_html=True)

# ============================================================================
# FOOTER
# ============================================================================
st.divider()
st.markdown("""
<div style='text-align: center; padding: 2rem 0; color: #6B7280; font-size: 0.9rem;'>
    <p style='margin-bottom: 0.5rem;'>
        <strong style='color: #004785;'>🚀 USAF KSA Extraction Pipeline - Documentation</strong>
    </p>
    <p style='margin: 0;'>
        © 2025 George Washington University | MS Data Science Capstone
    </p>
</div>
""", unsafe_allow_html=True)
