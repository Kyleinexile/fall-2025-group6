# demo/Streamlit/pages/01_Admin_Ingest.py
from __future__ import annotations

# --- repo path bootstrap (so imports work when run via streamlit) ---
import sys, pathlib, os, json, time
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]  # repo root (…/fall-2025-group6)
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# -------------------------------------------------------------------

from typing import Dict, Any, List
import re
import pandas as pd
import streamlit as st
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

# --- Import your pipeline pieces ---
from afsc_pipeline.preprocess import clean_afsc_text  # noqa: F401 (import ensures module is reachable)
from afsc_pipeline.pipeline import run_pipeline, ItemDraft, ItemType  # noqa: F401

# ----------------------------
# Env / Config
# ----------------------------
NEO4J_URI = os.getenv("NEO4J_URI", "")
NEO4J_USER = os.getenv("NEO4J_USER", "")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# Optional gate (simple): set ADMIN_KEY in your Streamlit secrets or env.
ADMIN_KEY = os.getenv("ADMIN_KEY", "")

APP_TITLE = "Admin: AFSC Ingest (Run Pipeline → Aura → Viewer)"

# ----------------------------
# Helpers
# ----------------------------
@st.cache_resource(show_spinner=False)
def get_driver():
    if not (NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
        raise RuntimeError("Neo4j env vars are not fully set.")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session(database=NEO4J_DATABASE) as s:
            s.run("RETURN 1 AS ok").single()
    except (ServiceUnavailable, AuthError) as e:
        raise RuntimeError(f"Neo4j connection failed: {e}") from e
    return driver


def summarize_items(items: List[ItemDraft]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(columns=["text", "item_type", "confidence", "source", "esco_id", "content_sig"])
    rows = []
    for it in items:
        rows.append({
            "text": it.text,
            "item_type": it.item_type.value if hasattr(it.item_type, "value") else str(it.item_type),
            "confidence": float(getattr(it, "confidence", 0.0) or 0.0),
            "source": getattr(it, "source", "") or "",
            "esco_id": getattr(it, "esco_id", "") or "",
            "content_sig": getattr(it, "content_sig", ""),
        })
    df = pd.DataFrame(rows)
    return df.sort_values(["confidence", "text"], ascending=[False, True]).reset_index(drop=True)

# ----------------------------
# UI
# ----------------------------
st.set_page_config(page_title=APP_TITLE, page_icon="🧩", layout="wide")
st.title(APP_TITLE)
st.caption("Paste AFSC text → Run pipeline → Write to Aura → Verify in the viewer page")

with st.expander("Connection", expanded=False):
    st.code(f"NEO4J_URI={NEO4J_URI}\nNEO4J_DATABASE={NEO4J_DATABASE}", language="bash")

# Optional admin key check
if ADMIN_KEY:
    entered = st.text_input("Admin key", type="password", placeholder="Required to run", help="Set ADMIN_KEY in environment or Streamlit Secrets.")
    if entered.strip() != ADMIN_KEY.strip():
        st.info("Enter the admin key to enable ingestion.")
        st.stop()

# =========================
# Single-AFSC ingest
# =========================
st.subheader("Single AFSC ingest")

col1, col2 = st.columns([1, 3], gap="large")
with col1:
    afsc_code = st.text_input("AFSC code", value="1N1X1", help="Example: 1N1X1")
    min_conf = st.slider("Min confidence (post-filter)", 0.0, 1.0, 0.0, 0.05)

    st.markdown("**LAiSER settings (env-driven)**")
    st.caption("USE_LAISER=true, LAISER_MODE=lib (CPU align fallback), LAISER_ALIGN_TOPK=25 recommended.")
    run_btn = st.button("🚀 Run pipeline", type="primary", use_container_width=True)

with col2:
    afsc_text = st.text_area(
        "AFSC text",
        height=300,
        placeholder="Paste the AFSC (Duties / Knowledge / Skills / Abilities) text here…",
    )

if run_btn:
    if not afsc_code.strip() or not afsc_text.strip():
        st.error("AFSC code and AFSC text are required.")
        st.stop()

    st.info("Starting pipeline…")
    with st.spinner("Extracting & writing to Neo4j…"):
        try:
            driver = get_driver()
            with driver.session(database=NEO4J_DATABASE) as session:
                summary: Dict[str, Any] = run_pipeline(
                    afsc_code=afsc_code.strip(),
                    afsc_raw_text=afsc_text,
                    neo4j_session=session,
                )
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.stop()

    # Show results
    st.success("Done.")
    colA, colB, colC, colD = st.columns(4)
    colA.metric("Items (raw)", summary.get("n_items_raw", 0))
    colB.metric("After filters", summary.get("n_items_after_filters", 0))
    colC.metric("After dedupe", summary.get("n_items_after_dedupe", 0))
    colD.metric("Used fallback?", "Yes" if summary.get("used_fallback") else "No")

    # Items preview (from pipeline output if present; else query Aura)
    items_written = summary.get("items")
    if items_written and isinstance(items_written, list):
        df = summarize_items(items_written)
        st.subheader("Preview of items (from pipeline output)")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.subheader("Preview of items (fresh from Aura)")
        try:
            with driver.session(database=NEO4J_DATABASE) as s:
                rows = list(s.run("""
                    MATCH (a:AFSC {code: $code})-[:HAS_ITEM|:REQUIRES]->(i)
                    RETURN i.text AS text, i.item_type AS item_type,
                           coalesce(i.confidence,0.0) AS confidence,
                           coalesce(i.source,'') AS source,
                           coalesce(i.esco_id,'') AS esco_id,
                           coalesce(i.content_sig,'') AS content_sig
                    ORDER BY confidence DESC, text ASC
                """, {"code": afsc_code.strip()}))
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.warning(f"Could not fetch items for preview: {e}")

    st.markdown("---")
    st.caption("Switch to the main viewer page to see these items with filters/CSV.")

# =========================
# Bulk JSONL ingest (Claude output)
# =========================
st.subheader("Bulk JSONL ingest")
st.caption("Upload a JSONL with one AFSC per line (fields like: afsc, md, sections, source). Each line will be run through the same pipeline.")

jsonl_file = st.file_uploader("Upload JSONL (one AFSC per line)", type=["jsonl"])
if jsonl_file is not None:
    if st.button("🚀 Ingest JSONL", use_container_width=True):
        try:
            driver = get_driver()
        except Exception as e:
            st.error(f"Neo4j connection error: {e}")
            st.stop()

        lines = jsonl_file.getvalue().decode("utf-8").splitlines()
        total = len(lines)
        ok = fail = 0
        pb = st.progress(0)
        log = st.empty()

        with driver.session(database=NEO4J_DATABASE) as session:
            for i, line in enumerate(lines, start=1):
                try:
                    obj = json.loads(line)
                    afsc_code = (obj.get("afsc") or "").strip()
                    # Prefer the Markdown body; fall back to structured sections
                    afsc_text = obj.get("md") or json.dumps(obj.get("sections", {}), ensure_ascii=False)
                    if not afsc_code or not afsc_text:
                        fail += 1
                    else:
                        run_pipeline(
                            afsc_code=afsc_code,
                            afsc_raw_text=afsc_text,
                            neo4j_session=session,
                        )
                        ok += 1
                except Exception as e:
                    fail += 1
                pb.progress(min(i / total, 1.0))
                log.text(f"Ingested {i}/{total} … success={ok}, fail={fail}")
                time.sleep(0.01)

        st.success(f"Bulk ingest complete — success: {ok}, failed: {fail}. Open the main tab to verify.")


st.markdown("---")
st.subheader("🛑 Danger Zone — Clear AFSC data")

codes_text = st.text_area(
    "AFSC codes to clear (comma/space/newline separated)",
    placeholder="e.g., 1N1X1, 1N0X1",
)
mode = st.radio(
    "Delete mode",
    ["Delete AFSC(s) + orphaned Items", "Only remove relationships"],
    index=0,
    horizontal=False,
)

if st.button("Clear selected AFSCs", type="secondary"):
    codes = [c.strip() for c in re.split(r"[,\s]+", codes_text or "") if c.strip()]
    if not codes:
        st.warning("Provide at least one AFSC code.")
    else:
        driver = get_driver()
        with driver.session(database=NEO4J_DATABASE) as s:
            if mode == "Only remove relationships":
                q = """
                WITH $codes AS codes
                UNWIND codes AS code
                MATCH (a:AFSC {code:code})-[r:HAS_ITEM|REQUIRES]->(:Item)
                DELETE r
                """
                s.run(q, {"codes": codes})
            else:
                q = """
                WITH $codes AS codes
                UNWIND codes AS code
                MATCH (a:AFSC {code:code})
                WITH collect(DISTINCT a) AS afscs
                UNWIND afscs AS a
                OPTIONAL MATCH (a)-[:HAS_ITEM|REQUIRES]->(i:Item)
                WITH collect(DISTINCT a) AS afscs, collect(DISTINCT i) AS wasItems
                FOREACH (x IN afscs | DETACH DELETE x)
                UNWIND wasItems AS i
                WITH DISTINCT i
                WHERE NOT ( (:AFSC)-[:HAS_ITEM|REQUIRES]->(i) )
                DETACH DELETE i
                """
                s.run(q, {"codes": codes})
        st.success(f"Cleared {len(codes)} AFSC(s). Check the viewer tab.")

