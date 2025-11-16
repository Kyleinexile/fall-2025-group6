import streamlit as st
import os
import base64
from pathlib import Path
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# HELPER FUNCTION - Convert image to base64
# ============================================================================
def get_base64_image(image_path):
    """Convert an image file to base64 string for embedding in CSS"""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception as e:
        st.warning(f"Could not load background image: {e}")
        return None

# ============================================================================
# LOAD BACKGROUND IMAGE
# ============================================================================
current_dir = Path(__file__).parent
bg_image_path = current_dir / "assets" / "AFDOGGO.jpg"
bg_image_base64 = get_base64_image(bg_image_path)

# Debug: Uncomment to verify image loading
# st.sidebar.caption(f"🖼️ Background loaded: {bool(bg_image_base64)}")

st.set_page_config(
    page_title="USAF KSA Explorer",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CUSTOM CSS - Transparent overlay + full-page background
# ============================================================================
background_css = ""
if bg_image_base64:
    background_css = f"""
    [data-testid="stAppViewContainer"] {{
        /* Combine overlay + image */
        background:
            linear-gradient(rgba(255,255,255,0.90), rgba(255,255,255,0.90)),
            url('data:image/jpeg;base64,{bg_image_base64}');
        background-size: cover;
        background-repeat: no-repeat;
        background-attachment: fixed;
        background-position: center 65%; /* horizontal center, vertical offset (positive = down) */
    }}

    [data-testid="stHeader"] {{
        background: transparent !important;
    }}

    [data-testid="stSidebar"] {{
        background: rgba(255,255,255,0.92) !important;
        backdrop-filter: blur(2px);
    }}

    .main .block-container {{
        background: transparent !important;
    }}
    """

st.markdown(f"""
<style>
    /* Import Professional Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    {background_css}
    
    /* Global Font & Typography */
    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
        font-size: 15px;
    }}
    
    /* Air Force Blue Theme - Aggressive Button Styling */
    .stButton>button[kind="primary"],
    button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {{
        background-color: #00539B !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.75rem 1.5rem !important;
        font-size: 16px !important;
        transition: all 0.3s ease !important;
        border-radius: 8px !important;
    }}
    .stButton>button[kind="primary"]:hover {{
        background-color: #003D7A !important;
        color: #FFFFFF !important;
        transform: translateY(-3px);
        box-shadow: 0 6px 20px rgba(0, 83, 155, 0.4) !important;
    }}
    .stButton>button[kind="primary"] p,
    .stButton>button[kind="primary"] span,
    .stButton>button[kind="primary"] div {{
        color: #FFFFFF !important;
    }}
    
    .stButton>button[kind="secondary"],
    button[kind="secondary"],
    .stButton > button[data-testid="baseButton-secondary"] {{
        background-color: #FFFFFF !important;
        border: 2px solid #00539B !important;
        color: #00539B !important;
        font-weight: 600 !important;
        padding: 0.75rem 1.5rem !important;
        font-size: 16px !important;
        transition: all 0.3s ease !important;
        border-radius: 8px !important;
    }}
    .stButton>button[kind="secondary"]:hover {{
        background-color: #00539B !important;
        color: #FFFFFF !important;
        border: 2px solid #00539B !important;
        transform: translateY(-3px);
        box-shadow: 0 6px 20px rgba(0, 83, 155, 0.3) !important;
    }}
    .stButton>button[kind="secondary"] p,
    .stButton>button[kind="secondary"] span,
    .stButton>button[kind="secondary"] div {{
        color: inherit !important;
    }}
    
    /* Metrics Styling - Bigger and Bolder */
    [data-testid="stMetricValue"] {{
        font-size: 42px;
        font-weight: 800;
        color: #00539B;
    }}
    [data-testid="stMetricLabel"] {{
        font-size: 14px;
        font-weight: 600;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    
    /* Headers */
    h1 {{
        color: #1F2937;
        font-weight: 800;
        letter-spacing: -0.5px;
    }}
    h2 {{
        color: #374151;
        font-weight: 700;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }}
    h3 {{
        color: #1F2937;
        font-weight: 600;
    }}
    
    /* Thicker Dividers */
    hr {{
        border: none;
        border-top: 3px solid #E5E7EB;
        margin: 3rem 0;
    }}
    
    /* Better Typography */
    p {{
        line-height: 1.6;
        color: #4B5563;
    }}
    
    /* Status Badge */
    .status-badge {{
        display: inline-block;
        padding: 6px 16px;
        border-radius: 16px;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.3px;
        margin-right: 8px;
        margin-bottom: 8px;
    }}
    .status-success {{
        background-color: #D1FAE5;
        color: #065F46;
    }}
    .status-warning {{
        background-color: #FEF3C7;
        color: #92400E;
    }}
    .status-error {{
        background-color: #FEE2E2;
        color: #991B1B;
    }}
    
    /* Splash Screen Animation */
    @keyframes fadeInUp {{
        from {{
            opacity: 0;
            transform: translateY(30px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}
    .splash-container {{
        animation: fadeInUp 0.8s ease-out;
    }}
    .splash-image {{
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
        margin-bottom: 2rem;
    }}
    
    /* Pipeline Step Boxes */
    .pipeline-step {{
        background: white;
        border: 3px solid #00539B;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        min-height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        transition: all 0.3s ease;
    }}
    .pipeline-step:hover {{
        transform: translateY(-4px);
        box-shadow: 0 8px 24px rgba(0, 83, 155, 0.2);
    }}
</style>
""", unsafe_allow_html=True)

# ============================================================================
# SPLASH SCREEN
# ============================================================================
if 'entered' not in st.session_state:
    st.session_state.entered = False

if not st.session_state.entered:
    st.markdown("<div class='splash-container'>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Air Force Image
        current_dir = Path(__file__).parent
        image_path = current_dir / "assets" / "air force.jpg"
        
        if image_path.exists():
            st.markdown("<div class='splash-image'>", unsafe_allow_html=True)
            st.image(str(image_path), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        
        # Title
        st.markdown("""
        <h1 style='text-align: center; font-size: 3.2rem; font-weight: 800; 
                   color: #00539B; margin-bottom: 2rem; line-height: 1.2;'>
            Military Knowledge, Skills and Abilities (KSA) Pipeline
        </h1>
        """, unsafe_allow_html=True)
        
        # Enter Button
        if st.button("🚀 Enter Application", type="primary", use_container_width=True):
            st.session_state.entered = True
            st.rerun()
        
        # ============================================================================
        # VIDEO SECTION (Added below Enter button, above icons)
        # ============================================================================
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("""
        <div style='text-align: center;'>
            <h3 style='color: #00539B; font-size: 1.4rem; margin-bottom: 1rem; font-weight: 700;'>
                📹 Watch Our 1-Minute Demo
            </h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Video with centered layout
        video_url = "https://raw.githubusercontent.com/Kyleinexile/fall-2025-group6/main/presentation/AFSC_KSA_Capstone_Promo.mp4"
        st.video(video_url)
        
        st.markdown("""
        <div style='text-align: center; color: #6B7280; font-size: 0.95rem; margin-top: 0.5rem; margin-bottom: 1.5rem;'>
            Complete pipeline overview: from AFSC documents to structured KSAs
        </div>
        """, unsafe_allow_html=True)
        
        # ============================================================================
        
        st.markdown("<hr style='margin: 2.5rem 0; border-color: #E5E7EB;'>", unsafe_allow_html=True)
        
        # Key Features
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            st.markdown("""
            <div style='text-align: center; padding: 24px;'>
                <div style='font-size: 3.5rem; margin-bottom: 1rem;'>🤖</div>
                <h3 style='color: #00539B; font-size: 1.3rem; margin-bottom: 0.75rem; font-weight: 700;'>AI-Powered</h3>
                <p style='color: #6B7280; font-size: 1rem; line-height: 1.5;'>GWU's LAiSER + LLM extraction</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col_b:
            st.markdown("""
            <div style='text-align: center; padding: 24px;'>
                <div style='font-size: 3.5rem; margin-bottom: 1rem;'>🔍</div>
                <h3 style='color: #00539B; font-size: 1.3rem; margin-bottom: 0.75rem; font-weight: 700;'>Comprehensive</h3>
                <p style='color: #6B7280; font-size: 1rem; line-height: 1.5;'>Knowledge, Skills, Abilities</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col_c:
            st.markdown("""
            <div style='text-align: center; padding: 24px;'>
                <div style='font-size: 3.5rem; margin-bottom: 1rem;'>🌐</div>
                <h3 style='color: #00539B; font-size: 1.3rem; margin-bottom: 0.75rem; font-weight: 700;'>Interactive</h3>
                <p style='color: #6B7280; font-size: 1rem; line-height: 1.5;'>Real-time exploration</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<hr style='margin: 2.5rem 0; border-color: #E5E7EB;'>", unsafe_allow_html=True)
        
        # Project Description
        st.markdown("""
        <div style='text-align: center; font-size: 1.15em; color: #4B5563; margin-bottom: 2.5rem;'>
            <p style='margin-bottom: 0.75rem; font-size: 1.1em;'>Automated extraction and analysis of Air Force Specialty Code knowledge requirements</p>
            <p style='font-weight: 600; color: #00539B; margin-bottom: 0.75rem; font-size: 1.05em;'>MS Data Science Capstone Project</p>
            <p style='color: #6B7280;'>George Washington University | 2025</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ============================================================================
# MAIN APPLICATION
# ============================================================================

# Cached functions for status/metrics
@st.cache_data(ttl=60)
def get_env_status():
    return {
        "neo4j": bool(os.getenv("NEO4J_URI")),
        "gemini": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
    }

@st.cache_data(ttl=60)
def get_database_metrics():
    try:
        NEO4J_URI = os.getenv("NEO4J_URI", "")
        NEO4J_USER = os.getenv("NEO4J_USER", "")
        NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
        NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
        
        if all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            with driver.session(database=NEO4J_DATABASE) as session:
                result = session.run("""
                    MATCH (a:AFSC)
                    OPTIONAL MATCH (a)-[:REQUIRES]->(k:KSA)
                    RETURN 
                        count(DISTINCT a) as afscs,
                        count(DISTINCT k) as total_ksas,
                        count(DISTINCT CASE WHEN k.type = 'knowledge' THEN k END) as knowledge,
                        count(DISTINCT CASE WHEN k.type = 'skill' THEN k END) as skills,
                        count(DISTINCT CASE WHEN k.type = 'ability' THEN k END) as abilities
                """).single()
            driver.close()
            
            return {
                "afscs": result["afscs"] or 0,
                "total_ksas": result["total_ksas"] or 0,
                "knowledge": result["knowledge"] or 0,
                "skills": result["skills"] or 0,
                "abilities": result["abilities"] or 0
            }
    except Exception:
        pass
    
    return {
        "afscs": 0,
        "total_ksas": 0,
        "knowledge": 0,
        "skills": 0,
        "abilities": 0
    }

# Fetch data once
status = get_env_status()
metrics = get_database_metrics()

# ============================================================================
# SIDEBAR - Connection Status at Bottom
# ============================================================================
with st.sidebar:
    # Add spacer to push to bottom
    st.markdown("<br>" * 20, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 📊 System Status")
    
    # Connection Status
    st.markdown("**Connections:**")
    
    # Neo4j
    if status["neo4j"]:
        st.markdown("✅ Neo4j Database")
    else:
        st.markdown("❌ Neo4j Database")
    
    # Gemini
    if status["gemini"]:
        st.markdown("✅ Gemini API")
    else:
        st.markdown("⚠️ Gemini API")
    
    # OpenAI
    if status["openai"]:
        st.markdown("✅ OpenAI API")
    else:
        st.markdown("⚠️ OpenAI API")
    
    # Anthropic
    if status["anthropic"]:
        st.markdown("✅ Anthropic API")
    else:
        st.markdown("⚠️ Anthropic API")

# ============================================================================
# COMPACT BANNER - At Very Top (Metrics Only)
# ============================================================================
st.markdown(f"""
<div style='background: linear-gradient(135deg, #00539B 0%, #003D7A 100%); 
            padding: 12px 24px; border-radius: 8px; margin-bottom: 2rem;
            box-shadow: 0 2px 8px rgba(0, 83, 155, 0.15);'>
    <div style='display: flex; justify-content: space-around; align-items: center; flex-wrap: wrap; gap: 16px;'>
        <div style='display: flex; align-items: baseline; gap: 8px;'>
            <span style='color: white; font-size: 1.1rem; font-weight: 600; opacity: 0.95; text-transform: uppercase; letter-spacing: 0.5px;'>AFSCs:</span>
            <span style='color: white; font-size: 1.1rem; font-weight: 800;'>{metrics["afscs"]}</span>
        </div>
        <div style='display: flex; align-items: baseline; gap: 8px;'>
            <span style='color: white; font-size: 1.1rem; font-weight: 600; opacity: 0.95; text-transform: uppercase; letter-spacing: 0.5px;'>Total KSAs:</span>
            <span style='color: white; font-size: 1.1rem; font-weight: 800;'>{metrics["total_ksas"]}</span>
        </div>
        <div style='display: flex; align-items: baseline; gap: 8px;'>
            <span style='color: white; font-size: 1.1rem; font-weight: 600; opacity: 0.95; text-transform: uppercase; letter-spacing: 0.5px;'>Knowledge:</span>
            <span style='color: white; font-size: 1.1rem; font-weight: 800;'>{metrics["knowledge"]}</span>
        </div>
        <div style='display: flex; align-items: baseline; gap: 8px;'>
            <span style='color: white; font-size: 1.1rem; font-weight: 600; opacity: 0.95; text-transform: uppercase; letter-spacing: 0.5px;'>Skills:</span>
            <span style='color: white; font-size: 1.1rem; font-weight: 800;'>{metrics["skills"]}</span>
        </div>
        <div style='display: flex; align-items: baseline; gap: 8px;'>
            <span style='color: white; font-size: 1.1rem; font-weight: 600; opacity: 0.95; text-transform: uppercase; letter-spacing: 0.5px;'>Abilities:</span>
            <span style='color: white; font-size: 1.1rem; font-weight: 800;'>{metrics["abilities"]}</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<h1 style='font-size: 2.75rem; margin-bottom: 0.5rem; font-weight: 800;'>
    ✈️ USAF KSA Extraction Pipeline
</h1>
""", unsafe_allow_html=True)

st.markdown("""
<p style='font-size: 1.15rem; color: #6B7280; margin-bottom: 0.5rem; line-height: 1.5;'>
    Map Air Force Specialty Codes to transferable <strong>Knowledge, Skills, and Abilities</strong> for analysis and career planning.
</p>
""", unsafe_allow_html=True)

st.caption("Capstone Project | MS Data Science | George Washington University | 2025")

# First-time helper
if "hide_getting_started" not in st.session_state:
    st.session_state.hide_getting_started = False

if not st.session_state.hide_getting_started:
    with st.container():
        st.info(
            "**First time here?** Start with **Explore KSAs** to browse existing data. "
            "Want to test extraction? Use **Try It Yourself** with your own API key. "
            "Admins can process documents in **Admin Tools**.",
            icon="🧭"
        )
        if st.checkbox("Don't show this again", key="hide_gs_checkbox"):
            st.session_state.hide_getting_started = True
            st.rerun()

st.markdown("<hr style='border: none; border-top: 3px solid #E5E7EB; margin: 3rem 0;'>", unsafe_allow_html=True)

# ============================================================================
# WHAT WOULD YOU LIKE TO DO?
# ============================================================================
st.markdown("## 🚀 What would you like to do?")
st.markdown("<p style='color: #6B7280; font-size: 1.05rem; margin-bottom: 2rem;'>Choose your workflow below</p>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3, gap="large")

with col1:
    with st.container():
        st.markdown("### 🔍 Explore KSAs")
        st.markdown("Browse AFSCs, view extracted Knowledge, Skills, and Abilities, and find overlaps between specialties.")
        st.caption("→ Read-only insights & cross-AFSC analysis")
        if st.button("Open Explore KSAs →", use_container_width=True, type="primary", key="explore"):
            st.switch_page("pages/03_Explore_KSAs.py")

with col2:
    with st.container():
        st.markdown("### 🔑 Try It Yourself")
        st.markdown("Paste AFSC text and generate Knowledge/Ability items using your own API key for testing.")
        st.caption("→ Sandbox with your own API key")
        if st.button("Open Try It Yourself →", use_container_width=True, type="secondary", key="byo"):
            st.switch_page("pages/02_Try_It_Yourself.py")

with col3:
    with st.container():
        st.markdown("### ⚙️ Admin Tools")
        st.markdown("Process PDFs/Markdown, run extraction pipeline, and manage database content.")
        st.caption("→ Power tools for data management")
        if st.button("Open Admin Tools →", use_container_width=True, type="secondary", key="admin"):
            st.switch_page("pages/04_Admin_Tools.py")

st.markdown("<hr style='border: none; border-top: 3px solid #E5E7EB; margin: 3rem 0;'>", unsafe_allow_html=True)

# ============================================================================
# HOW IT WORKS - 6 Steps with Boxes
# ============================================================================
st.markdown("## 🔄 How it works")

# 6-step pipeline with boxes
col1, arr1, col2, arr2, col3, arr3, col4, arr4, col5, arr5, col6 = st.columns([1, 0.15, 1, 0.15, 1, 0.15, 1, 0.15, 1, 0.15, 1])

with col1:
    st.markdown("""
    <div class='pipeline-step'>
        <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>📄</div>
        <h4 style='color: #00539B; margin-bottom: 0.5rem; font-weight: 700;'>1. Ingest</h4>
        <p style='color: #6B7280; font-size: 0.9rem; margin: 0;'>Load AFOCD/AFECD documents</p>
    </div>
    """, unsafe_allow_html=True)

with arr1:
    st.markdown("<h2 style='text-align: center; color: #00539B; margin-top: 60px;'>→</h2>", unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class='pipeline-step'>
        <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>🧹</div>
        <h4 style='color: #00539B; margin-bottom: 0.5rem; font-weight: 700;'>2. Preprocess</h4>
        <p style='color: #6B7280; font-size: 0.9rem; margin: 0;'>Clean & normalize text</p>
    </div>
    """, unsafe_allow_html=True)

with arr2:
    st.markdown("<h2 style='text-align: center; color: #00539B; margin-top: 60px;'>→</h2>", unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class='pipeline-step'>
        <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>🤖</div>
        <h4 style='color: #00539B; margin-bottom: 0.5rem; font-weight: 700;'>3. Extract</h4>
        <p style='color: #6B7280; font-size: 0.9rem; margin: 0;'>LAiSER skill extraction</p>
    </div>
    """, unsafe_allow_html=True)

with arr3:
    st.markdown("<h2 style='text-align: center; color: #00539B; margin-top: 60px;'>→</h2>", unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div class='pipeline-step'>
        <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>✨</div>
        <h4 style='color: #00539B; margin-bottom: 0.5rem; font-weight: 700;'>4. Enhance</h4>
        <p style='color: #6B7280; font-size: 0.9rem; margin: 0;'>LLM K/A generation</p>
    </div>
    """, unsafe_allow_html=True)

with arr4:
    st.markdown("<h2 style='text-align: center; color: #00539B; margin-top: 60px;'>→</h2>", unsafe_allow_html=True)

with col5:
    st.markdown("""
    <div class='pipeline-step'>
        <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>💾</div>
        <h4 style='color: #00539B; margin-bottom: 0.5rem; font-weight: 700;'>5. Store</h4>
        <p style='color: #6B7280; font-size: 0.9rem; margin: 0;'>Neo4j graph database</p>
    </div>
    """, unsafe_allow_html=True)

with arr5:
    st.markdown("<h2 style='text-align: center; color: #00539B; margin-top: 60px;'>→</h2>", unsafe_allow_html=True)

with col6:
    st.markdown("""
    <div class='pipeline-step'>
        <div style='font-size: 2.5rem; margin-bottom: 0.5rem;'>🌐</div>
        <h4 style='color: #00539B; margin-bottom: 0.5rem; font-weight: 700;'>6. Explore</h4>
        <p style='color: #6B7280; font-size: 0.9rem; margin: 0;'>Interactive web interface</p>
    </div>
    """, unsafe_allow_html=True)

with st.expander("See detailed pipeline steps"):
    st.markdown("""
    ### Detailed Process
    
    The AFSC → KSA Pipeline automates the extraction and organization of Knowledge, Skills, and Abilities (KSAs) from Air Force Specialty Code (AFSC) descriptions. It enables skill-mapping, workforce analytics, and cross-AFSC capability visualization within a Neo4j graph.
    
    **0. Ingest (Document Loading)**  
    AFSC source documents (AFOCD / AFECD PDFs or JSONL) are parsed and indexed. Each AFSC entry is extracted with section headers (summary, duties, qualifications) and stored as normalized JSON records for downstream use.
    
    **1. Preprocessing**  
    Removes headers, page numbers, and formatting artifacts. Fixes hyphenation / line-break issues and standardizes encoding for consistent text analysis.
    
    **2. Extraction (Skills – LAiSER Engine)**  
    The LAiSER extractor identifies core Skill items via taxonomy-based matching against professional datasets. Each item is tagged with confidence (0–1). Fallback regex logic provides coverage in offline or low-confidence cases.
    
    **3. Enhancement (Knowledge & Ability – LLM Stage)**  
    Large Language Models (Gemini 1.5 Flash primary, Claude Sonnet 4 fallback) generate complementary Knowledge and Ability statements to fill coverage gaps. If no API key is provided, heuristics generate minimal items. Outputs are filtered for duplicates and format compliance.
    
    **4. Quality Filtering**  
    Applies domain-specific rules and confidence thresholds (items below 0.50 removed). Performs exact-match deduplication (type + text) and drops generic or low-signal entries.
    
    **5. Deduplication & Canonicalization**  
    Performs fuzzy merge of near-duplicates using cosine-similarity (TF-IDF vectors) and Levenshtein distance checks. Keeps the highest-confidence or ESCO-linked instance to maintain clarity and consistency.
    
    **6. ESCO Mapping**  
    Aligns remaining items to the European Skills, Competences, Qualifications and Occupations (ESCO) taxonomy. Enables standardized cross-AFSC / civilian comparisons and labor-market interoperability.
    
    **7. Graph Persistence**  
    Writes results to a Neo4j Aura graph using `MERGE` operations for idempotency (no duplicate nodes or edges). Establishes relationships between (AFSC) and (Item) nodes for querying and overlap analysis.
    
    **8. Audit & Telemetry**  
    Logs counts, timings, and errors for each stage. All outputs are timestamped and versioned, providing full traceability from source text to graph node.
    """)

st.markdown("<hr style='border: none; border-top: 3px solid #E5E7EB; margin: 3rem 0;'>", unsafe_allow_html=True)

# ============================================================================
# LEARN MORE
# ============================================================================
with st.expander("📖 Learn More (About • KSA Definitions • Tech Stack • Configuration)"):
    st.markdown("### About This Project")
    st.write(
        "This is a GWU Data Science Capstone project that maps **Air Force Specialty Code (AFSC)** "
        "descriptions to transferable **Knowledge, Skills, and Abilities (KSAs)** for career analysis, "
        "planning, and transition insights."
    )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("### KSA Definitions")
    col_k, col_s, col_a = st.columns(3)
    
    with col_k:
        st.markdown("**📖 Knowledge**")
        st.markdown("A body of facts, concepts, and procedures necessary to perform tasks effectively.")
        st.caption("Example: Intelligence cycle fundamentals")
    
    with col_s:
        st.markdown("**🛠️ Skills**")
        st.markdown("Learned capacities to perform specific tasks or activities.")
        st.caption("Example: Perform intelligence analysis")
    
    with col_a:
        st.markdown("**💪 Abilities**")
        st.markdown("Enduring capabilities that enable performance across contexts.")
        st.caption("Example: Synthesize multi-source data")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("### Tech Stack (High Level)")
    col_t1, col_t2, col_t3 = st.columns(3)
    
    with col_t1:
        st.markdown("**🤖 AI/ML**")
        st.markdown("""
        - LAiSER (GWU) - Skill extraction
        - Gemini 1.5 Flash - Primary LLM
        - Claude Sonnet 4 - Fallback LLM
        - OpenAI GPT-4 - Optional
        """)
    
    with col_t2:
        st.markdown("**💾 Data**")
        st.markdown("""
        - Neo4j Aura - Graph database
        - ESCO Taxonomy - EU skills framework
        - LAiSER Taxonomy - Extended codes
        - Python 3.11 - Core language
        """)
    
    with col_t3:
        st.markdown("**🌐 Interface**")
        st.markdown("""
        - Streamlit - Multi-page web app
        - GitHub - Version control
        - Streamlit Cloud - Hosting
        - Custom CSS - Air Force theme
        """)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("### System Configuration (Quick Check)")
    col_cfg1, col_cfg2 = st.columns(2)
    
    with col_cfg1:
        st.markdown("**Environment Status**")
        st.code(f"""
Neo4j: {'✅ Connected' if status['neo4j'] else '❌ Not configured'}
Gemini API: {'✅ Set' if status['gemini'] else '⚠️ Missing'}
OpenAI API: {'✅ Set' if status['openai'] else '⚠️ Missing'}
Anthropic API: {'✅ Set' if status['anthropic'] else '⚠️ Missing'}
        """)
    
    with col_cfg2:
        st.markdown("**Next Steps**")
        st.markdown("""
        - **Explore existing data** → Explore KSAs page
        - **Test extraction** → Try It Yourself page
        - **Process documents** → Admin Tools page
        - **View documentation** → System Configuration expander
        """)

# Footer
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div style='text-align: center; padding: 2rem 0; color: #6B7280; font-size: 0.9rem;'>
    <p style='margin-bottom: 0.5rem;'>
        <strong style='color: #00539B;'>🚀 USAF KSA Extraction Pipeline</strong>
    </p>
    <p style='margin: 0;'>
        © 2025 George Washington University | MS Data Science Capstone
    </p>
</div>
""", unsafe_allow_html=True)
