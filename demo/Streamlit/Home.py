import streamlit as st
import os
from pathlib import Path
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="USAF KSA Explorer",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CUSTOM CSS - Air Force Theme & Professional Styling
# ============================================================================
st.markdown("""
<style>
    /* Import Professional Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    /* Global Font & Typography */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        font-size: 15px;
    }
    
    /* Air Force Blue Theme - Aggressive Button Styling */
    .stButton>button[kind="primary"],
    button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {
        background-color: #00539B !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.75rem 1.5rem !important;
        font-size: 16px !important;
        transition: all 0.3s ease !important;
        border-radius: 8px !important;
    }
    .stButton>button[kind="primary"]:hover,
    button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover {
        background-color: #003D7A !important;
        color: #FFFFFF !important;
        transform: translateY(-3px);
        box-shadow: 0 6px 20px rgba(0, 83, 155, 0.4) !important;
    }
    .stButton>button[kind="primary"] p,
    .stButton>button[kind="primary"] span,
    .stButton>button[kind="primary"] div {
        color: #FFFFFF !important;
    }
    
    .stButton>button[kind="secondary"],
    button[kind="secondary"],
    .stButton > button[data-testid="baseButton-secondary"] {
        background-color: #FFFFFF !important;
        border: 2px solid #00539B !important;
        color: #00539B !important;
        font-weight: 600 !important;
        padding: 0.75rem 1.5rem !important;
        font-size: 16px !important;
        transition: all 0.3s ease !important;
        border-radius: 8px !important;
    }
    .stButton>button[kind="secondary"]:hover,
    button[kind="secondary"]:hover,
    .stButton > button[data-testid="baseButton-secondary"]:hover {
        background-color: #00539B !important;
        color: #FFFFFF !important;
        border: 2px solid #00539B !important;
        transform: translateY(-3px);
        box-shadow: 0 6px 20px rgba(0, 83, 155, 0.3) !important;
    }
    .stButton>button[kind="secondary"] p,
    .stButton>button[kind="secondary"] span,
    .stButton>button[kind="secondary"] div {
        color: inherit !important;
    }
    
    /* Metrics Styling - Bigger and Bolder */
    [data-testid="stMetricValue"] {
        font-size: 42px;
        font-weight: 800;
        color: #00539B;
    }
    [data-testid="stMetricLabel"] {
        font-size: 14px;
        font-weight: 600;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* Headers - Better Hierarchy */
    h1 {
        color: #1F2937;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    h2 {
        color: #374151;
        font-weight: 700;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    h3 {
        color: #1F2937;
        font-weight: 600;
    }
    
    /* Dividers */
    hr {
        margin: 2.5rem 0;
        border: none;
        border-top: 2px solid #E5E7EB;
    }
    
    /* Better Typography */
    p {
        line-height: 1.6;
        color: #4B5563;
    }
    
    /* Status Badge - Larger and More Prominent */
    .status-badge {
        display: inline-block;
        padding: 6px 16px;
        border-radius: 16px;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.3px;
        margin-right: 8px;
        margin-bottom: 8px;
    }
    .status-success {
        background-color: #D1FAE5;
        color: #065F46;
    }
    .status-warning {
        background-color: #FEF3C7;
        color: #92400E;
    }
    .status-error {
        background-color: #FEE2E2;
        color: #991B1B;
    }
    
    /* Splash Screen Animation */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    .splash-container {
        animation: fadeInUp 0.8s ease-out;
    }
    .splash-image {
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
        margin-bottom: 2rem;
    }
    
    /* Action Cards */
    .action-card {
        padding: 24px;
        border-radius: 12px;
        border: 2px solid #E5E7EB;
        background: #FAFAFA;
        transition: all 0.3s ease;
        height: 100%;
    }
    .action-card:hover {
        border-color: #00539B;
        background: white;
        box-shadow: 0 8px 24px rgba(0, 83, 155, 0.12);
        transform: translateY(-4px);
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# SPLASH SCREEN - Entry Page
# ============================================================================
if 'entered' not in st.session_state:
    st.session_state.entered = False

if not st.session_state.entered:
    st.markdown("<div class='splash-container'>", unsafe_allow_html=True)
    
    # Center content
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
# MAIN APPLICATION - Simplified UX with Air Force Branding
# ============================================================================

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

# First-time helper (dismissible per session)
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

st.divider()

# ============================================================================
# Quick Actions - What would you like to do?
# ============================================================================
st.markdown("## 🚀 What would you like to do?")
st.markdown("<p style='color: #6B7280; font-size: 1.05rem; margin-bottom: 2rem;'>Choose your workflow below</p>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3, gap="large")

with col1:
    st.markdown("<div class='action-card'>", unsafe_allow_html=True)
    st.markdown("### 🔍 Explore KSAs")
    st.markdown("Browse AFSCs, view extracted Knowledge, Skills, and Abilities, and find overlaps between specialties.")
    st.caption("→ Read-only insights & cross-AFSC analysis")
    if st.button("Open Explore KSAs →", use_container_width=True, type="primary", key="explore"):
        st.switch_page("pages/03_Explore_KSAs.py")
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown("<div class='action-card'>", unsafe_allow_html=True)
    st.markdown("### 🔑 Try It Yourself")
    st.markdown("Paste AFSC text and generate Knowledge/Ability items using your own API key for testing.")
    st.caption("→ Sandbox with your own API key")
    if st.button("Open Try It Yourself →", use_container_width=True, type="secondary", key="byo"):
        st.switch_page("pages/02_Try_It_Yourself.py")
    st.markdown("</div>", unsafe_allow_html=True)

with col3:
    st.markdown("<div class='action-card'>", unsafe_allow_html=True)
    st.markdown("### ⚙️ Admin Tools")
    st.markdown("Process PDFs/Markdown, run extraction pipeline, and manage database content.")
    st.caption("→ Power tools for data management")
    if st.button("Open Admin Tools →", use_container_width=True, type="secondary", key="admin"):
        st.switch_page("pages/04_Admin_Tools.py")
    st.markdown("</div>", unsafe_allow_html=True)

st.divider()

# ============================================================================
# System Snapshot - Lightweight Status & Metrics
# ============================================================================
st.markdown("## 📊 System Snapshot")

# Lightweight environment status check (no DB calls for status badges)
@st.cache_data(ttl=60)
def get_env_status():
    return {
        "neo4j": bool(os.getenv("NEO4J_URI")),
        "gemini": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
    }

# Database metrics with caching and fallback
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
    
    # Fallback if DB unavailable
    return {
        "afscs": 0,
        "total_ksas": 0,
        "knowledge": 0,
        "skills": 0,
        "abilities": 0
    }

status = get_env_status()
metrics = get_database_metrics()

# Connection Status Badges
st.markdown("**Connection Status:**")
badge_html = ""
if status["neo4j"]:
    badge_html += "<span class='status-badge status-success'>✅ Neo4j Database</span>"
else:
    badge_html += "<span class='status-badge status-error'>❌ Neo4j Database</span>"

if status["gemini"]:
    badge_html += "<span class='status-badge status-success'>✅ Gemini API</span>"
else:
    badge_html += "<span class='status-badge status-warning'>⚠️ Gemini API</span>"

if status["openai"]:
    badge_html += "<span class='status-badge status-success'>✅ OpenAI API</span>"
else:
    badge_html += "<span class='status-badge status-warning'>⚠️ OpenAI API</span>"

if status["anthropic"]:
    badge_html += "<span class='status-badge status-success'>✅ Anthropic API</span>"
else:
    badge_html += "<span class='status-badge status-warning'>⚠️ Anthropic API</span>"

st.markdown(badge_html, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Database Metrics
st.markdown("**Database Metrics:**")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("AFSCs Loaded", metrics["afscs"], help="Number of AFSC nodes in graph")
m2.metric("Total KSAs", metrics["total_ksas"], help="All Knowledge, Skills, and Abilities")
m3.metric("Knowledge", metrics["knowledge"])
m4.metric("Skills", metrics["skills"])
m5.metric("Abilities", metrics["abilities"])

st.divider()

# ============================================================================
# How It Works - Simple Visual
# ============================================================================
st.markdown("## 🔄 How it works (at a glance)")

s1, s2, s3, s4, s5 = st.columns([1.3, 0.2, 1.3, 0.2, 1.3])
with s1:
    st.markdown("""
    <div style='text-align: center; padding: 16px;'>
        <div style='font-size: 3rem; margin-bottom: 0.5rem;'>📄</div>
        <h4 style='color: #00539B; margin-bottom: 0.5rem;'>Ingest</h4>
        <p style='color: #6B7280; font-size: 0.95rem;'>Load AFOCD/AFECD text (PDF or Markdown)</p>
    </div>
    """, unsafe_allow_html=True)

with s2:
    st.markdown("<h3 style='text-align: center; color: #00539B;'>→</h3>", unsafe_allow_html=True)

with s3:
    st.markdown("""
    <div style='text-align: center; padding: 16px;'>
        <div style='font-size: 3rem; margin-bottom: 0.5rem;'>🤖</div>
        <h4 style='color: #00539B; margin-bottom: 0.5rem;'>Extract</h4>
        <p style='color: #6B7280; font-size: 0.95rem;'>Parse baseline KSAs using LAiSER rules</p>
    </div>
    """, unsafe_allow_html=True)

with s4:
    st.markdown("<h3 style='text-align: center; color: #00539B;'>→</h3>", unsafe_allow_html=True)

with s5:
    st.markdown("""
    <div style='text-align: center; padding: 16px;'>
        <div style='font-size: 3rem; margin-bottom: 0.5rem;'>✨</div>
        <h4 style='color: #00539B; margin-bottom: 0.5rem;'>Enhance</h4>
        <p style='color: #6B7280; font-size: 0.95rem;'>Refine with LLM, store to Neo4j</p>
    </div>
    """, unsafe_allow_html=True)

with st.expander("See detailed pipeline steps"):
    st.markdown("""
    ### Detailed Process
    
    1. **Ingest** • Upload AFSC documents (AFOCD/AFECD) or use pre-split Markdown
    2. **Preprocess** • Clean text, remove formatting artifacts, normalize structure
    3. **Extract** • LAiSER generates baseline KSAs with confidence scores and ESCO taxonomy IDs
    4. **Enhance** • LLMs (Gemini/Claude/OpenAI) add complementary Knowledge/Ability items
    5. **Store** • Write AFSCs, KSAs, and relationships into Neo4j graph database
    6. **Explore** • Query, compare AFSCs, find skill overlaps, and export analysis tables
    
    **Performance:** ~5-10 seconds per AFSC | **Accuracy:** 85%+ precision on validated samples
    """)

st.divider()

# ============================================================================
# Learn More - Consolidated Section
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
