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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Global Font */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Air Force Blue Theme */
    .stButton>button[kind="primary"] {
        background-color: #00539B !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }
    .stButton>button[kind="primary"]:hover {
        background-color: #003D7A !important;
        color: white !important;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 83, 155, 0.3) !important;
    }
    
    .stButton>button[kind="secondary"] {
        background-color: white !important;
        border: 2px solid #00539B !important;
        color: #00539B !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }
    .stButton>button[kind="secondary"]:hover {
        background-color: #00539B !important;
        color: white !important;
        border: 2px solid #00539B !important;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 83, 155, 0.2) !important;
    }
    
    /* Metrics Styling */
    [data-testid="stMetricValue"] {
        font-size: 32px;
        font-weight: 700;
        color: #00539B;
    }
    [data-testid="stMetricLabel"] {
        font-size: 14px;
        font-weight: 600;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* Headers */
    h1 {
        color: #1F2937;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    h2 {
        color: #374151;
        font-weight: 600;
        margin-top: 2rem;
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
    
    /* Card Styling */
    .nav-card {
        padding: 24px;
        border-radius: 12px;
        border: 2px solid #E5E7EB;
        background: white;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        transition: all 0.3s ease;
        height: 100%;
    }
    .nav-card:hover {
        border-color: #00539B;
        box-shadow: 0 8px 24px rgba(0, 83, 155, 0.12);
        transform: translateY(-4px);
    }
    
    /* Expander Styling */
    .streamlit-expanderHeader {
        font-weight: 600;
        color: #374151;
        font-size: 16px;
    }
    
    /* Status Badge */
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.3px;
    }
    .status-success {
        background-color: #D1FAE5;
        color: #065F46;
    }
    .status-warning {
        background-color: #FEF3C7;
        color: #92400E;
    }
    .status-info {
        background-color: #DBEAFE;
        color: #1E40AF;
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
        border-radius: 16px;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
        margin-bottom: 2rem;
    }
    
    /* Gradient Background for Header */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
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
        else:
            st.info("📸 Air Force image: assets/air force.jpg")
        
        # Title and Description
        st.markdown("""
        <h1 style='text-align: center; font-size: 3rem; font-weight: 700; 
                   color: #00539B; margin-bottom: 0.5rem;'>
            USAF KSA Extraction Pipeline
        </h1>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <h3 style='text-align: center; font-weight: 400; color: #6B7280; 
                   margin-top: 0; margin-bottom: 2rem;'>
            Translating Military Skills to Civilian Careers
        </h3>
        """, unsafe_allow_html=True)
        
        st.markdown("<hr style='margin: 2rem 0; border-color: #E5E7EB;'>", unsafe_allow_html=True)
        
        # Project Description
        st.markdown("""
        <div style='text-align: center; font-size: 1.1em; color: #4B5563; margin-bottom: 2rem;'>
            <p style='margin-bottom: 0.5rem;'>Automated extraction and analysis of Air Force Specialty Code knowledge requirements</p>
            <p style='font-weight: 600; color: #00539B; margin-bottom: 0.5rem;'>MS Data Science Capstone Project</p>
            <p style='color: #6B7280;'>George Washington University | 2025</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<hr style='margin: 2rem 0; border-color: #E5E7EB;'>", unsafe_allow_html=True)
        
        # Key Features with Icons
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            st.markdown("""
            <div style='text-align: center; padding: 20px;'>
                <div style='font-size: 3rem; margin-bottom: 0.5rem;'>🤖</div>
                <h3 style='color: #00539B; font-size: 1.2rem; margin-bottom: 0.5rem;'>AI-Powered</h3>
                <p style='color: #6B7280; font-size: 0.95rem;'>LAiSER + LLM extraction</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col_b:
            st.markdown("""
            <div style='text-align: center; padding: 20px;'>
                <div style='font-size: 3rem; margin-bottom: 0.5rem;'>🔍</div>
                <h3 style='color: #00539B; font-size: 1.2rem; margin-bottom: 0.5rem;'>Comprehensive</h3>
                <p style='color: #6B7280; font-size: 0.95rem;'>Knowledge, Skills, Abilities</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col_c:
            st.markdown("""
            <div style='text-align: center; padding: 20px;'>
                <div style='font-size: 3rem; margin-bottom: 0.5rem;'>🌐</div>
                <h3 style='color: #00539B; font-size: 1.2rem; margin-bottom: 0.5rem;'>Interactive</h3>
                <p style='color: #6B7280; font-size: 0.95rem;'>Real-time exploration</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Enter Button
        if st.button("🚀 Enter Application", type="primary", use_container_width=True):
            st.session_state.entered = True
            st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ============================================================================
# MAIN APPLICATION - Only shown after entering
# ============================================================================

# Header with Gradient Effect
st.markdown("""
<h1 style='font-size: 2.5rem; margin-bottom: 0.5rem;'>
    ✈️ USAF KSA Extraction Pipeline
</h1>
""", unsafe_allow_html=True)

st.markdown("""
<p style='font-size: 1.1rem; color: #6B7280; margin-bottom: 0.5rem;'>
    <strong>Automated extraction and analysis of Air Force Specialty Code knowledge requirements</strong>
</p>
""", unsafe_allow_html=True)

st.caption("Capstone Project | MS Data Science | George Washington University | 2025")
st.divider()

# Live Database Stats with Enhanced Styling
st.markdown("## 📊 Current Database Status")

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
                OPTIONAL MATCH (k)-[:ALIGNS_TO]->(e:ESCOSkill)
                RETURN 
                    count(DISTINCT a) as afscs,
                    count(DISTINCT k) as total_ksas,
                    count(DISTINCT CASE WHEN k.type = 'knowledge' THEN k END) as knowledge,
                    count(DISTINCT CASE WHEN k.type = 'skill' THEN k END) as skills,
                    count(DISTINCT CASE WHEN k.type = 'ability' THEN k END) as abilities,
                    count(DISTINCT e) as esco_aligned
            """).single()
            
            # Enhanced Metrics Display
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("AFSCs Processed", result["afscs"] or 0, delta=None)
            m2.metric("Total KSAs", result["total_ksas"] or 0, delta=None)
            m3.metric("Knowledge", result["knowledge"] or 0, delta=None)
            m4.metric("Skills", result["skills"] or 0, delta=None)
            m5.metric("Abilities", result["abilities"] or 0, delta=None)
            m6.metric("ESCO Aligned", result["esco_aligned"] or 0, delta=None)
            
        driver.close()
        
        # Status Badge
        st.markdown("""
        <div style='margin-top: 1rem;'>
            <span class='status-badge status-success'>✓ Database Connected</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("⚠️ Neo4j connection not configured")
        st.markdown("<span class='status-badge status-warning'>⚠ Configuration Required</span>", unsafe_allow_html=True)
        
except Exception as e:
    st.error(f"Could not load database stats: {str(e)[:100]}")
    st.markdown("<span class='status-badge status-warning'>⚠ Connection Error</span>", unsafe_allow_html=True)

st.divider()

# Navigation Cards with Enhanced Styling
st.markdown("## 🚀 Quick Access")
st.markdown("<br>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3, gap="large")

with col1:
    st.markdown("<div class='nav-card'>", unsafe_allow_html=True)
    st.markdown("### 🔍 Explore KSAs")
    st.markdown("Query, filter, and analyze extracted Knowledge, Skills, and Abilities across all AFSCs")
    st.markdown("**Features:**")
    st.markdown("- Search by AFSC with full titles")
    st.markdown("- Filter by type and confidence")
    st.markdown("- Find overlapping skills")
    st.markdown("- Export to CSV")
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("→ Explore KSAs", use_container_width=True, type="primary", key="explore"):
        st.switch_page("pages/03_Explore_KSAs.py")
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown("<div class='nav-card'>", unsafe_allow_html=True)
    st.markdown("### 🔑 Try It Yourself")
    st.markdown("Run KSA extraction on your own AFSC text using your API key")
    st.markdown("**Benefits:**")
    st.markdown("- Bring your own API key")
    st.markdown("- Test with custom text")
    st.markdown("- No quota limits")
    st.markdown("- Session-only storage")
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("→ Try It Yourself", use_container_width=True, type="secondary", key="byo"):
        st.switch_page("pages/02_Try_It_Yourself.py")
    st.markdown("</div>", unsafe_allow_html=True)

with col3:
    st.markdown("<div class='nav-card'>", unsafe_allow_html=True)
    st.markdown("### ⚙️ Admin Tools")
    st.markdown("Browse existing documents and process new AFSC text through the extraction pipeline")
    st.markdown("**Capabilities:**")
    st.markdown("- View all source documents")
    st.markdown("- Upload new AFSC data")
    st.markdown("- Run LAiSER + LLM pipeline")
    st.markdown("- Manage database content")
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("→ Admin Tools", use_container_width=True, type="secondary", key="admin"):
        st.switch_page("pages/04_Admin_Tools.py")
    st.markdown("</div>", unsafe_allow_html=True)

st.divider()

# About Project (Collapsible)
with st.expander("📖 About This Project", expanded=False):
    st.markdown("""
    ### Problem Statement
    Manual KSA extraction from Air Force Specialty Code documentation is:
    - ⏱️ **Time-consuming** - Hours per AFSC
    - 🎯 **Inconsistent** - Variable quality across analysts
    - 🔗 **Unstandardized** - No civilian skill taxonomy mapping
    - 📊 **Unscalable** - Cannot process hundreds of AFSCs
    
    ### Solution
    This pipeline automates KSA extraction using:
    - **LAiSER** - Skill extraction with ESCO/LAiSER taxonomy alignment
    - **LLM Enhancement** - Knowledge and Ability generation via Gemini/Claude
    - **Neo4j Graph** - Structured storage enabling overlap analysis
    - **Streamlit Interface** - Professional web-based exploration tool
    
    ### Key Results
    - ✅ **12 AFSCs processed** (100% of initial target)
    - ✅ **264 unique KSAs extracted** (~31 per AFSC average)
    - ✅ **29% cross-AFSC overlap** - Validates skill transferability
    - ✅ **30 civilian framework alignments** - ESCO + LAiSER taxonomy
    - ✅ **Sub-minute processing** - 1.3 minutes for all 12 AFSCs
    """)

# KSA Definitions
with st.expander("📚 What are KSAs?", expanded=False):
    col_k, col_s, col_a = st.columns(3)
    
    with col_k:
        st.markdown("### 📖 Knowledge")
        st.markdown("""
        **Body of information necessary to perform tasks**
        
        Examples:
        - Intelligence cycle fundamentals
        - Geospatial analysis techniques
        - Threat assessment methodologies
        
        Characteristics:
        - Theoretical understanding
        - Factual information
        - Domain expertise
        """)
    
    with col_s:
        st.markdown("### 🛠️ Skills")
        st.markdown("""
        **Observable, measurable proficiencies**
        
        Examples:
        - Perform intelligence analysis
        - Conduct collection management
        - Prepare intelligence reports
        
        Characteristics:
        - Action-oriented
        - Demonstrable competencies
        - Technical capabilities
        """)
    
    with col_a:
        st.markdown("### 💪 Abilities")
        st.markdown("""
        **Enduring attributes enabling performance**
        
        Examples:
        - Synthesize multi-source data
        - Work under time constraints
        - Communicate complex information
        
        Characteristics:
        - Cognitive/physical capacities
        - Adaptable traits
        - Performance enablers
        """)

# Pipeline Architecture
with st.expander("🔄 Pipeline Architecture", expanded=False):
    st.markdown("""
    ### Extraction Pipeline
    
    Our system combines multiple technologies for comprehensive KSA extraction:
    """)
    
    st.code("""
┌─────────────────────────────────────────────────────────┐
│ 1. INPUT: AFSC Description (PDF/Text)                  │
│    └─ Air Force Specialty Code documentation           │
└────────────────┬────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────┐
│ 2. PREPROCESSING: Text Cleaning                        │
│    └─ Remove artifacts, normalize structure            │
└────────────────┬────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────┐
│ 3. LAiSER: Skill Extraction                            │
│    • Pattern-based phrase detection                     │
│    • ESCO/LAiSER taxonomy matching                      │
│    • Confidence scoring                                 │
│    OUTPUT: 25-30 Skills with taxonomy IDs               │
└────────────────┬────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────┐
│ 4. LLM ENHANCEMENT: Knowledge + Ability Generation     │
│    • Context-aware K/A generation                       │
│    • Dynamic hints from extracted skills                │
│    • Deduplication and sanitization                     │
│    OUTPUT: 3-6 Knowledge + Ability items                │
└────────────────┬────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────┐
│ 5. STORAGE: Neo4j Graph Database                       │
│    • AFSC nodes with titles                             │
│    • KSA nodes (deduplicated)                           │
│    • REQUIRES relationships                             │
│    • ALIGNS_TO skill taxonomy                           │
└────────────────┬────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────────────┐
│ 6. INTERFACE: Interactive Exploration                  │
│    • Search and filter capabilities                     │
│    • Cross-AFSC comparison                              │
│    • Export functionality                               │
└─────────────────────────────────────────────────────────┘
    """, language="text")

# Tech Stack
with st.expander("🔧 Technology Stack", expanded=False):
    col_tech1, col_tech2, col_tech3 = st.columns(3)
    
    with col_tech1:
        st.markdown("### 🤖 AI/ML Components")
        st.markdown("""
        - **LAiSER** - Skill extraction & taxonomy mapping
        - **Google Gemini 1.5 Flash** - Primary LLM
        - **Anthropic Claude Sonnet 4.5** - Fallback LLM
        - **Pattern Matching** - Intelligent fallback
        """)
    
    with col_tech2:
        st.markdown("### 💾 Data & Storage")
        st.markdown("""
        - **Neo4j Aura** - Cloud graph database
        - **ESCO Taxonomy** - EU skills framework
        - **LAiSER Taxonomy** - Extended skill codes
        - **Python 3.11** - Core language
        """)
    
    with col_tech3:
        st.markdown("### 🌐 Interface & Deployment")
        st.markdown("""
        - **Streamlit** - Web framework
        - **GitHub** - Version control
        - **Streamlit Cloud** - Production hosting
        - **Windows/Codespaces** - Dev environments
        """)

# System Status
with st.expander("🔧 System Configuration", expanded=False):
    st.markdown("### Connection Status")
    
    col_s1, col_s2 = st.columns(2)
    
    with col_s1:
        st.code(f"""
Neo4j URI: {os.getenv('NEO4J_URI', 'Not set')[:50]}...
Database: {os.getenv('NEO4J_DATABASE', 'neo4j')}
User: {os.getenv('NEO4J_USER', 'Not set')}
        """)
    
    with col_s2:
        st.code(f"""
LAiSER Mode: {os.getenv('USE_LAISER', 'Not set')}
Gemini API: {'✅ Set' if os.getenv('GEMINI_API_KEY') else '❌ Not set'}
OpenAI API: {'✅ Set' if os.getenv('OPENAI_API_KEY') else '❌ Not set'}
        """)

st.divider()

# Footer with Enhanced Styling
st.markdown("""
<div style='text-align: center; padding: 2rem 0; color: #6B7280; font-size: 0.9rem;'>
    <p style='margin-bottom: 0.5rem;'>
        <strong style='color: #00539B;'>🚀 USAF KSA Extraction Pipeline</strong>
    </p>
    <p style='margin: 0;'>
        Capstone Project 2025 | George Washington University | MS Data Science
    </p>
</div>
""", unsafe_allow_html=True)