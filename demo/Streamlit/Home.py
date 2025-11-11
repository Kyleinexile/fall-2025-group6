import streamlit as st

st.set_page_config(
    page_title="USAF KSA Explorer",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Header
st.title("✈️ USAF KSA Explorer")
st.markdown("**Extract, explore, and analyze Air Force Specialty Code knowledge requirements**")

st.divider()

# Quick workflow guide
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📄 Step 1: Find Docs")
    st.markdown("Browse official AFECD/AFOCD PDFs or search for specific AFSC documentation")
    if st.button("→ View Documentation", use_container_width=True, type="secondary"):
        st.switch_page("pages/02_View_Docs.py")

with col2:
    st.markdown("### 🔧 Step 2: Ingest")
    st.markdown("Process AFSC text through the extraction pipeline into the knowledge graph")
    if st.button("→ Admin Ingest", use_container_width=True, type="secondary"):
        st.switch_page("pages/01_Admin_Ingest.py")

with col3:
    st.markdown("### 🔍 Step 3: Explore")
    st.markdown("Query, filter, and analyze KSAs across AFSCs with overlap analysis")
    if st.button("→ Explore KSAs", use_container_width=True, type="primary"):
        # This would go to your main explore page when you create it
        st.info("Create an 'Explore KSAs' page next!")

st.divider()

# Quick stats (if connected to Neo4j)
st.markdown("### 📊 Database Overview")

import os
from neo4j import GraphDatabase

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
                OPTIONAL MATCH (a)-[:HAS_ITEM|REQUIRES]->(i:Item)
                RETURN count(DISTINCT a) as afscs, 
                       count(DISTINCT i) as items,
                       count(DISTINCT CASE WHEN i.item_type = 'knowledge' THEN i END) as knowledge,
                       count(DISTINCT CASE WHEN i.item_type = 'skill' THEN i END) as skills,
                       count(DISTINCT CASE WHEN i.item_type = 'ability' THEN i END) as abilities
            """).single()
            
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("AFSCs", result["afscs"])
            m2.metric("Total Items", result["items"])
            m3.metric("Knowledge", result["knowledge"])
            m4.metric("Skills", result["skills"])
            m5.metric("Abilities", result["abilities"])
        driver.close()
    else:
        st.info("💡 Connect to Neo4j to see database statistics")
        
except Exception as e:
    st.warning(f"Could not load stats: {str(e)[:100]}")

st.divider()

# Help section
with st.expander("ℹ️ About This Tool"):
    st.markdown("""
    **Purpose**: Extract and analyze Knowledge, Skills, and Abilities (KSAs) from Air Force Specialty Codes
    
    **Workflow**:
    1. **View Docs** - Search official AFSC documentation (AFECD/AFOCD PDFs)
    2. **Admin Ingest** - Process AFSC text through the extraction pipeline
    3. **Explore KSAs** - Query and analyze the knowledge graph
    
    **Tech Stack**:
    - 🔍 LAiSER extraction with ESCO skill alignment
    - 📊 Neo4j Aura knowledge graph
    - 🎯 LLM-powered enhancement (optional)
    - 📈 Streamlit interface
    """)

with st.expander("🔧 Connection Status"):
    st.code(f"""
NEO4J_URI: {os.getenv('NEO4J_URI', 'Not set')}
NEO4J_DATABASE: {os.getenv('NEO4J_DATABASE', 'neo4j')}
LAiSER_MODE: {os.getenv('LAISER_MODE', 'Not set')}
USE_LAISER: {os.getenv('USE_LAISER', 'Not set')}
    """)
