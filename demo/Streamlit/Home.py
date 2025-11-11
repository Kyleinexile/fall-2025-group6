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
# SPLASH SCREEN - Entry Page
# ============================================================================
if 'entered' not in st.session_state:
    st.session_state.entered = False

if not st.session_state.entered:
    # Center content
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Air Force Image - Get absolute path
        current_dir = Path(__file__).parent
        image_path = current_dir / "assets" / "air force.jpg"
        
        if image_path.exists():
            st.image(str(image_path), use_container_width=True)
        else:
            st.warning("Air Force image not found")
        
        # Title and Description
        st.markdown("<h1 style='text-align: center;'>USAF KSA Extraction Pipeline</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center;'>Translating Military Skills to Civilian Careers</h3>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Project Description
        st.markdown("""
        <div style='text-align: center; font-size: 1.1em;'>
        <p>Automated extraction and analysis of Air Force Specialty Code knowledge requirements</p>
        <p><strong>MS Data Science Capstone Project</strong></p>
        <p>George Washington University | 2025</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Key Features
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown("### 🤖 AI-Powered")
            st.markdown("LAiSER + LLM extraction")
        with col_b:
            st.markdown("### 🔍 Comprehensive")
            st.markdown("Knowledge, Skills, Abilities")
        with col_c:
            st.markdown("### 🌐 Interactive")
            st.markdown("Real-time exploration")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Enter Button
        if st.button("🚀 Enter Application", type="primary", use_container_width=True):
            st.session_state.entered = True
            st.rerun()
    
    st.stop()

# ============================================================================
# MAIN APPLICATION - Only shown after entering
# ============================================================================

# Header
st.title("✈️ USAF KSA Extraction Pipeline")
st.markdown("**Automated extraction and analysis of Air Force Specialty Code knowledge requirements**")
st.caption("Capstone Project | MS Data Science | George Washington University | 2025")
st.divider()

# Live Database Stats
st.markdown("## 📊 Current Database Status")

try:
    NEO4J_URI = os.getenv("NEO4J_URI", "")
    NEO4J_USER = os.getenv("NEO4J_USER", "")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
    
    if all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session(database=NEO4J_DATABASE) as session:
            # Query with NEW schema (KSA nodes, REQUIRES relationships)
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
            
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("AFSCs Processed", result["afscs"] or 0)
            m2.metric("Total KSAs", result["total_ksas"] or 0)
            m3.metric("Knowledge", result["knowledge"] or 0)
            m4.metric("Skills", result["skills"] or 0)
            m5.metric("Abilities", result["abilities"] or 0)
            m6.metric("Skill Aligned", result["esco_aligned"] or 0)
            
        driver.close()
    else:
        st.warning("⚠️ Neo4j connection not configured")
        
except Exception as e:
    st.error(f"Could not load database stats: {str(e)[:100]}")

st.divider()

# Navigation Cards
st.markdown("## 🚀 Quick Access")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 🔍 Explore KSAs")
    st.markdown("Query, filter, and analyze extracted Knowledge, Skills, and Abilities across all AFSCs")
    st.markdown("**Features:**")
    st.markdown("- Search by AFSC with full titles")
    st.markdown("- Filter by type and confidence")
    st.markdown("- Find overlapping skills")
    st.markdown("- Export to CSV")
    if st.button("→ Explore KSAs", use_container_width=True, type="primary", key="explore"):
        st.switch_page("pages/03_Explore_KSAs.py")

with col2:
    st.markdown("### ⚙️ Admin Tools")
    st.markdown("Browse existing documents and process new AFSC text through the extraction pipeline")
    st.markdown("**Capabilities:**")
    st.markdown("- View all source documents")
    st.markdown("- Upload new AFSC data")
    st.markdown("- Run LAiSER + LLM pipeline")
    st.markdown("- Manage database content")
    if st.button("→ Admin Ingest", use_container_width=True, type="secondary", key="admin"):
        st.switch_page("pages/04_Admin_Tools.py")

with col3:
    st.markdown("### 🔑 Try It Yourself")
    st.markdown("Run KSA extraction on your own AFSC text using your API key")
    st.markdown("**Benefits:**")
    st.markdown("- Bring your own API key")
    st.markdown("- Test with custom text")
    st.markdown("- No quota limits")
    st.markdown("- Session-only storage")
    if st.button("→ BYO-API Query", use_container_width=True, type="secondary", key="byo"):
        st.switch_page("pages/02_Try_It_Yourself.py")

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
st.caption("🚀 USAF KSA Extraction Pipeline | Capstone Project 2025 | George Washington University")
