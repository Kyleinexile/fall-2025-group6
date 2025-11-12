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
        margin-top: 3rem;
        margin-bottom: 1.5rem;
    }
    h3 {
        color: #1F2937;
        font-weight: 600;
    }
    
    /* Dividers */
    hr {
        margin: 3rem 0;
        border: none;
        border-top: 2px solid #E5E7EB;
    }
    
    /* Better Typography */
    p {
        line-height: 1.6;
        color: #4B5563;
    }
    
    /* Loading Skeleton */
    .skeleton {
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 200% 100%;
        animation: loading 1.5s ease-in-out infinite;
        height: 80px;
        border-radius: 8px;
    }
    @keyframes loading {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
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
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
        margin-bottom: 2rem;
    }
    
    /* Expander Improvements */
    .streamlit-expanderHeader {
        font-weight: 600;
        color: #374151;
        font-size: 16px;
        background-color: #F9FAFB;
        border-radius: 8px;
    }
    
    /* Caption Improvements */
    .stCaptionContainer {
        font-size: 13px;
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
        <h1 style='text-align: center; font-size: 3.2rem; font-weight: 800; 
                   color: #00539B; margin-bottom: 2rem; line-height: 1.2;'>
            Military Knowledge, Skills and Abilities (KSA) Pipeline
        </h1>
        """, unsafe_allow_html=True)
        
        # Enter Button - Prominently Placed
        if st.button("🚀 Enter Application", type="primary", use_container_width=True):
            st.session_state.entered = True
            st.rerun()
        
        st.markdown("<hr style='margin: 2.5rem 0; border-color: #E5E7EB;'>", unsafe_allow_html=True)
        
        # Key Features - Moved to Middle
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
        
        # Project Description - Moved to Bottom
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
# MAIN APPLICATION - Enhanced UX with Merged Sections
# ============================================================================

# Header
st.markdown("""
<h1 style='font-size: 2.75rem; margin-bottom: 0.5rem; font-weight: 800;'>
    ✈️ USAF KSA Extraction Pipeline
</h1>
""", unsafe_allow_html=True)

st.markdown("""
<p style='font-size: 1.15rem; color: #6B7280; margin-bottom: 0.5rem; line-height: 1.5;'>
    <strong>Automated extraction and analysis of Air Force Specialty Code knowledge requirements</strong>
</p>
""", unsafe_allow_html=True)

st.caption("Capstone Project | MS Data Science | George Washington University | 2025")
st.divider()

# ============================================================================
# MERGED SECTION: Dashboard Overview + Quick Access
# ============================================================================
st.markdown("## 📊 Dashboard Overview & Quick Access")
st.markdown("<p style='color: #6B7280; font-size: 1.05rem; margin-bottom: 2rem;'>Current system status and navigation</p>", unsafe_allow_html=True)

# Two-column layout: Status on left, Navigation on right
col_status, col_nav = st.columns([1, 2], gap="large")

with col_status:
    st.markdown("### System Status")
    
    # Create placeholder for loading state
    stats_placeholder = st.empty()
    
    try:
        NEO4J_URI = os.getenv("NEO4J_URI", "")
        NEO4J_USER = os.getenv("NEO4J_USER", "")
        NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
        NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
        
        if all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
            # Show loading skeleton
            with stats_placeholder.container():
                st.markdown('<div class="skeleton"></div>', unsafe_allow_html=True)
            
            # Fetch data
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
                
                # Replace skeleton with actual metrics
                with stats_placeholder.container():
                    st.markdown("**Database Metrics:**")
                    m1, m2 = st.columns(2)
                    m1.metric("AFSCs", result["afscs"] or 0)
                    m2.metric("Total KSAs", result["total_ksas"] or 0)
                    
                    m3, m4, m5 = st.columns(3)
                    m3.metric("K", result["knowledge"] or 0)
                    m4.metric("S", result["skills"] or 0)
                    m5.metric("A", result["abilities"] or 0)
                    
                    st.metric("ESCO Aligned", result["esco_aligned"] or 0)
            
            driver.close()
            
            # Connection Status Badges
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**Connection Status:**")
            st.markdown("<span class='status-badge status-success'>✅ Neo4j Database</span>", unsafe_allow_html=True)
            
            # API Key Status
            if GEMINI_API_KEY:
                st.markdown("<span class='status-badge status-success'>✅ Gemini API</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span class='status-badge status-error'>❌ Gemini API</span>", unsafe_allow_html=True)
            
            if OPENAI_API_KEY:
                st.markdown("<span class='status-badge status-success'>✅ OpenAI API</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span class='status-badge status-warning'>⚠️ OpenAI API</span>", unsafe_allow_html=True)
            
            if ANTHROPIC_API_KEY:
                st.markdown("<span class='status-badge status-success'>✅ Anthropic API</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span class='status-badge status-warning'>⚠️ Anthropic API</span>", unsafe_allow_html=True)
                
        else:
            with stats_placeholder.container():
                st.warning("⚠️ Neo4j connection not configured")
                st.markdown("<span class='status-badge status-warning'>⚠️ Configuration Required</span>", unsafe_allow_html=True)
            
    except Exception as e:
        with stats_placeholder.container():
            st.error(f"❌ Could not load database stats: {str(e)[:100]}")
            st.markdown("<span class='status-badge status-error'>❌ Connection Error</span>", unsafe_allow_html=True)

with col_nav:
    st.markdown("### Quick Navigation")
    st.markdown("<p style='color: #6B7280; margin-bottom: 1.5rem;'>Choose your workflow</p>", unsafe_allow_html=True)
    
    # Card 1: Explore KSAs
    with st.container():
        st.markdown("#### 🔍 Explore KSAs")
        st.markdown("Query and analyze Knowledge, Skills, and Abilities across all AFSCs")
        st.caption("→ Read-only insights & analysis")
        if st.button("→ Explore KSAs", use_container_width=True, type="primary", key="explore"):
            st.switch_page("pages/03_Explore_KSAs.py")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Card 2: Try It Yourself
    with st.container():
        st.markdown("#### 🔑 Try It Yourself")
        st.markdown("Test KSA extraction with your own API key and AFSC text")
        st.caption("→ Sandbox with your own API key")
        if st.button("→ Try It Yourself", use_container_width=True, type="secondary", key="byo"):
            st.switch_page("pages/02_Try_It_Yourself.py")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Card 3: Admin Tools
    with st.container():
        st.markdown("#### ⚙️ Admin Tools")
        st.markdown("Manage documents and process new AFSC data through the pipeline")
        st.caption("→ Power tools for data management")
        if st.button("→ Admin Tools", use_container_width=True, type="secondary", key="admin"):
            st.switch_page("pages/04_Admin_Tools.py")

st.divider()

# ============================================================================
# MERGED SECTION: Pipeline Architecture + How It Works
# ============================================================================
with st.expander("🔄 Pipeline Architecture & How It Works", expanded=False):
    st.markdown("### How the Pipeline Works")
    
    st.markdown("""
    Our extraction pipeline combines AI technologies to automatically identify and classify military skills:
    
    **3-Step Process:**
    
    1. **Extract** → GWU's LAiSER identifies skills from AFSC documentation using pattern matching and ESCO taxonomy alignment
    
    2. **Enhance** → LLMs (Gemini/Claude) generate complementary Knowledge and Ability statements based on extracted skills
    
    3. **Store** → Neo4j graph database enables cross-AFSC analysis, overlap detection, and civilian skill mapping
    
    ---
    
    **Performance:** ~5-10 seconds per AFSC | **Accuracy:** 85%+ precision on validated samples
    """)
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Detailed Pipeline Steps")
    
    # Visual Step Cards with centered white text
    steps = [
        ("📄", "INPUT", "AFSC Documentation", "Source: Official AFOCD (Enlisted) and AFECD (Officer) publications providing detailed specialty descriptions"),
        ("🧹", "PREPROCESSING", "Text Cleaning", "Removes headers, footers, page numbers, and formatting artifacts; normalizes structure and prepares for analysis"),
        ("🤖", "LAiSER EXTRACTION", "Skill Extraction", "Pattern detection identifies skill phrases; ESCO taxonomy provides standardized skill codes (25-30 skills per AFSC)"),
        ("✨", "LLM ENHANCEMENT", "K/A Generation", "Gemini 1.5 Flash or Claude Sonnet 4 generate Knowledge and Ability items based on extracted skills (3-6 items)"),
        ("💾", "NEO4J STORAGE", "Graph Database", "Structured storage with AFSC nodes, KSA nodes, and relationships; enables career path mapping and overlap analysis"),
        ("🌐", "WEB INTERFACE", "Interactive Exploration", "Streamlit interface provides search, filtering, export, and cross-AFSC comparison capabilities")
    ]
    
    for i, (icon, title, subtitle, desc) in enumerate(steps):
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #00539B 0%, #003D7A 100%); 
                    color: white; padding: 24px; border-radius: 12px; margin-bottom: 16px;
                    box-shadow: 0 4px 12px rgba(0, 83, 155, 0.2);'>
            <div style='display: flex; align-items: center;'>
                <span style='font-size: 3rem; margin-right: 24px; text-align: center; min-width: 60px;'>{icon}</span>
                <div style='text-align: center; flex-grow: 1;'>
                    <h4 style='margin: 0; color: white; font-weight: 700; font-size: 1.2rem;'>Step {i+1}: {title}</h4>
                    <p style='margin: 8px 0; font-weight: 600; color: #FFF; font-size: 1.05rem;'>{subtitle}</p>
                    <p style='margin: 0; font-size: 14px; color: #FFF; line-height: 1.5;'>{desc}</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if i < len(steps) - 1:
            st.markdown("<div style='text-align: center; margin: 8px 0; font-size: 1.5rem;'>⬇️</div>", unsafe_allow_html=True)

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
    - **GWU's LAiSER** - Skill extraction with ESCO/LAiSER taxonomy alignment
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

# Tech Stack
with st.expander("🔧 Technology Stack", expanded=False):
    col_tech1, col_tech2, col_tech3 = st.columns(3)
    
    with col_tech1:
        st.markdown("### 🤖 AI/ML Components")
        st.markdown("""
        - **LAiSER (GWU)** - Skill extraction & taxonomy mapping
        - **Google Gemini 1.5 Flash** - Primary LLM
        - **Anthropic Claude Sonnet 4** - Fallback LLM
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
Anthropic API: {'✅ Set' if os.getenv('ANTHROPIC_API_KEY') else '❌ Not set'}
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
