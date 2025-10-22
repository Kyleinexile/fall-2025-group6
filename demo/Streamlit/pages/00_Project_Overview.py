import streamlit as st
import sys
import pathlib

# Setup path
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

st.set_page_config(page_title="Project Overview", page_icon="📊", layout="wide")

# Header
st.title("🎯 USAF KSA Extraction Pipeline")
st.markdown("### Capstone Project: Automated Knowledge, Skills, and Abilities Extraction")
st.markdown("**Presented by:** Kyle | **Date:** October 22, 2025")
st.divider()

# Project Overview Section
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("## 📋 Project Overview")
    st.markdown("""
    This capstone project develops an **automated pipeline** for extracting Knowledge, Skills, and Abilities (KSAs) 
    from U.S. Air Force Specialty Code (AFSC) descriptions. The system combines LAiSER (Leveraging AI for Skills Extraction & Research) 
    with modern Large Language Models to create a comprehensive KSA database stored in a Neo4j graph database.
    
    **Problem Statement:**
    - Manual KSA extraction from AFSC documentation is time-consuming and inconsistent
    - No standardized taxonomy mapping for military skills
    - Difficult to compare skills across different career fields
    
    **Solution:**
    - Automated extraction using LAiSER + LLM enhancement
    - ESCO taxonomy integration for skill standardization
    - Interactive graph database for analysis and comparison
    """)

with col2:
    st.markdown("## 🎯 Key Objectives")
    st.success("✅ Integrate LAiSER framework")
    st.success("✅ Extract all 3 KSA types")
    st.success("✅ Minimum 3 KSAs per AFSC")
    st.success("✅ Graph database storage")
    st.success("✅ Professional web interface")
    st.info("🔄 Process 12 AFSCs")

st.divider()

# KSA Definitions Section
st.markdown("## 📚 What are KSAs?")

col_k, col_s, col_a = st.columns(3)

with col_k:
    st.markdown("### 📖 Knowledge")
    st.markdown("""
    **Definition:** The body of information that is necessary to perform a task.
    
    **Examples:**
    - Knowledge of intelligence cycle fundamentals
    - Knowledge of geospatial analysis techniques
    - Knowledge of threat assessment methodologies
    
    **Characteristics:**
    - Theoretical understanding
    - Factual information
    - Domain expertise
    """)

with col_s:
    st.markdown("### 🛠️ Skills")
    st.markdown("""
    **Definition:** Observable, measurable proficiencies required to perform job activities.
    
    **Examples:**
    - Perform intelligence data analysis
    - Conduct collection management
    - Prepare intelligence reports
    
    **Characteristics:**
    - Action-oriented
    - Demonstrable competencies
    - Technical capabilities
    """)

with col_a:
    st.markdown("### 💪 Abilities")
    st.markdown("""
    **Definition:** Enduring attributes that enable task performance under varying conditions.
    
    **Examples:**
    - Ability to synthesize multi-source data
    - Ability to work under time constraints
    - Ability to communicate complex information
    
    **Characteristics:**
    - Cognitive/physical capacities
    - Adaptable traits
    - Performance enablers
    """)

st.divider()

# Pipeline Architecture Section
st.markdown("## 🔄 Extraction Pipeline Architecture")

st.markdown("""
Our pipeline combines multiple technologies to achieve comprehensive KSA extraction:
""")

# Visual pipeline flow
st.code("""
┌─────────────────────────────────────────────────────────────────┐
│ 1. INPUT: AFSC Description (PDF/Text)                          │
│    • Air Force Specialty Code documentation                     │
│    • Duties, responsibilities, and requirements                 │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. PREPROCESSING: Text Cleaning                                │
│    • Remove formatting artifacts                                │
│    • Normalize text structure                                   │
│    • Extract relevant sections                                  │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. LAiSER: Skill Extraction                                     │
│    • Pattern-based phrase detection                             │
│    • ESCO taxonomy matching                                     │
│    • Confidence scoring                                         │
│    OUTPUT: 3-6 Skills with ESCO IDs                            │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. LLM ENHANCEMENT: Knowledge + Ability Generation             │
│    • Google Gemini 1.5 Flash (primary)                         │
│    • Anthropic Claude (fallback)                               │
│    • Context-aware K/A statements                              │
│    OUTPUT: 3-6 Knowledge + Ability items                       │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. CONSOLIDATION: Deduplication & Validation                   │
│    • Remove duplicate items                                     │
│    • Validate K/S/A balance                                     │
│    • Quality filtering                                          │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. STORAGE: Neo4j Graph Database                               │
│    • AFSC nodes with relationships                              │
│    • KSA nodes with properties                                  │
│    • HAS_ITEM relationships                                     │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│ 7. DISPLAY: Interactive Streamlit Interface                    │
│    • Search and filter capabilities                             │
│    • Cross-AFSC comparison                                      │
│    • Export functionality                                       │
└─────────────────────────────────────────────────────────────────┘
""", language="text")

st.divider()

# Technology Stack Section
st.markdown("## 🔧 Technology Stack")

col_tech1, col_tech2, col_tech3 = st.columns(3)

with col_tech1:
    st.markdown("### 🤖 AI/ML Components")
    st.markdown("""
    - **LAiSER**: Skill extraction & ESCO mapping
    - **Google Gemini 1.5 Flash**: Free LLM (15 RPM)
    - **Anthropic Claude Sonnet 4.5**: Fallback LLM
    - **Pattern Matching**: Fallback extraction
    """)

with col_tech2:
    st.markdown("### 💾 Data & Storage")
    st.markdown("""
    - **Neo4j Aura**: Graph database (cloud)
    - **ESCO Taxonomy**: EU skills classification
    - **Python 3.11**: Core language
    - **Pandas**: Data processing
    """)

with col_tech3:
    st.markdown("### 🌐 Interface & Deployment")
    st.markdown("""
    - **Streamlit**: Web application framework
    - **GitHub**: Version control & CI/CD
    - **Streamlit Cloud**: Production hosting
    - **Codespaces**: Development environment
    """)

st.divider()

# Current Progress Section
st.markdown("## 📊 Current Project Status")

# Metrics
col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)

with col_m1:
    st.metric("AFSCs Processed", "1/12", delta="8%")
with col_m2:
    st.metric("Total KSAs", "7+", delta="per AFSC")
with col_m3:
    st.metric("Avg Confidence", "0.63", delta="Good")
with col_m4:
    st.metric("Processing Time", "~8 sec", delta="per AFSC")
with col_m5:
    st.metric("System Status", "✅ Online")

st.markdown("---")

# Progress breakdown
col_p1, col_p2 = st.columns(2)

with col_p1:
    st.markdown("### ✅ Completed Components")
    st.markdown("""
    - ✅ LAiSER integration (pattern-based fallback working)
    - ✅ LLM enhancement with Gemini + Anthropic
    - ✅ Heuristic fallback (always functional)
    - ✅ Neo4j database schema and connections
    - ✅ Streamlit 5-page web interface
    - ✅ Admin Ingest pipeline (LAiSER → LLM → DB)
    - ✅ Explore KSAs page with filtering
    - ✅ View Docs page for source material
    - ✅ End-to-end pipeline testing
    """)

with col_p2:
    st.markdown("### 🔄 In Progress")
    st.markdown("""
    - 🔄 Processing remaining 11 AFSCs (target: 3-5/day)
    - 🔄 Quality assurance review
    - 🔄 Statistical analysis and reporting
    - 🔄 Cross-AFSC comparison analysis
    
    ### 🎯 Next Steps
    - Complete 12 AFSC processing
    - Generate comprehensive statistics
    - Finalize presentation materials
    - Prepare deployment documentation
    """)

st.divider()

# Results & Performance Section
st.markdown("## 📈 Pipeline Performance")

col_r1, col_r2 = st.columns(2)

with col_r1:
    st.markdown("### Extraction Results (AFSC 14N)")
    results_data = {
        "Component": ["LAiSER Skills", "LLM Knowledge", "LLM Abilities", "Total"],
        "Count": [3, 3, 1, 7],
        "Avg Confidence": [0.55, 0.70, 0.70, 0.63],
        "Source": ["fallback-pattern", "llm-gemini", "llm-gemini", "mixed"]
    }
    st.dataframe(results_data, use_container_width=True, hide_index=True)
    
    st.markdown("**Quality Metrics:**")
    st.markdown("- ✅ All 3 KSA types present")
    st.markdown("- ✅ Exceeds 3 KSA minimum (7 total)")
    st.markdown("- ✅ Confidence scores 0.50-0.70 (acceptable)")

with col_r2:
    st.markdown("### System Capabilities")
    st.markdown("""
    **Strengths:**
    - ✅ Consistent K/S/A extraction across AFSCs
    - ✅ Automatic fallback prevents failures
    - ✅ Free API usage (no ongoing costs)
    - ✅ Real-time processing (~8 seconds)
    - ✅ Scalable to hundreds of AFSCs
    
    **Future Improvements:**
    - 🔮 Enable full LAiSER engine with models
    - 🔮 Implement batch processing
    - 🔮 Add custom ESCO taxonomy training
    - 🔮 Automated quality scoring
    """)

st.divider()

# Demo Workflow Section
st.markdown("## 🎬 Live Demo Workflow")

st.markdown("""
### What We'll Demonstrate:

1. **Admin Ingest Page** - Load AFSC, watch pipeline process, view results
2. **Explore KSAs Page** - Search, filter, compare, and export data
3. **View Docs Page** - Access source documentation
4. **Technical Architecture** - Review code and database structure
""")

st.divider()

st.markdown("---")
st.caption("🚀 USAF KSA Extraction Pipeline | Capstone Project 2025")
