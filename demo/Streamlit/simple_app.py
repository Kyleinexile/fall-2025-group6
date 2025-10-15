# demo/Streamlit/simple_app.py
from __future__ import annotations

import os
import re
import urllib.parse
from typing import List, Dict, Any, Tuple, Optional

import pandas as pd
import streamlit as st
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError


# ----------------------------
# Env / Config
# ----------------------------
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

APP_TITLE = "AFSC → Civilian KSAs (Aura Live)"
APP_SUBTITLE = "Search • Filter • Overlaps • CSV"

# GEOINT-ish demo regex (case-insensitive)
GEOINT_REGEX = r"(?i)(imag(e|ery)|geospatial|geoint|gis|remote sensing|target(ing| development)|mensurat|terrain|azimuth|coordinates|order of battle|brief(ing)?|synthesi[sz]e|damage assessment|annotation|mensuration|collection requirement|AOC|IPO[Ee])"


# ----------------------------
# Helpers
# ----------------------------
@st.cache_resource(show_spinner=False)
def get_driver():
    if not (NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
        raise RuntimeError("Neo4j connection env vars are not fully set.")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    # probe connection
    try:
        with driver.session(database=NEO4J_DATABASE) as s:
            s.run("RETURN 1 AS ok").single()
    except (ServiceUnavailable, AuthError) as e:
        raise RuntimeError(f"Neo4j connection failed: {e}") from e
    return driver


@st.cache_data(show_spinner=False, ttl=30)
def fetch_afsc_list() -> List[str]:
    with get_driver().session(database=NEO4J_DATABASE) as s:
        res = s.run("MATCH (a:AFSC) RETURN a.code AS code ORDER BY code")
        return [r["code"] for r in res]


@st.cache_data(show_spinner=False, ttl=15)
def fetch_items_for_afsc(afsc_code: str) -> pd.DataFrame:
    """
    Returns items and basic overlap stats for a given AFSC.

    Columns:
      text, item_type, confidence, source, esco_id, content_sig, overlap_count
    """
    cypher = """
    MATCH (a:AFSC {code: $code})-[:HAS_ITEM|REQUIRES]->(i)
    WITH a, i
    OPTIONAL MATCH (other:AFSC)-[:HAS_ITEM|REQUIRES]->(i)
    WITH i, collect(DISTINCT other.code) AS afscs
    RETURN
      i.text AS text,
      i.item_type AS item_type,
      coalesce(i.confidence, 0.0) AS confidence,
      coalesce(i.source, 'unknown') AS source,
      coalesce(i.esco_id, '') AS esco_id,
      coalesce(i.content_sig, '') AS content_sig,
      size(afscs) AS overlap_count
    ORDER BY confidence DESC, text ASC
    """
    with get_driver().session(database=NEO4J_DATABASE) as s:
        res = s.run(cypher, {"code": afsc_code})
        rows = [r.data() for r in res]  # <-- convert Record -> dict

    if not rows:
        return pd.DataFrame(columns=[
            "text","item_type","confidence","source","esco_id","content_sig","overlap_count"
        ])
    return pd.DataFrame(rows)



def esco_link_for(value: str) -> str:
    """Return a markdown link for an ESCO id or a search link if format is unknown."""
    if not value:
        return ""
    v = str(value).strip()
    if v.startswith("http://") or v.startswith("https://"):
        return f"[ESCO]({v})"
    # Fallback to ESCO site search
    q = urllib.parse.quote(v)
    return f"[ESCO](https://esco.ec.europa.eu/en/classification?text={q})"


def filter_dataframe(
    df: pd.DataFrame,
    *,
    item_types: List[str],
    min_conf: float,
    search_text: str,
    regex_text: Optional[str] = None,
) -> pd.DataFrame:
    out = df.copy()
    if item_types:
        out = out[out["item_type"].isin(item_types)]
    if min_conf > 0:
        out = out[out["confidence"] >= min_conf]
    if search_text:
        s = search_text.strip().lower()
        out = out[out["text"].str.lower().str.contains(s, na=False)]
    if regex_text:
        pattern = regex_text.strip()
        if pattern:
            try:
                out = out[out["text"].str.contains(pattern, regex=True, na=False)]
            except re.error:
                st.warning("Invalid regex pattern. Showing un-regexed results.")
    return out.reset_index(drop=True)


def df_with_display_cols(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    display = df.copy()
    # Add ESCO link column (markdown)
    display["ESCO"] = display["esco_id"].apply(esco_link_for)
    # Reorder columns for display
    cols = ["text", "item_type", "confidence", "source", "ESCO", "overlap_count", "esco_id", "content_sig"]
    for c in cols:
        if c not in display.columns:
            display[c] = ""
    return display[cols]


# ----------------------------
# UI
# ----------------------------
st.set_page_config(page_title=APP_TITLE, page_icon="🛰️", layout="wide")
st.title(APP_TITLE)
st.caption(APP_SUBTITLE)

# Connection status
with st.expander("Connection", expanded=False):
    st.code(f"NEO4J_URI={NEO4J_URI}\nNEO4J_DATABASE={NEO4J_DATABASE}", language="bash")

# Sidebar: AFSC picker & filters
with st.sidebar:
    st.header("Controls")

    afsc_list = fetch_afsc_list()
    if not afsc_list:
        st.error("No AFSC nodes found in the database.")
        st.stop()

    selected_afsc = st.selectbox("AFSC", afsc_list, index=max(0, afsc_list.index("1N1X1") if "1N1X1" in afsc_list else 0), key="afsc_select")

    st.markdown("---")
    st.subheader("Filters")

    # Demo-friendly defaults: show 'skill' only and 0.55 confidence
    type_opts = ["knowledge", "skill", "ability"]
    pick_types = st.multiselect("Item Types", type_opts, default=["skill"], key="type_filter")

    min_conf = st.slider("Min Confidence", 0.0, 1.0, 0.55, 0.05, key="conf_filter")

    search_text = st.text_input("Search text (simple contains)", placeholder="e.g., intelligence cycle", key="search_filter")

    use_geoint_preset = st.checkbox("Use GEOINT demo regex", value=True)
    regex_text = st.text_input(
        "Regex (advanced)",
        value=GEOINT_REGEX if use_geoint_preset else "",
        help="Python-style regex applied to item text, case-insensitive supported (e.g., (?i)imagery)",
        key="regex_filter",
    )

    st.markdown("---")
    csv_filename = f"afsc_{selected_afsc}_items.csv"
    st.caption("CSV export includes: text, item_type, confidence, source, esco_id, content_sig, overlap_count.")

# Main area
try:
    df_all = fetch_items_for_afsc(selected_afsc)
except RuntimeError as e:
    st.error(str(e))
    st.stop()

left, right = st.columns([3, 2], gap="large")

with left:
    st.subheader(f"Items for AFSC {selected_afsc}")

    df_filtered = filter_dataframe(
        df_all,
        item_types=pick_types,
        min_conf=min_conf,
        search_text=search_text,
        regex_text=regex_text,
    )

    st.write(f"Showing **{len(df_filtered)}** of **{len(df_all)}** items")

    # Display table with ESCO markdown links
    df_display = df_with_display_cols(df_filtered)
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True
    )

with right:
    st.subheader("Quick Stats")
    k = int((df_filtered["item_type"] == "knowledge").sum()) if not df_filtered.empty else 0
    s_ = int((df_filtered["item_type"] == "skill").sum()) if not df_filtered.empty else 0
    a = int((df_filtered["item_type"] == "ability").sum()) if not df_filtered.empty else 0
    overlaps = int(df_filtered["overlap_count"].sum()) if "overlap_count" in df_filtered.columns and not df_filtered.empty else 0

    st.metric("Knowledge", k)
    st.metric("Skills", s_)
    st.metric("Abilities", a)
    st.metric("Total Overlap Sum", overlaps)

    st.markdown("---")
    # CSV export includes esco_id + content_sig for downstream QA
    csv_cols = ["text","item_type","confidence","source","esco_id","content_sig","overlap_count"]
    csv_df = df_filtered[csv_cols] if not df_filtered.empty else pd.DataFrame(columns=csv_cols)
    csv_bytes = csv_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="⬇️ Download CSV",
        data=csv_bytes,
        file_name=csv_filename,
        mime="text/csv",
        key=f"dl_csv_{selected_afsc}"
    )

st.markdown("---")
st.caption(
    "Tip: ESCO badges/links appear when an item has an `esco_id`. "
    "If `esco_id` is a full URI it links directly; otherwise it opens an ESCO search."
)
