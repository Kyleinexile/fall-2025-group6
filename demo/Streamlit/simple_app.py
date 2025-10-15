import os
import streamlit as st
from neo4j import GraphDatabase

# Page config FIRST
st.set_page_config(page_title="USAF KSA Database", page_icon="✈️", layout="wide")

st.title("✈️ USAF KSA Database")
st.caption("Data source: AFSC → KSAs (AuraDB Free). Use the sidebar to filter/search.")

# Env-driven connection (works for Aura or local)
URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "")
DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

@st.cache_resource
def get_driver():
    return GraphDatabase.driver(URI, auth=(USER, PASSWORD))

def run_query(query, params=None):
    with get_driver().session(database=DATABASE) as session:
        result = session.run(query, params or {})
        return [r.data() for r in result]

# Sidebar
with st.sidebar:
    st.header("Filters")
    afsc_rows = run_query("MATCH (a:AFSC) RETURN a.code AS code ORDER BY code")
    afsc_list = [r["code"] for r in afsc_rows]
    selected = st.selectbox("Select AFSC:", afsc_list if afsc_list else ["(none)"])

    type_filter = st.multiselect(
        "KSA Types",
        options=["knowledge", "skill", "ability"],
        default=["knowledge", "skill", "ability"]
    )

    search = st.text_input("Search KSAs")

if afsc_list and selected and selected != "(none)":
    # Query KSAs (include ESCO from edge or item)
    ksas = run_query(
        """
        MATCH (a:AFSC {code: $code})-[r:REQUIRES]->(i:Item)
        RETURN i.name AS ksa,
               i.type AS type,
               coalesce(r.esco_id, i.esco_id) AS esco
        ORDER BY i.type, i.name
        """,
        {"code": selected}
    )

    # Client-side filters
    if type_filter:
        ksas = [k for k in ksas if k["type"] in type_filter]
    if search:
        s = search.lower()
        ksas = [k for k in ksas if s in k["ksa"].lower()]

    # Metrics
    st.subheader(f"{selected} — {len(ksas)} KSAs")
    col1, col2, col3 = st.columns(3)
    col1.metric("Knowledge", len([k for k in ksas if k["type"] == "knowledge"]))
    col2.metric("Skills", len([k for k in ksas if k["type"] == "skill"]))
    col3.metric("Abilities", len([k for k in ksas if k["type"] == "ability"]))

    # Display
for ksa_type in ["knowledge", "skill", "ability"]:
    items = [k for k in ksas if k["type"] == ksa_type]
    if items:
        st.write(f"**{ksa_type.title()}:**")
        for item in items:
            esco = item.get("esco")
            if esco:
                st.markdown(f"- {item['ksa']}  [ESCO]({esco})")
            else:
                st.markdown(f"- {item['ksa']}")


    # Download (unique key avoids duplicate element id)
    csv_data = "Type,KSA\n" + "\n".join([f"{k['type']},{k['ksa']}" for k in ksas])
    st.download_button(
        label="⬇️ Download CSV",
        data=csv_data,
        file_name=f"{selected}_ksas.csv",
        mime="text/csv",
        key=f"dl_{selected}"
    )

    # Overlaps
    st.markdown("---")
    if st.checkbox("Show overlapping AFSCs", key=f"ovlp_{selected}"):
        overlaps = run_query(
            """
            MATCH (a:AFSC {code: $code})-[:REQUIRES]->(i:Item)<-[:REQUIRES]-(b:AFSC)
            WHERE a.code <> b.code
            RETURN b.code AS afsc, count(DISTINCT i) AS shared
            ORDER BY shared DESC
            LIMIT 10
            """,
            {"code": selected}
        )
        if overlaps:
            st.write("**Shared KSAs with other AFSCs:**")
            for o in overlaps:
                st.write(f"- {o['afsc']}: {o['shared']} shared items")

# Footer
st.markdown("---")
st.caption("Built for AFSC → Civilian Skills Translation (Data Science Capstone).")
