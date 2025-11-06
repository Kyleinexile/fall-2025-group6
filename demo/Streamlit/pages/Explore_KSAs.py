import os, sys, pathlib
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
import streamlit as st
from neo4j import GraphDatabase

st.set_page_config(page_title="Explore KSAs", page_icon="🔍", layout="wide")

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

@st.cache_resource
def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

@st.cache_data(ttl=60)
def get_afsc_list():
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as s:
        result = s.run("MATCH (a:AFSC) RETURN a.code as code ORDER BY code")
        return [r["code"] for r in result]

@st.cache_data(ttl=60)
def get_items_for_afsc(afsc_code: str):
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as s:
        result = s.run("""
            MATCH (a:AFSC {code: $code})-[:REQUIRES]->(k:KSA)
            OPTIONAL MATCH (k)-[:ALIGNS_TO]->(e:ESCOSkill)
            RETURN 
                k.text as text,
                k.type as type,
                coalesce(k.confidence, 0.0) as confidence,
                coalesce(k.source, '') as source,
                coalesce(e.esco_id, '') as esco_id
            ORDER BY type, confidence DESC, text
        """, {"code": afsc_code})
        return pd.DataFrame([r.data() for r in result])

def find_overlaps(afsc_codes: list):
    """Find items shared between multiple AFSCs"""
    driver = get_driver()
    with driver.session(database=NEO4J_DATABASE) as s:
        result = s.run("""
            MATCH (a:AFSC)-[:REQUIRES]->(k:KSA)
            WHERE a.code IN $codes
            OPTIONAL MATCH (k)-[:ALIGNS_TO]->(e:ESCOSkill)
            WITH k, e, collect(DISTINCT a.code) as afscs
            WHERE size(afscs) > 1
            RETURN 
                k.text as text,
                k.type as type,
                coalesce(e.esco_id, '') as esco_id,
                afscs,
                size(afscs) as overlap_count
            ORDER BY overlap_count DESC, text
        """, {"codes": afsc_codes})
        return pd.DataFrame([r.data() for r in result])

# Main UI
st.title("🔍 Explore KSAs")
st.caption("Query, filter, and analyze Knowledge, Skills, and Abilities across AFSCs")

# Sidebar: AFSC selection
with st.sidebar:
    st.markdown("### Select AFSCs")
    
    try:
        all_afscs = get_afsc_list()
        if not all_afscs:
            st.warning("No AFSCs in database")
            st.stop()
        
        st.caption(f"{len(all_afscs)} total AFSCs")
        
        # Multi-select
        selected = st.multiselect(
            "Choose one or more",
            all_afscs,
            max_selections=5,
            help="Select up to 5 AFSCs"
        )
        
        if not selected:
            st.info("👆 Select at least one AFSC")
            st.stop()
        
        st.success(f"{len(selected)} selected")
        
    except Exception as e:
        st.error(f"Connection error: {e}")
        st.stop()

# Main content
if len(selected) == 1:
    # Single AFSC view
    code = selected[0]
    st.markdown(f"## {code}")
    
    try:
        df = get_items_for_afsc(code)
        
        if df.empty:
            st.info(f"No items found for {code}")
            st.stop()
        
        # Stats
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Items", len(df))
        col2.metric("Knowledge", len(df[df["type"] == "knowledge"]))
        col3.metric("Skills", len(df[df["type"] == "skill"]))
        col4.metric("Abilities", len(df[df["type"] == "ability"]))
        col5.metric("ESCO Aligned", len(df[df["esco_id"] != ""]))
        
        # Filters
        st.markdown("### Filters")
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            type_filter = st.multiselect("Type", ["knowledge", "skill", "ability"], default=["knowledge", "skill", "ability"])
        with col_b:
            min_conf = st.slider("Min confidence", 0.0, 1.0, 0.0, 0.05)
        with col_c:
            search = st.text_input("Search text", placeholder="Filter items...")
        
        # Apply filters
        filtered = df[df["type"].isin(type_filter)]
        filtered = filtered[filtered["confidence"] >= min_conf]
        if search:
            filtered = filtered[filtered["text"].str.contains(search, case=False, na=False)]
        
        st.caption(f"Showing {len(filtered)} of {len(df)} items")
        
        # Display
        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True,
            column_config={
                "confidence": st.column_config.NumberColumn(format="%.2f"),
                "esco_id": st.column_config.TextColumn("ESCO ID")
            }
        )
        
        # Export
        csv = filtered.to_csv(index=False)
        st.download_button(
            "⬇️ Export CSV",
            csv,
            f"{code}_ksas.csv",
            "text/csv"
        )
        
    except Exception as e:
        st.error(f"Query error: {e}")

else:
    # Multi-AFSC comparison
    st.markdown(f"## Comparison: {', '.join(selected)}")
    
    tab1, tab2 = st.tabs(["📊 Overview", "🔗 Overlaps"])
    
    with tab1:
        st.markdown("### Individual Counts")
        
        data = []
        for code in selected:
            try:
                df = get_items_for_afsc(code)
                data.append({
                    "AFSC": code,
                    "Total": len(df),
                    "Knowledge": len(df[df["type"] == "knowledge"]),
                    "Skills": len(df[df["type"] == "skill"]),
                    "Abilities": len(df[df["type"] == "ability"]),
                    "ESCO": len(df[df["esco_id"] != ""])
                })
            except:
                pass
        
        if data:
            summary_df = pd.DataFrame(data)
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
            
            # Bar chart
            chart_data = summary_df.set_index("AFSC")[["Knowledge", "Skills", "Abilities"]]
            st.bar_chart(chart_data)
    
    with tab2:
        st.markdown("### Shared Items")
        st.caption("Items that appear in multiple selected AFSCs")
        
        try:
            overlaps = find_overlaps(selected)
            
            if overlaps.empty:
                st.info("No shared items found")
            else:
                st.metric("Shared Items", len(overlaps))
                
                # Filter by overlap count
                min_overlap = st.slider(
                    "Min shared by (AFSCs)",
                    2,
                    len(selected),
                    2
                )
                
                filtered = overlaps[overlaps["overlap_count"] >= min_overlap]
                st.caption(f"Showing {len(filtered)} items")
                
                # Format for display
                display_df = filtered.copy()
                display_df["afscs"] = display_df["afscs"].apply(lambda x: ", ".join(x))
                
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "overlap_count": st.column_config.NumberColumn("# AFSCs"),
                        "afscs": st.column_config.TextColumn("Found in"),
                        "esco_id": st.column_config.TextColumn("ESCO ID")
                    }
                )
                
                # Export
                csv = display_df.to_csv(index=False)
                st.download_button(
                    "⬇️ Export Overlaps",
                    csv,
                    f"overlaps_{'_'.join(selected[:3])}.csv",
                    "text/csv"
                )
                
        except Exception as e:
            st.error(f"Error finding overlaps: {e}")

# Help in sidebar
with st.sidebar:
    st.markdown("---")
    with st.expander("💡 Tips"):
        st.markdown("""
        **Single AFSC**: View and filter all items
        
        **Multiple AFSCs**: Compare counts and find shared items
        
        **Use filters**: Narrow down by type, confidence, or text search
        
        **Export**: Download filtered results as CSV
        """)